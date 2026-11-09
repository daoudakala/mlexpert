"""Règles métier du module comptabilite.

Deux services pour la partie référentiel, à l'image de ses deux niveaux
(voir models.py et repository.py) :

- `ServicePlanComptableGlobal` : gère le référentiel partagé (comptes
  globaux). Construit avec `db` seul, comme `ServiceDroits` — ce n'est
  pas une ressource d'une entreprise, mais de la plateforme, réservée à
  l'administration (cahier, Annexe B).
- `ServiceComptabilite` : le plan comptable applicable, les journaux ET
  les écritures d'UNE entreprise. Construit avec `(db, entreprise_id)`,
  comme `ServiceExercices`.

Attribut `journal_activite` plutôt que `journal` (utilisé ailleurs, ex.
`ServiceExercices.journal`) : ici "journal" désigne déjà un objet métier
du module (`Journal`), le nommer pareil pour le service d'audit aurait
prêté à confusion.

Partie transactionnelle (`Ecriture`/`LigneEcriture`) : une écriture se
crée toujours avec la totalité de ses lignes en un seul appel (pas de
saisie ligne à ligne côté service) — c'est ce qui permet de vérifier
l'équilibre débit/crédit dès la création, pas seulement à la validation.
`valider_ecriture` attribue le numéro séquentiel (par journal et par
exercice) et rend l'écriture immuable : `modifier_ecriture` et
`supprimer_ecriture` refusent ensuite toute action dessus. Corriger une
écriture validée passe par `extourner_ecriture`, qui crée une NOUVELLE
écriture en brouillon avec les mêmes lignes, débit et crédit inversés —
à valider séparément, comme n'importe quelle écriture.

Limite connue, assumée à ce stade : `valider_ecriture` calcule le
prochain numéro en comptant les écritures déjà validées, sans verrou
explicite sur la ligne — deux validations strictement simultanées sur le
même journal/exercice pourraient en théorie calculer le même numéro.
Une vraie séquence en base (ou un verrou `SELECT ... FOR UPDATE`) serait
nécessaire avant une mise en production ; non fait ici pour rester dans
la portée de cette étape.
"""

import calendar
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.core.exceptions import AccesRefuse, Conflit, RessourceIntrouvable, ValidationMetier
from app.modules.comptabilite.import_utils import analyser_fichier, analyser_fichier_ecritures
from app.modules.comptabilite.models import (
    Compte,
    Ecriture,
    EcritureRecurrente,
    Journal,
    LigneEcriture,
    LigneEcritureRecurrente,
    LigneModeleEcriture,
    ModeleEcriture,
    PeriodiciteRecurrence,
    StatutEcriture,
    TypeJournal,
)
from app.modules.comptabilite.repository import (
    RepositoryComptes,
    RepositoryComptesGlobal,
    RepositoryEcritures,
    RepositoryEcrituresRecurrentes,
    RepositoryJournaux,
    RepositoryLignesEcriture,
    RepositoryLignesEcritureRecurrente,
    RepositoryLignesModeleEcriture,
    RepositoryModelesEcriture,
)
from app.modules.dashboards.repository import RepositoryReporting
from app.modules.entreprises.repository import RepositoryEntreprises
from app.modules.exercices.models import Exercice, StatutExercice
from app.modules.exercices.repository import RepositoryExercice
from app.modules.journal_activite.models import TypeAction
from app.modules.journal_activite.service import ServiceJournalActivite
from app.modules.tiers.repository import RepositoryTiers


@dataclass
class LigneSaisie:
    """Une ligne saisie côté appelant, avant qu'elle devienne une
    `LigneEcriture` en base. Exactement un des deux montants doit être
    strictement positif, l'autre à zéro (voir `_valider_lignes`)."""

    compte_id: uuid.UUID
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")
    tiers_id: uuid.UUID | None = None
    libelle: str | None = None
    date_echeance: date | None = None


@dataclass
class LigneModeleSaisie:
    """Une ligne de modèle saisie côté appelant (voir `ModeleEcriture` :
    compte + sens figés, jamais de montant)."""

    compte_id: uuid.UUID
    sens: str  # "debit" ou "credit", voir `SensLigne`
    libelle: str | None = None


@dataclass
class MontantLigneModele:
    """Le montant renseigné pour une ligne de modèle au moment de
    l'appliquer (voir `ServiceComptabilite.appliquer_modele`). Un montant
    à zéro (ou une ligne absente de la liste) omet simplement cette ligne
    dans l'écriture générée — utile pour un modèle dont certaines lignes
    ne concernent pas toutes les occurrences (ex. une charge optionnelle)."""

    ligne_modele_id: uuid.UUID
    montant: Decimal


@dataclass
class LigneEcritureRecurrenteSaisie:
    """Une ligne de récurrence saisie côté appelant (voir
    `EcritureRecurrente` : compte, sens ET montant sont figés, à la
    différence d'une ligne de modèle)."""

    compte_id: uuid.UUID
    sens: str  # "debit" ou "credit", voir `SensLigne`
    montant: Decimal
    libelle: str | None = None


@dataclass
class EcheanceIgnoree:
    """Une occurrence que `generer_echeances` n'a pas pu créer (exercice
    clôturé, compte désactivé...) — reportée plutôt que fatale pour les
    échéances suivantes, même philosophie que `EcritureImportIgnoree`."""

    date_echeance: date
    raison: str


@dataclass
class ResultatGenerationEcheances:
    ecritures_creees: list[Ecriture] = field(default_factory=list)
    ignorees: list[EcheanceIgnoree] = field(default_factory=list)


def _decimal_importee(valeur: str) -> Decimal:
    """Un montant tel qu'il arrive d'un fichier importé : chaîne vide ou
    blanche -> zéro (une ligne de débit n'a pas de valeur en colonne
    crédit, et réciproquement) ; virgule tolérée comme séparateur
    décimal, en plus du point."""
    nettoyee = (valeur or "").strip().replace(" ", "").replace(",", ".")
    if not nettoyee:
        return Decimal("0")
    try:
        return Decimal(nettoyee)
    except InvalidOperation:
        raise ValidationMetier(f"Montant invalide : '{valeur}'.")


def _ajouter_mois(une_date: date, mois: int, *, jour_ancre: int) -> date:
    """Avance `une_date` de `mois` mois, en revenant à `jour_ancre` (le
    jour du mois de la date de DÉBUT de la récurrence) chaque fois que le
    mois cible le permet, et en se repliant sur le dernier jour du mois
    sinon (ex. jour_ancre=31, avril -> 30/04, mais le mois suivant qui a
    31 jours revient bien au 31, jamais de dérive cumulative vers un jour
    plus petit). Jamais de `ValueError` sur un mois plus court. Pas de
    dépendance à `python-dateutil` : la bibliothèque est installée dans
    l'environnement mais n'est déclarée dans aucun manifeste du projet et
    n'est utilisée nulle part ailleurs dans `app/` — pour ne pas
    introduire une dépendance incohérente avec le reste du code, ce
    calcul reste fait à la main avec `calendar.monthrange`."""
    mois_total = une_date.month - 1 + mois
    annee = une_date.year + mois_total // 12
    mois_resultat = mois_total % 12 + 1
    dernier_jour_du_mois = calendar.monthrange(annee, mois_resultat)[1]
    jour = min(jour_ancre, dernier_jour_du_mois)
    return date(annee, mois_resultat, jour)


def _prochaine_echeance(date_actuelle: date, periodicite: str, *, jour_ancre: int) -> date:
    if periodicite == PeriodiciteRecurrence.MENSUELLE.value:
        return _ajouter_mois(date_actuelle, 1, jour_ancre=jour_ancre)
    if periodicite == PeriodiciteRecurrence.TRIMESTRIELLE.value:
        return _ajouter_mois(date_actuelle, 3, jour_ancre=jour_ancre)
    if periodicite == PeriodiciteRecurrence.ANNUELLE.value:
        return _ajouter_mois(date_actuelle, 12, jour_ancre=jour_ancre)
    raise ValidationMetier(f"Périodicité de récurrence inconnue : '{periodicite}'.")


def _valider_classe(classe: int) -> None:
    if not 1 <= classe <= 8:
        raise ValidationMetier("La classe d'un compte doit être comprise entre 1 et 8.")


def _valider_coherence_collectif(*, est_collectif: bool, lettrable: bool) -> None:
    if est_collectif and not lettrable:
        raise ValidationMetier("Un compte collectif doit être lettrable.")


def _prefixe_significatif(numero: str) -> str:
    """Le plan SYSCOHADA complète souvent un numéro avec des zéros de
    bourrage à droite pour atteindre une largeur fixe (ex. "411000" pour
    "Clients" : seul "411" est significatif). Un sous-compte ("411001")
    ne préfixe donc jamais littéralement le numéro complet de son parent
    — il préfixe son radical, une fois les zéros de fin retirés. C'est ce
    radical qui sert de test de filiation, pas le numéro brut."""
    radical = numero.rstrip("0")
    return radical or numero  # cas limite "000..." : rien à retirer


def _valider_parent(repository, parent_id: uuid.UUID | None, *, numero: str, classe: int) -> Compte | None:
    """Résout et valide un `compte_parent_id` optionnel. `repository` est
    `RepositoryComptesGlobal` (référentiel global : un parent ne peut être
    qu'un autre compte global, son `.obtenir()` filtre déjà là-dessus) ou
    `RepositoryComptes` (une entreprise : un parent peut être global ou une
    extension de la MÊME entreprise — même filtre déjà appliqué par
    `.obtenir()`). Pas de détection de cycle nécessaire : le parent doit
    déjà exister en base, un compte ne peut donc jamais devenir son propre
    ancêtre."""
    if parent_id is None:
        return None
    parent = repository.obtenir(parent_id)
    if parent is None:
        raise RessourceIntrouvable("Compte parent introuvable.")
    if parent.classe != classe:
        raise ValidationMetier(
            f"Le compte parent {parent.numero} appartient à la classe {parent.classe} ; "
            "un sous-compte doit rester dans la même classe."
        )
    prefixe = _prefixe_significatif(parent.numero)
    if numero == parent.numero or not numero.startswith(prefixe):
        raise ValidationMetier(
            f"Le numéro d'un sous-compte doit commencer par le radical du numéro de son "
            f"compte parent ({parent.numero}, soit « {prefixe} »)."
        )
    return parent


def _meilleur_parent(comptes_connus: dict[str, Compte], numero: str) -> Compte | None:
    """Pendant un import, aucune colonne ne désigne le parent : il est
    déduit du numéro lui-même — le compte déjà connu dont le numéro est,
    une fois ses zéros de fin retirés (voir `_prefixe_significatif`), le
    plus long préfixe de `numero` (ex. pour "4111002", "411100" est
    préféré à "411" s'il existe déjà)."""
    meilleur: Compte | None = None
    for candidat_numero, candidat in comptes_connus.items():
        if candidat_numero == numero or len(candidat_numero) > len(numero):
            continue
        if numero.startswith(_prefixe_significatif(candidat_numero)):
            if meilleur is None or len(candidat_numero) > len(meilleur.numero):
                meilleur = candidat
    return meilleur


@dataclass
class CompteImportIgnore:
    numero: str
    libelle: str
    raison: str


@dataclass
class ResultatImportComptes:
    comptes_crees: list[Compte]
    ignores: list[CompteImportIgnore]


@dataclass
class EcritureImportIgnoree:
    journal: str
    date: str
    piece: str
    raison: str


@dataclass
class ResultatImportEcritures:
    ecritures_creees: list[Ecriture]
    ignorees: list[EcritureImportIgnoree]


@dataclass
class LigneLettrage:
    """Une ligne d'écriture enrichie des informations de l'écriture
    porteuse (date, numéro, référence, libellé) — ce que l'écran de
    lettrage manuel affiche pour que l'utilisateur reconnaisse quelle
    facture/paiement correspond à quelle ligne (section 8.2 du cahier)."""

    id: uuid.UUID
    ecriture_id: uuid.UUID
    date_ecriture: date
    numero: str | None
    reference_piece: str | None
    libelle_ecriture: str
    libelle_ligne: str | None
    debit: Decimal
    credit: Decimal
    tiers_id: uuid.UUID | None
    code_lettrage: str | None


class ServicePlanComptableGlobal:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.comptes = RepositoryComptesGlobal(db)
        self.journal_activite = ServiceJournalActivite(db)

    def creer_compte(
        self,
        *,
        auteur_id: uuid.UUID,
        numero: str,
        libelle: str,
        classe: int,
        lettrable: bool = False,
        est_collectif: bool = False,
        compte_parent_id: uuid.UUID | None = None,
    ) -> Compte:
        _valider_classe(classe)
        _valider_coherence_collectif(est_collectif=est_collectif, lettrable=lettrable)
        if self.comptes.obtenir_par_numero(numero) is not None:
            raise Conflit(f"Le compte {numero} existe déjà dans le référentiel global.")
        parent = _valider_parent(self.comptes, compte_parent_id, numero=numero, classe=classe)

        compte = Compte(
            numero=numero,
            libelle=libelle,
            classe=classe,
            lettrable=lettrable,
            est_collectif=est_collectif,
            compte_parent_id=parent.id if parent else None,
        )
        self.comptes.ajouter(compte)
        self.journal_activite.enregistrer(
            module="comptabilite",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            type_objet="Compte",
            objet_id=compte.id,
            description=f"Création du compte global {numero} — {libelle}.",
            valeurs_apres={"numero": numero, "libelle": libelle, "classe": classe},
        )
        return compte

    def desactiver_compte(self, compte_id: uuid.UUID, *, auteur_id: uuid.UUID) -> None:
        compte = self._obtenir_ou_lever(compte_id)
        if not compte.actif:
            raise ValidationMetier("Ce compte est déjà désactivé.")
        compte.actif = False
        self.db.flush()
        self.journal_activite.enregistrer(
            module="comptabilite",
            type_action=TypeAction.ARCHIVER,
            utilisateur_id=auteur_id,
            type_objet="Compte",
            objet_id=compte.id,
            description=f"Désactivation du compte global {compte.numero}.",
            valeurs_avant={"actif": True},
            valeurs_apres={"actif": False},
        )

    def obtenir_compte(self, compte_id: uuid.UUID) -> Compte:
        return self._obtenir_ou_lever(compte_id)

    def lister_comptes(
        self,
        *,
        actifs_seulement: bool = True,
        recherche: str | None = None,
        classe: int | None = None,
        limite: int = 1000,
        decalage: int = 0,
    ) -> list[Compte]:
        return self.comptes.lister(
            actifs_seulement=actifs_seulement,
            recherche=recherche,
            classe=classe,
            limite=limite,
            decalage=decalage,
        )

    def _obtenir_ou_lever(self, compte_id: uuid.UUID) -> Compte:
        compte = self.comptes.obtenir(compte_id)
        if compte is None:
            raise RessourceIntrouvable("Compte introuvable dans le référentiel global.")
        return compte


class ServiceComptabilite:
    def __init__(self, db: Session, entreprise_id: uuid.UUID) -> None:
        self.db = db
        self.entreprise_id = entreprise_id
        self.comptes = RepositoryComptes(db, entreprise_id)
        self.comptes_globaux = RepositoryComptesGlobal(db)
        self.journaux = RepositoryJournaux(db, entreprise_id)
        self.ecritures = RepositoryEcritures(db, entreprise_id)
        self.lignes_ecriture = RepositoryLignesEcriture(db, entreprise_id)
        self.modeles = RepositoryModelesEcriture(db, entreprise_id)
        self.lignes_modele = RepositoryLignesModeleEcriture(db, entreprise_id)
        self.recurrentes = RepositoryEcrituresRecurrentes(db, entreprise_id)
        self.lignes_recurrentes = RepositoryLignesEcritureRecurrente(db, entreprise_id)
        self.exercices = RepositoryExercice(db, entreprise_id)
        self.tiers = RepositoryTiers(db, entreprise_id)
        self.entreprises = RepositoryEntreprises(db)
        self.journal_activite = ServiceJournalActivite(db)

    # --- Plan comptable (lecture + extensions) -----------------------------

    def lister_comptes(
        self,
        *,
        actifs_seulement: bool = True,
        recherche: str | None = None,
        classe: int | None = None,
        limite: int = 1000,
        decalage: int = 0,
    ) -> list[Compte]:
        """Le plan comptable applicable : comptes globaux + extensions de
        cette entreprise. `recherche` filtre sur le numéro OU le libellé
        (`ILIKE`, insensible à la casse), `classe` sur la classe SYSCOHADA
        exacte (1 à 8 — pas de validation de la borne ici, un filtre hors
        borne renvoie simplement une liste vide) — utilisés par l'écran de
        recherche du plan comptable ; `limite`/`decalage` en pagination
        simple (page suivante/précédente, pas de total — même choix que
        `journal_activite`). Les appelants qui veulent la liste complète
        (listes déroulantes de choix de compte ailleurs dans l'app)
        n'ont rien à changer : tous ces paramètres restent optionnels,
        avec les mêmes valeurs par défaut qu'avant."""
        return self.comptes.lister(
            actifs_seulement=actifs_seulement,
            recherche=recherche,
            classe=classe,
            limite=limite,
            decalage=decalage,
        )

    def lister_extensions(self, *, actifs_seulement: bool = True) -> list[Compte]:
        return self.comptes.lister_extensions(actifs_seulement=actifs_seulement)

    def lister_comptes_collectifs(self) -> list[Compte]:
        """Utilisé par le futur module `tiers` pour proposer les comptes
        collectifs éligibles (411, 401...)."""
        return self.comptes.lister_comptes_collectifs()

    def obtenir_compte(self, compte_id: uuid.UUID) -> Compte:
        return self._obtenir_compte_ou_lever(compte_id)

    def creer_extension_compte(
        self,
        *,
        auteur_id: uuid.UUID,
        numero: str,
        libelle: str,
        classe: int,
        lettrable: bool = False,
        est_collectif: bool = False,
        compte_parent_id: uuid.UUID | None = None,
    ) -> Compte:
        """Une extension propre à cette entreprise, en plus du référentiel
        partagé (cahier : le plan SYSCOHADA peut être étendu localement).
        `compte_parent_id` en fait, en plus, un sous-compte au sens strict
        (hiérarchie, voir models.py) — un parent global ou une extension
        de cette même entreprise, jamais d'une autre."""
        _valider_classe(classe)
        _valider_coherence_collectif(est_collectif=est_collectif, lettrable=lettrable)

        # Vérification portée par le service, pas par la base (voir la
        # note de models.py) : un numéro déjà pris globalement ne peut pas
        # être réutilisé comme extension.
        if self.comptes_globaux.obtenir_par_numero(numero) is not None:
            raise Conflit(f"Le compte {numero} existe déjà dans le référentiel global.")
        if self.comptes.obtenir_par_numero_extension(numero) is not None:
            raise Conflit(f"Le compte {numero} existe déjà pour cette entreprise.")
        parent = _valider_parent(self.comptes, compte_parent_id, numero=numero, classe=classe)

        compte = Compte(
            numero=numero,
            libelle=libelle,
            classe=classe,
            lettrable=lettrable,
            est_collectif=est_collectif,
            compte_parent_id=parent.id if parent else None,
        )
        self.comptes.ajouter(compte)
        self.journal_activite.enregistrer(
            module="comptabilite",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Compte",
            objet_id=compte.id,
            description=f"Création du sous-compte {numero} — {libelle}.",
            valeurs_apres={"numero": numero, "libelle": libelle, "classe": classe},
        )
        return compte

    def importer_comptes(
        self, *, auteur_id: uuid.UUID, contenu: bytes, nom_fichier: str
    ) -> ResultatImportComptes:
        """Import en masse d'un plan comptable (CSV ou Excel, deux
        colonnes : numéro, libellé — voir `import_utils.py`), comme autant
        d'extensions de cette entreprise. La classe est déduite du premier
        chiffre du numéro ; `lettrable`/`est_collectif` restent à `False`
        (absents du format d'import) et se corrigent ensuite compte par
        compte via `creer_extension_compte` si besoin — il n'existe pas de
        route de modification d'un compte existant (voir models.py).

        Une ligne invalide (numéro/libellé manquant, numéro hors 1-8, ou
        déjà pris) est ignorée et reportée, jamais fatale pour le reste du
        fichier. Les lignes sont traitées des numéros les plus courts aux
        plus longs, pour que le parent d'un compte soit toujours déjà créé
        — qu'il préexistait ou qu'il vienne d'être importé — au moment où
        on en a besoin (voir `_meilleur_parent`)."""
        lignes = analyser_fichier(contenu, nom_fichier)
        lignes_triees = sorted(lignes, key=lambda l: (len(l.numero), l.numero))

        comptes_connus: dict[str, Compte] = {
            c.numero: c for c in self.comptes.lister(actifs_seulement=False, limite=100_000)
        }
        comptes_crees: list[Compte] = []
        ignores: list[CompteImportIgnore] = []

        for ligne in lignes_triees:
            numero = ligne.numero.strip()
            libelle = ligne.libelle.strip()
            if not numero or not libelle:
                ignores.append(
                    CompteImportIgnore(numero=numero, libelle=libelle, raison="Numéro ou libellé manquant.")
                )
                continue
            if not numero[0].isdigit() or not (1 <= int(numero[0]) <= 8):
                ignores.append(
                    CompteImportIgnore(
                        numero=numero,
                        libelle=libelle,
                        raison="Le numéro doit commencer par un chiffre de 1 à 8 (classe SYSCOHADA).",
                    )
                )
                continue
            if numero in comptes_connus:
                ignores.append(
                    CompteImportIgnore(numero=numero, libelle=libelle, raison=f"Le compte {numero} existe déjà.")
                )
                continue

            classe = int(numero[0])
            parent = _meilleur_parent(comptes_connus, numero)
            compte = Compte(
                numero=numero,
                libelle=libelle,
                classe=classe,
                lettrable=False,
                est_collectif=False,
                compte_parent_id=parent.id if parent else None,
            )
            self.comptes.ajouter(compte)
            comptes_connus[numero] = compte
            comptes_crees.append(compte)

        self.journal_activite.enregistrer(
            module="comptabilite",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Compte",
            description=(
                f"Import du plan comptable depuis « {nom_fichier} » : "
                f"{len(comptes_crees)} compte(s) créé(s), {len(ignores)} ignoré(s)."
            ),
            valeurs_apres={"crees": len(comptes_crees), "ignores": len(ignores)},
        )
        return ResultatImportComptes(comptes_crees=comptes_crees, ignores=ignores)

    def importer_ecritures(
        self, *, auteur_id: uuid.UUID, contenu: bytes, nom_fichier: str
    ) -> ResultatImportEcritures:
        """Import en masse d'écritures (CSV ou Excel — format exact :
        journal, date, pièce, compte, libellé, débit, crédit par ligne,
        voir `import_utils.py`). Les lignes qui partagent le même triplet
        (journal, date, pièce) forment une écriture ; l'exercice se
        résout automatiquement depuis la date (`obtenir_pour_date`), pas
        de colonne dédiée. Chaque groupe est délégué à `creer_ecriture`,
        qui réapplique tous ses contrôles habituels (exercice ouvert,
        compte actif, équilibre débit/crédit...) — un groupe invalide est
        ignoré et reporté, jamais fatal pour le reste du fichier, même
        philosophie que `importer_comptes`."""
        lignes = analyser_fichier_ecritures(contenu, nom_fichier)

        groupes: dict[tuple[str, str, str], list] = {}
        for ligne in lignes:
            cle = (ligne.journal.strip().upper(), ligne.date.strip(), ligne.piece.strip())
            groupes.setdefault(cle, []).append(ligne)

        comptes_connus = {
            c.numero: c for c in self.comptes.lister(actifs_seulement=False, limite=100_000)
        }
        journaux_connus = {j.code.upper(): j for j in self.journaux.lister()}

        ecritures_creees: list[Ecriture] = []
        ignorees: list[EcritureImportIgnoree] = []

        for (code_journal, date_brute, piece), lignes_groupe in groupes.items():
            try:
                if not piece:
                    raise ValidationMetier(
                        "Pièce manquante (sert à regrouper les lignes d'une même écriture)."
                    )
                journal = journaux_connus.get(code_journal)
                if journal is None:
                    raise ValidationMetier(f"Journal '{code_journal}' introuvable pour cette entreprise.")
                if not journal.actif:
                    raise ValidationMetier(f"Le journal '{code_journal}' est désactivé.")
                try:
                    date_ecriture = date.fromisoformat(date_brute)
                except ValueError:
                    raise ValidationMetier(f"Date invalide : '{date_brute}' (attendu AAAA-MM-JJ).")
                exercice = self.exercices.obtenir_pour_date(date_ecriture)
                if exercice is None:
                    raise ValidationMetier(f"Aucun exercice ne couvre la date {date_brute}.")

                lignes_saisies: list[LigneSaisie] = []
                libelle_ecriture: str | None = None
                for ligne in lignes_groupe:
                    numero = ligne.compte.strip()
                    compte = comptes_connus.get(numero)
                    if compte is None:
                        raise ValidationMetier(f"Compte '{numero}' introuvable.")
                    libelle_ligne = ligne.libelle.strip() or None
                    if libelle_ecriture is None and libelle_ligne:
                        libelle_ecriture = libelle_ligne
                    lignes_saisies.append(
                        LigneSaisie(
                            compte_id=compte.id,
                            debit=_decimal_importee(ligne.debit),
                            credit=_decimal_importee(ligne.credit),
                            libelle=libelle_ligne,
                        )
                    )

                ecriture = self.creer_ecriture(
                    auteur_id=auteur_id,
                    journal_id=journal.id,
                    exercice_id=exercice.id,
                    date_ecriture=date_ecriture,
                    libelle=libelle_ecriture or piece,
                    reference_piece=piece,
                    lignes=lignes_saisies,
                )
                ecritures_creees.append(ecriture)
            except (ValidationMetier, RessourceIntrouvable) as erreur:
                ignorees.append(
                    EcritureImportIgnoree(
                        journal=code_journal, date=date_brute, piece=piece, raison=str(erreur)
                    )
                )

        self.journal_activite.enregistrer(
            module="comptabilite",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Ecriture",
            description=(
                f"Import d'écritures depuis « {nom_fichier} » : "
                f"{len(ecritures_creees)} écriture(s) créée(s), {len(ignorees)} ignorée(s)."
            ),
            valeurs_apres={"creees": len(ecritures_creees), "ignorees": len(ignorees)},
        )
        return ResultatImportEcritures(ecritures_creees=ecritures_creees, ignorees=ignorees)

    def desactiver_extension_compte(self, compte_id: uuid.UUID, *, auteur_id: uuid.UUID) -> None:
        """Ne peut désactiver qu'une extension de CETTE entreprise, jamais
        un compte du référentiel global (voir `_obtenir_extension_ou_lever`)."""
        compte = self._obtenir_extension_ou_lever(compte_id)
        if not compte.actif:
            raise ValidationMetier("Ce compte est déjà désactivé.")
        compte.actif = False
        self.db.flush()
        self.journal_activite.enregistrer(
            module="comptabilite",
            type_action=TypeAction.ARCHIVER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Compte",
            objet_id=compte.id,
            description=f"Désactivation du sous-compte {compte.numero}.",
            valeurs_avant={"actif": True},
            valeurs_apres={"actif": False},
        )

    # --- Journaux ------------------------------------------------------------

    def creer_journal(
        self,
        *,
        auteur_id: uuid.UUID,
        code: str,
        libelle: str,
        type_journal: TypeJournal,
    ) -> Journal:
        if self.journaux.obtenir_par_code(code) is not None:
            raise Conflit(f"Le journal {code} existe déjà pour cette entreprise.")

        journal = Journal(code=code, libelle=libelle, type_journal=type_journal.value)
        self.journaux.ajouter(journal)
        self.journal_activite.enregistrer(
            module="comptabilite",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Journal",
            objet_id=journal.id,
            description=f"Création du journal {code} — {libelle}.",
            valeurs_apres={"code": code, "libelle": libelle, "type_journal": type_journal.value},
        )
        return journal

    def desactiver_journal(self, journal_id: uuid.UUID, *, auteur_id: uuid.UUID) -> None:
        journal = self._obtenir_journal_ou_lever(journal_id)
        if not journal.actif:
            raise ValidationMetier("Ce journal est déjà désactivé.")
        journal.actif = False
        self.db.flush()
        self.journal_activite.enregistrer(
            module="comptabilite",
            type_action=TypeAction.ARCHIVER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Journal",
            objet_id=journal.id,
            description=f"Désactivation du journal {journal.code}.",
            valeurs_avant={"actif": True},
            valeurs_apres={"actif": False},
        )

    def obtenir_journal(self, journal_id: uuid.UUID) -> Journal:
        return self._obtenir_journal_ou_lever(journal_id)

    def lister_journaux(self, *, actifs_seulement: bool = True) -> list[Journal]:
        journaux = self.journaux.lister()
        if actifs_seulement:
            journaux = [j for j in journaux if j.actif]
        return journaux

    # --- Écritures : création et modification (brouillon uniquement) -------

    # --- Modèles d'écriture (saisie par modèle) -----------------------------

    def creer_modele(
        self,
        *,
        auteur_id: uuid.UUID,
        code: str,
        libelle: str,
        journal_id: uuid.UUID,
        lignes: list[LigneModeleSaisie],
    ) -> ModeleEcriture:
        self._obtenir_journal_ou_lever(journal_id)
        if self.modeles.obtenir_par_code(code) is not None:
            raise Conflit(f"Le modèle {code} existe déjà pour cette entreprise.")
        self._valider_lignes_modele(lignes)

        modele = ModeleEcriture(code=code, libelle=libelle, journal_id=journal_id)
        self.modeles.ajouter(modele)
        self._remplacer_lignes_modele(modele.id, lignes)

        self.journal_activite.enregistrer(
            module="comptabilite",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="ModeleEcriture",
            objet_id=modele.id,
            description=f"Création du modèle d'écriture '{code}'.",
            valeurs_apres={"code": code, "libelle": libelle},
        )
        return modele

    def modifier_modele(
        self,
        modele_id: uuid.UUID,
        *,
        auteur_id: uuid.UUID,
        code: str | None = None,
        libelle: str | None = None,
        journal_id: uuid.UUID | None = None,
        actif: bool | None = None,
        lignes: list[LigneModeleSaisie] | None = None,
    ) -> ModeleEcriture:
        modele = self._obtenir_modele_ou_lever(modele_id)

        if code is not None and code != modele.code:
            if self.modeles.obtenir_par_code(code) is not None:
                raise Conflit(f"Le modèle {code} existe déjà pour cette entreprise.")
            modele.code = code
        if libelle is not None:
            modele.libelle = libelle
        if journal_id is not None:
            self._obtenir_journal_ou_lever(journal_id)
            modele.journal_id = journal_id
        if actif is not None:
            modele.actif = actif
        if lignes is not None:
            self._valider_lignes_modele(lignes)
            self.lignes_modele.supprimer_pour_modele(modele_id)
            self._remplacer_lignes_modele(modele_id, lignes)
        self.db.flush()

        self.journal_activite.enregistrer(
            module="comptabilite",
            type_action=TypeAction.MODIFIER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="ModeleEcriture",
            objet_id=modele.id,
            description=f"Modification du modèle d'écriture '{modele.code}'.",
        )
        return modele

    def obtenir_modele(self, modele_id: uuid.UUID) -> ModeleEcriture:
        return self._obtenir_modele_ou_lever(modele_id)

    def lister_modeles(self, *, actifs_seulement: bool = True) -> list[ModeleEcriture]:
        return self.modeles.lister(actifs_seulement=actifs_seulement)

    def lister_lignes_modele(self, modele_id: uuid.UUID) -> list[LigneModeleEcriture]:
        return self.lignes_modele.lister_pour_modele(modele_id)

    def appliquer_modele(
        self,
        modele_id: uuid.UUID,
        *,
        auteur_id: uuid.UUID,
        exercice_id: uuid.UUID,
        date_ecriture: date,
        libelle: str | None = None,
        reference_piece: str | None = None,
        montants: list[MontantLigneModele],
    ) -> Ecriture:
        """Génère une écriture brouillon à partir d'un modèle : le compte
        et le sens de chaque ligne viennent du modèle, seul le montant est
        fourni ici. Réutilise `creer_ecriture` (donc tous ses contrôles :
        exercice ouvert, compte actif, équilibre débit/crédit...) plutôt
        que de dupliquer la logique de création."""
        modele = self._obtenir_modele_ou_lever(modele_id)
        if not modele.actif:
            raise ValidationMetier(f"Le modèle {modele.code} est désactivé.")

        lignes_modele = self.lignes_modele.lister_pour_modele(modele_id)
        montants_par_ligne = {m.ligne_modele_id: m.montant for m in montants}

        lignes: list[LigneSaisie] = []
        for ligne_modele in lignes_modele:
            montant = montants_par_ligne.get(ligne_modele.id)
            if montant is None or montant == 0:
                continue
            if montant < 0:
                raise ValidationMetier("Le montant d'une ligne de modèle ne peut pas être négatif.")
            if ligne_modele.sens == "debit":
                lignes.append(
                    LigneSaisie(compte_id=ligne_modele.compte_id, debit=montant, libelle=ligne_modele.libelle)
                )
            else:
                lignes.append(
                    LigneSaisie(compte_id=ligne_modele.compte_id, credit=montant, libelle=ligne_modele.libelle)
                )

        if len(lignes) < 2:
            raise ValidationMetier(
                "Au moins deux lignes avec un montant renseigné sont nécessaires pour "
                "appliquer ce modèle."
            )

        return self.creer_ecriture(
            auteur_id=auteur_id,
            journal_id=modele.journal_id,
            exercice_id=exercice_id,
            date_ecriture=date_ecriture,
            libelle=libelle or modele.libelle,
            reference_piece=reference_piece,
            lignes=lignes,
        )

    def _valider_lignes_modele(self, lignes: list[LigneModeleSaisie]) -> None:
        if len(lignes) < 2:
            raise ValidationMetier("Un modèle doit avoir au moins deux lignes.")
        for ligne in lignes:
            if ligne.sens not in ("debit", "credit"):
                raise ValidationMetier("Le sens d'une ligne de modèle doit être 'debit' ou 'credit'.")
            compte = self._obtenir_compte_ou_lever(ligne.compte_id)
            if not compte.actif:
                raise ValidationMetier(f"Le compte {compte.numero} est désactivé.")

    def _remplacer_lignes_modele(self, modele_id: uuid.UUID, lignes: list[LigneModeleSaisie]) -> None:
        for ligne in lignes:
            self.lignes_modele.ajouter(
                LigneModeleEcriture(
                    modele_id=modele_id,
                    compte_id=ligne.compte_id,
                    sens=ligne.sens,
                    libelle=ligne.libelle,
                )
            )

    def _obtenir_modele_ou_lever(self, modele_id: uuid.UUID) -> ModeleEcriture:
        modele = self.modeles.obtenir(modele_id)
        if modele is None:
            raise RessourceIntrouvable("Modèle d'écriture introuvable.")
        return modele

    # --- Écritures récurrentes (cahier, section 8.4) -------------------------

    def creer_ecriture_recurrente(
        self,
        *,
        auteur_id: uuid.UUID,
        code: str,
        libelle: str,
        journal_id: uuid.UUID,
        periodicite: PeriodiciteRecurrence,
        date_debut: date,
        date_fin: date | None = None,
        reference_piece: str | None = None,
        lignes: list[LigneEcritureRecurrenteSaisie],
    ) -> EcritureRecurrente:
        self._obtenir_journal_ou_lever(journal_id)
        if self.recurrentes.obtenir_par_code(code) is not None:
            raise Conflit(f"L'écriture récurrente {code} existe déjà pour cette entreprise.")
        if date_fin is not None and date_fin < date_debut:
            raise ValidationMetier("La date de fin ne peut pas être antérieure à la date de début.")
        self._valider_lignes_recurrentes(lignes)

        recurrente = EcritureRecurrente(
            code=code,
            libelle=libelle,
            journal_id=journal_id,
            periodicite=periodicite.value,
            reference_piece=reference_piece,
            date_debut=date_debut,
            date_fin=date_fin,
            prochaine_echeance=date_debut,
        )
        self.recurrentes.ajouter(recurrente)
        self._remplacer_lignes_recurrentes(recurrente.id, lignes)

        self.journal_activite.enregistrer(
            module="comptabilite",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="EcritureRecurrente",
            objet_id=recurrente.id,
            description=f"Création de l'écriture récurrente '{code}'.",
            valeurs_apres={"code": code, "libelle": libelle, "periodicite": periodicite.value},
        )
        return recurrente

    def modifier_ecriture_recurrente(
        self,
        ecriture_recurrente_id: uuid.UUID,
        *,
        auteur_id: uuid.UUID,
        code: str | None = None,
        libelle: str | None = None,
        journal_id: uuid.UUID | None = None,
        periodicite: PeriodiciteRecurrence | None = None,
        date_fin: date | None = None,
        reference_piece: str | None = None,
        actif: bool | None = None,
        lignes: list[LigneEcritureRecurrenteSaisie] | None = None,
    ) -> EcritureRecurrente:
        """Mise à jour partielle. `date_debut` n'est volontairement pas
        modifiable ici (voir la note de `EcritureRecurrente` dans
        models.py) : une récurrence qui a déjà pu générer des occurrences
        ne doit pas pouvoir revenir dans le passé — seule `prochaine_
        echeance` avance, via `generer_echeances`."""
        recurrente = self._obtenir_ecriture_recurrente_ou_lever(ecriture_recurrente_id)

        if code is not None and code != recurrente.code:
            if self.recurrentes.obtenir_par_code(code) is not None:
                raise Conflit(f"L'écriture récurrente {code} existe déjà pour cette entreprise.")
            recurrente.code = code
        if libelle is not None:
            recurrente.libelle = libelle
        if journal_id is not None:
            self._obtenir_journal_ou_lever(journal_id)
            recurrente.journal_id = journal_id
        if periodicite is not None:
            recurrente.periodicite = periodicite.value
        if reference_piece is not None:
            recurrente.reference_piece = reference_piece
        if date_fin is not None:
            if date_fin < recurrente.date_debut:
                raise ValidationMetier(
                    "La date de fin ne peut pas être antérieure à la date de début."
                )
            recurrente.date_fin = date_fin
        if actif is not None:
            recurrente.actif = actif
        if lignes is not None:
            self._valider_lignes_recurrentes(lignes)
            self.lignes_recurrentes.supprimer_pour_ecriture_recurrente(ecriture_recurrente_id)
            self._remplacer_lignes_recurrentes(ecriture_recurrente_id, lignes)
        self.db.flush()

        self.journal_activite.enregistrer(
            module="comptabilite",
            type_action=TypeAction.MODIFIER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="EcritureRecurrente",
            objet_id=recurrente.id,
            description=f"Modification de l'écriture récurrente '{recurrente.code}'.",
        )
        return recurrente

    def obtenir_ecriture_recurrente(self, ecriture_recurrente_id: uuid.UUID) -> EcritureRecurrente:
        return self._obtenir_ecriture_recurrente_ou_lever(ecriture_recurrente_id)

    def lister_ecritures_recurrentes(self, *, actifs_seulement: bool = True) -> list[EcritureRecurrente]:
        return self.recurrentes.lister(actifs_seulement=actifs_seulement)

    def lister_lignes_ecriture_recurrente(
        self, ecriture_recurrente_id: uuid.UUID
    ) -> list[LigneEcritureRecurrente]:
        return self.lignes_recurrentes.lister_pour_ecriture_recurrente(ecriture_recurrente_id)

    def generer_echeances(
        self,
        ecriture_recurrente_id: uuid.UUID,
        *,
        auteur_id: uuid.UUID,
        jusquau: date,
    ) -> ResultatGenerationEcheances:
        """Génère une occurrence brouillon par échéance due (`prochaine_
        echeance <= jusquau`), en réutilisant `creer_ecriture` pour chacune
        (donc tous ses contrôles : exercice ouvert, compte actif,
        équilibre...) — même principe de délégation qu'`appliquer_modele`.

        `prochaine_echeance` avance à CHAQUE passage, succès ou échec : une
        échéance qui tombe sur un exercice clôturé (par exemple) ne doit
        jamais bloquer indéfiniment les échéances suivantes — elle est
        seulement reportée dans `ignorees`, jamais retentée automatiquement
        (même philosophie que `importer_ecritures`). Un garde-fou borne le
        nombre d'itérations pour ne jamais boucler indéfiniment sur une
        récurrence mal configurée (périodicité incohérente, `jusquau` très
        éloigné)."""
        recurrente = self._obtenir_ecriture_recurrente_ou_lever(ecriture_recurrente_id)
        if not recurrente.actif:
            raise ValidationMetier(f"L'écriture récurrente {recurrente.code} est désactivée.")

        lignes_recurrence = self.lignes_recurrentes.lister_pour_ecriture_recurrente(ecriture_recurrente_id)
        if len(lignes_recurrence) < 2:
            raise ValidationMetier(
                "L'écriture récurrente doit comporter au moins deux lignes pour générer "
                "une occurrence."
            )

        resultat = ResultatGenerationEcheances()
        iterations = 0
        while (
            recurrente.prochaine_echeance <= jusquau
            and (recurrente.date_fin is None or recurrente.prochaine_echeance <= recurrente.date_fin)
            and iterations < 500
        ):
            iterations += 1
            date_echeance = recurrente.prochaine_echeance
            try:
                exercice = self.exercices.obtenir_pour_date(date_echeance)
                if exercice is None:
                    raise ValidationMetier(f"Aucun exercice ne couvre la date {date_echeance}.")

                lignes_saisies = [
                    LigneSaisie(
                        compte_id=ligne.compte_id,
                        debit=ligne.montant if ligne.sens == "debit" else Decimal("0"),
                        credit=ligne.montant if ligne.sens == "credit" else Decimal("0"),
                        libelle=ligne.libelle,
                    )
                    for ligne in lignes_recurrence
                ]
                ecriture = self.creer_ecriture(
                    auteur_id=auteur_id,
                    journal_id=recurrente.journal_id,
                    exercice_id=exercice.id,
                    date_ecriture=date_echeance,
                    libelle=recurrente.libelle,
                    reference_piece=recurrente.reference_piece,
                    lignes=lignes_saisies,
                )
                resultat.ecritures_creees.append(ecriture)
            except (ValidationMetier, RessourceIntrouvable) as erreur:
                resultat.ignorees.append(EcheanceIgnoree(date_echeance=date_echeance, raison=str(erreur)))
            finally:
                # Avance toujours, même en cas d'échec — voir la docstring.
                # L'ancre reste `date_debut.day` (jamais le jour de la
                # dernière occurrence, voir `_ajouter_mois`), pour ne
                # jamais dériver définitivement vers un jour plus petit
                # après un mois court.
                recurrente.prochaine_echeance = _prochaine_echeance(
                    date_echeance, recurrente.periodicite, jour_ancre=recurrente.date_debut.day
                )

        self.db.flush()
        self.journal_activite.enregistrer(
            module="comptabilite",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="EcritureRecurrente",
            objet_id=recurrente.id,
            description=(
                f"Génération des échéances de '{recurrente.code}' jusqu'au {jusquau} : "
                f"{len(resultat.ecritures_creees)} écriture(s) créée(s), "
                f"{len(resultat.ignorees)} ignorée(s)."
            ),
            valeurs_apres={
                "creees": len(resultat.ecritures_creees),
                "ignorees": len(resultat.ignorees),
            },
        )
        return resultat

    def _valider_lignes_recurrentes(self, lignes: list[LigneEcritureRecurrenteSaisie]) -> None:
        if len(lignes) < 2:
            raise ValidationMetier("Une écriture récurrente doit avoir au moins deux lignes.")
        for ligne in lignes:
            if ligne.sens not in ("debit", "credit"):
                raise ValidationMetier("Le sens d'une ligne récurrente doit être 'debit' ou 'credit'.")
            if ligne.montant <= 0:
                raise ValidationMetier("Le montant d'une ligne récurrente doit être strictement positif.")
            compte = self._obtenir_compte_ou_lever(ligne.compte_id)
            if not compte.actif:
                raise ValidationMetier(f"Le compte {compte.numero} est désactivé.")
        total_debit = sum((l.montant for l in lignes if l.sens == "debit"), Decimal("0"))
        total_credit = sum((l.montant for l in lignes if l.sens == "credit"), Decimal("0"))
        if total_debit != total_credit:
            raise ValidationMetier(
                "L'écriture récurrente n'est pas équilibrée : total débit "
                f"{total_debit} ≠ total crédit {total_credit}."
            )

    def _remplacer_lignes_recurrentes(
        self, ecriture_recurrente_id: uuid.UUID, lignes: list[LigneEcritureRecurrenteSaisie]
    ) -> None:
        for ligne in lignes:
            self.lignes_recurrentes.ajouter(
                LigneEcritureRecurrente(
                    ecriture_recurrente_id=ecriture_recurrente_id,
                    compte_id=ligne.compte_id,
                    sens=ligne.sens,
                    montant=ligne.montant,
                    libelle=ligne.libelle,
                )
            )

    def _obtenir_ecriture_recurrente_ou_lever(
        self, ecriture_recurrente_id: uuid.UUID
    ) -> EcritureRecurrente:
        recurrente = self.recurrentes.obtenir(ecriture_recurrente_id)
        if recurrente is None:
            raise RessourceIntrouvable("Écriture récurrente introuvable.")
        return recurrente

    # --- Écritures ------------------------------------------------------------

    def creer_ecriture(
        self,
        *,
        auteur_id: uuid.UUID,
        journal_id: uuid.UUID,
        exercice_id: uuid.UUID,
        date_ecriture: date,
        libelle: str,
        lignes: list[LigneSaisie],
        reference_piece: str | None = None,
    ) -> Ecriture:
        journal = self._obtenir_journal_ou_lever(journal_id)
        if not journal.actif:
            raise ValidationMetier("Ce journal est désactivé.")
        exercice = self._obtenir_exercice_ou_lever(exercice_id)
        self._verifier_exercice_ouvert(exercice)
        self._verifier_date_dans_exercice(date_ecriture, exercice)
        self._valider_lignes(lignes)

        ecriture = Ecriture(
            journal_id=journal_id,
            exercice_id=exercice_id,
            date_ecriture=date_ecriture,
            libelle=libelle,
            reference_piece=reference_piece,
            statut=StatutEcriture.BROUILLON.value,
        )
        self.ecritures.ajouter(ecriture)
        self._remplacer_lignes(ecriture.id, lignes, date_ecriture=date_ecriture)

        self.journal_activite.enregistrer(
            module="comptabilite",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Ecriture",
            objet_id=ecriture.id,
            description=f"Création de l'écriture '{libelle}' (brouillon).",
            valeurs_apres={"journal_id": str(journal_id), "libelle": libelle},
        )
        return ecriture

    def creer_ecriture_validee(
        self,
        *,
        auteur_id: uuid.UUID,
        journal_id: uuid.UUID,
        date_ecriture: date,
        libelle: str,
        lignes: list[LigneSaisie],
        exercice_id: uuid.UUID | None = None,
        reference_piece: str | None = None,
    ) -> Ecriture:
        """Saisie manuelle « en une étape » : crée l'écriture ET la valide
        immédiatement (plus d'étape brouillon pour l'utilisateur).

        - `exercice_id` est facultatif : à défaut, l'exercice qui couvre
          `date_ecriture` est retrouvé automatiquement (même règle que
          l'import d'écritures).
        - Une ligne sans libellé reprend celui de l'écriture, pour que le
          libellé soit uniforme sur toutes les lignes.
        - Le numéro de pièce est attribué par le logiciel (numéro
          séquentiel de la validation) ; il remplace `reference_piece`
          seulement si l'utilisateur n'en a pas fourni.

        Réservé à la saisie manuelle : l'import, les modèles, les
        récurrentes et la duplication continuent d'utiliser `creer_ecriture`
        (brouillon) — leur comportement ne change pas."""
        if exercice_id is None:
            exercice = self.exercices.obtenir_pour_date(date_ecriture)
            if exercice is None:
                raise ValidationMetier(
                    f"Aucun exercice ne couvre la date {date_ecriture.isoformat()}."
                )
            exercice_id = exercice.id

        lignes_uniformes = [
            LigneSaisie(
                compte_id=ligne.compte_id,
                debit=ligne.debit,
                credit=ligne.credit,
                tiers_id=ligne.tiers_id,
                libelle=ligne.libelle or libelle,
                date_echeance=ligne.date_echeance,
            )
            for ligne in lignes
        ]
        ecriture = self.creer_ecriture(
            auteur_id=auteur_id,
            journal_id=journal_id,
            exercice_id=exercice_id,
            date_ecriture=date_ecriture,
            libelle=libelle,
            lignes=lignes_uniformes,
            reference_piece=reference_piece,
        )
        ecriture = self.valider_ecriture(ecriture.id, auteur_id=auteur_id)
        if not ecriture.reference_piece:
            ecriture.reference_piece = ecriture.numero
            self.db.flush()
        return ecriture

    def modifier_ecriture(
        self,
        ecriture_id: uuid.UUID,
        *,
        auteur_id: uuid.UUID,
        date_ecriture: date | None = None,
        libelle: str | None = None,
        reference_piece: str | None = None,
        lignes: list[LigneSaisie] | None = None,
    ) -> Ecriture:
        ecriture = self._obtenir_ecriture_ou_lever(ecriture_id)
        self._verifier_brouillon(ecriture)

        if date_ecriture is not None or lignes is not None:
            exercice = self._obtenir_exercice_ou_lever(ecriture.exercice_id)
            self._verifier_date_dans_exercice(date_ecriture or ecriture.date_ecriture, exercice)
        if lignes is not None:
            self._valider_lignes(lignes)

        if date_ecriture is not None:
            ecriture.date_ecriture = date_ecriture
        if libelle is not None:
            ecriture.libelle = libelle
        if reference_piece is not None:
            ecriture.reference_piece = reference_piece
        if lignes is not None:
            self.lignes_ecriture.supprimer_pour_ecriture(ecriture_id)
            self._remplacer_lignes(ecriture_id, lignes, date_ecriture=ecriture.date_ecriture)
        self.db.flush()

        self.journal_activite.enregistrer(
            module="comptabilite",
            type_action=TypeAction.MODIFIER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Ecriture",
            objet_id=ecriture.id,
            description=f"Modification de l'écriture '{ecriture.libelle}' (brouillon).",
        )
        return ecriture

    def supprimer_ecriture(self, ecriture_id: uuid.UUID, *, auteur_id: uuid.UUID) -> None:
        ecriture = self._obtenir_ecriture_ou_lever(ecriture_id)
        self._verifier_brouillon(ecriture)
        self.db.delete(ecriture)  # les lignes suivent par ondelete=CASCADE
        self.db.flush()
        self.journal_activite.enregistrer(
            module="comptabilite",
            type_action=TypeAction.SUPPRIMER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Ecriture",
            objet_id=ecriture_id,
            description="Suppression d'une écriture en brouillon.",
        )

    # --- À-nouveaux (cahier, section 7.2) -----------------------------------

    CODE_JOURNAL_A_NOUVEAUX = "AN"
    # Seuls les comptes de bilan se reportent — les comptes de gestion
    # (classes 6/7) sont soldés par la clôture, jamais reportés : ouvrir
    # l'exercice N avec un solde de charges/produits de N-1 n'aurait pas
    # de sens comptable.
    CLASSES_BILAN = (1, 2, 3, 4, 5)

    def generer_a_nouveaux(self, exercice_id: uuid.UUID, *, auteur_id: uuid.UUID) -> Ecriture:
        """Crée et valide une écriture qui reporte, compte par compte, le
        solde de clôture des comptes de bilan de l'exercice précédent vers
        l'exercice `exercice_id` — dans un journal dédié ('AN'), créé à la
        demande s'il n'existe pas encore.

        Refuse si l'exercice précédent n'est pas défini ou pas clôturé
        (rien à reporter de façon fiable), et si les à-nouveaux de cet
        exercice ont déjà été générés (pas de double report silencieux :
        l'appelant doit explicitement supprimer l'écriture existante —
        via `supprimer_ecriture`, tant qu'elle est en brouillon — avant
        d'en regénérer une, mais ici elle est validée directement, donc
        passerait par une extourne)."""
        exercice = self._obtenir_exercice_ou_lever(exercice_id)
        if exercice.exercice_precedent_id is None:
            raise ValidationMetier("Cet exercice n'a pas d'exercice précédent défini.")
        precedent = self._obtenir_exercice_ou_lever(exercice.exercice_precedent_id)
        if precedent.statut != StatutExercice.CLOTURE.value:
            raise ValidationMetier(
                "L'exercice précédent doit être clôturé avant de générer les à-nouveaux."
            )

        journal = self.journaux.obtenir_par_code(self.CODE_JOURNAL_A_NOUVEAUX)
        if journal is None:
            journal = Journal(
                code=self.CODE_JOURNAL_A_NOUVEAUX,
                libelle="À-nouveaux",
                type_journal=TypeJournal.A_NOUVEAUX.value,
            )
            self.journaux.ajouter(journal)

        deja_generees = self.ecritures.lister(journal_id=journal.id, exercice_id=exercice_id, limite=1)
        if deja_generees:
            raise Conflit("Les à-nouveaux de cet exercice ont déjà été générés.")

        reporting = RepositoryReporting(self.db, self.entreprise_id)
        lignes: list[LigneSaisie] = []
        for compte_id, _numero, _libelle, total_debit, total_credit in reporting.totaux_par_compte(
            precedent.id
        ):
            compte = self.comptes.obtenir(compte_id)
            if compte is None or compte.classe not in self.CLASSES_BILAN:
                continue
            solde = total_debit - total_credit
            if solde == 0:
                continue
            if solde > 0:
                lignes.append(LigneSaisie(compte_id=compte_id, debit=solde, libelle="À-nouveau"))
            else:
                lignes.append(LigneSaisie(compte_id=compte_id, credit=-solde, libelle="À-nouveau"))

        if len(lignes) < 2:
            raise ValidationMetier(
                "Aucun solde de bilan à reporter depuis l'exercice précédent."
            )

        ecriture = self.creer_ecriture(
            auteur_id=auteur_id,
            journal_id=journal.id,
            exercice_id=exercice_id,
            date_ecriture=exercice.date_debut,
            libelle=f"À-nouveaux — report de l'exercice {precedent.date_debut.year}",
            lignes=lignes,
        )
        return self.valider_ecriture(ecriture.id, auteur_id=auteur_id)

    # --- Écritures : validation, immuabilité, extourne ----------------------

    def valider_ecriture(self, ecriture_id: uuid.UUID, *, auteur_id: uuid.UUID) -> Ecriture:
        ecriture = self._obtenir_ecriture_ou_lever(ecriture_id)
        if ecriture.statut == StatutEcriture.VALIDEE.value:
            raise ValidationMetier("Cette écriture est déjà validée.")

        lignes = self.lignes_ecriture.lister_pour_ecriture(ecriture.id)
        self._verifier_equilibre(lignes)

        exercice = self._obtenir_exercice_ou_lever(ecriture.exercice_id)
        self._verifier_exercice_ouvert(exercice)
        journal = self._obtenir_journal_ou_lever(ecriture.journal_id)

        # Voir la note de tête de fichier sur la limite de concurrence de
        # ce calcul de numéro.
        compteur = self.ecritures.compter_validees(
            journal_id=ecriture.journal_id, exercice_id=ecriture.exercice_id
        )
        numero = f"{journal.code}-{exercice.date_debut.year}-{compteur + 1:05d}"

        ecriture.statut = StatutEcriture.VALIDEE.value
        ecriture.numero = numero
        self.db.flush()
        self.journal_activite.enregistrer(
            module="comptabilite",
            type_action=TypeAction.VALIDER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Ecriture",
            objet_id=ecriture.id,
            description=f"Validation de l'écriture {numero}.",
            valeurs_avant={"statut": StatutEcriture.BROUILLON.value},
            valeurs_apres={"statut": StatutEcriture.VALIDEE.value, "numero": numero},
        )
        return ecriture

    def dupliquer_ecriture(
        self,
        ecriture_id: uuid.UUID,
        *,
        auteur_id: uuid.UUID,
        date_ecriture: date,
        exercice_id: uuid.UUID | None = None,
        libelle: str | None = None,
    ) -> Ecriture:
        """Copie les lignes d'une écriture (brouillon ou validée) vers une
        NOUVELLE écriture en brouillon, sur le même journal — l'originale
        n'est jamais modifiée. "Contrôlée" : pas une copie aveugle, cette
        méthode ne fait que rassembler les lignes d'origine et délègue
        ensuite à `creer_ecriture`, qui réapplique TOUS ses contrôles sur
        la cible (exercice ouvert, date dans l'exercice, compte toujours
        actif, équilibre) — une duplication peut donc être refusée si,
        par exemple, un compte utilisé a été désactivé depuis, ou si
        l'exercice cible est clôturé.

        `exercice_id` est optionnel : par défaut, le même exercice que
        l'originale ; le fournir permet de dupliquer vers un autre
        exercice (utile en tout début de nouvel exercice, en attendant
        les écritures récurrentes — cahier, section 8.3)."""
        originale = self._obtenir_ecriture_ou_lever(ecriture_id)
        lignes_originales = self.lignes_ecriture.lister_pour_ecriture(originale.id)
        lignes = [
            LigneSaisie(
                compte_id=ligne.compte_id,
                debit=ligne.debit,
                credit=ligne.credit,
                tiers_id=ligne.tiers_id,
                libelle=ligne.libelle,
            )
            for ligne in lignes_originales
        ]
        return self.creer_ecriture(
            auteur_id=auteur_id,
            journal_id=originale.journal_id,
            exercice_id=exercice_id or originale.exercice_id,
            date_ecriture=date_ecriture,
            libelle=libelle or f"Copie de « {originale.libelle} »",
            reference_piece=originale.reference_piece,
            lignes=lignes,
        )

    def extourner_ecriture(
        self,
        ecriture_id: uuid.UUID,
        *,
        auteur_id: uuid.UUID,
        date_ecriture: date,
        libelle: str | None = None,
    ) -> Ecriture:
        """Crée une NOUVELLE écriture en brouillon, lignes inversées,
        référençant l'originale via `ecriture_extournee_id` — l'originale
        elle-même n'est jamais modifiée (voir models.py). La nouvelle
        écriture doit ensuite être validée séparément, comme toute
        écriture (voir `valider_ecriture`)."""
        originale = self._obtenir_ecriture_ou_lever(ecriture_id)
        if originale.statut != StatutEcriture.VALIDEE.value:
            raise ValidationMetier(
                "Seule une écriture validée peut être extournée ; une écriture en "
                "brouillon se modifie ou se supprime directement."
            )

        exercice = self._obtenir_exercice_ou_lever(originale.exercice_id)
        self._verifier_date_dans_exercice(date_ecriture, exercice)

        lignes_originales = self.lignes_ecriture.lister_pour_ecriture(originale.id)
        nouvelle = Ecriture(
            journal_id=originale.journal_id,
            exercice_id=originale.exercice_id,
            date_ecriture=date_ecriture,
            libelle=libelle or f"Extourne de l'écriture {originale.numero}",
            reference_piece=originale.reference_piece,
            statut=StatutEcriture.BROUILLON.value,
            ecriture_extournee_id=originale.id,
        )
        self.ecritures.ajouter(nouvelle)
        for ligne in lignes_originales:
            self.lignes_ecriture.ajouter(
                LigneEcriture(
                    ecriture_id=nouvelle.id,
                    compte_id=ligne.compte_id,
                    tiers_id=ligne.tiers_id,
                    libelle=ligne.libelle,
                    debit=ligne.credit,
                    credit=ligne.debit,
                )
            )

        self.journal_activite.enregistrer(
            module="comptabilite",
            type_action=TypeAction.ANNULER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Ecriture",
            objet_id=nouvelle.id,
            description=f"Extourne de l'écriture {originale.numero} (brouillon à valider).",
            valeurs_avant={"ecriture_extournee_id": str(originale.id)},
        )
        return nouvelle

    def obtenir_ecriture(self, ecriture_id: uuid.UUID) -> Ecriture:
        return self._obtenir_ecriture_ou_lever(ecriture_id)

    def lister_lignes(self, ecriture_id: uuid.UUID) -> list[LigneEcriture]:
        return self.lignes_ecriture.lister_pour_ecriture(ecriture_id)

    def lister_ecritures(
        self,
        *,
        journal_id: uuid.UUID | None = None,
        exercice_id: uuid.UUID | None = None,
        statut: str | None = None,
    ) -> list[Ecriture]:
        return self.ecritures.lister(journal_id=journal_id, exercice_id=exercice_id, statut=statut)

    def lister_extournant(self, ecriture_id: uuid.UUID) -> list[Ecriture]:
        return self.ecritures.lister_extournant(ecriture_id)

    # --- Lettrage manuel (cahier, section 8.2) ------------------------------
    # Rapproche entre elles des lignes d'un même compte lettrable (compte
    # général lettrable ou compte collectif de tiers comme 411/401) qui
    # s'annulent — typiquement une facture et son règlement. Même principe
    # que le rapprochement bancaire de `tresorerie` (même colonne
    # `code_lettrage`, même convention de code aléatoire), mais ICI les deux
    # côtés du rapprochement sont des lignes d'écriture entre elles, pas une
    # ligne d'écriture face à une ligne de relevé.

    def lister_lignes_lettrage(
        self,
        compte_id: uuid.UUID,
        *,
        tiers_id: uuid.UUID | None = None,
        lettrees: bool | None = None,
    ) -> list[LigneLettrage]:
        compte = self._obtenir_compte_ou_lever(compte_id)
        if not compte.lettrable:
            raise ValidationMetier(f"Le compte {compte.numero} n'est pas lettrable.")
        resultats = self.lignes_ecriture.lister_pour_lettrage(
            compte_id, tiers_id=tiers_id, lettrees=lettrees
        )
        return [
            LigneLettrage(
                id=ligne.id,
                ecriture_id=ligne.ecriture_id,
                date_ecriture=date_ecriture,
                numero=numero,
                reference_piece=reference_piece,
                libelle_ecriture=libelle_ecriture,
                libelle_ligne=ligne.libelle,
                debit=ligne.debit,
                credit=ligne.credit,
                tiers_id=ligne.tiers_id,
                code_lettrage=ligne.code_lettrage,
            )
            for ligne, date_ecriture, numero, reference_piece, libelle_ecriture in resultats
        ]

    def lettrer(self, *, auteur_id: uuid.UUID, ligne_ecriture_ids: list[uuid.UUID]) -> str:
        if len(ligne_ecriture_ids) < 2:
            raise ValidationMetier("Le lettrage nécessite au moins deux lignes.")
        lignes = self.lignes_ecriture.obtenir_plusieurs(ligne_ecriture_ids)
        if len(lignes) != len(set(ligne_ecriture_ids)):
            raise RessourceIntrouvable("Une ou plusieurs lignes d'écriture sont introuvables.")

        premiere = lignes[0]
        compte = self._obtenir_compte_ou_lever(premiere.compte_id)
        if not compte.lettrable:
            raise ValidationMetier(f"Le compte {compte.numero} n'est pas lettrable.")

        for ligne in lignes:
            if ligne.code_lettrage is not None:
                raise ValidationMetier("Une ligne déjà lettrée ne peut pas l'être à nouveau.")
            if ligne.compte_id != premiere.compte_id:
                raise ValidationMetier("Toutes les lignes doivent porter sur le même compte.")
            # Un compte collectif (411, 401...) porte les comptes de
            # plusieurs tiers à la fois : interdire de lettrer la facture
            # d'un client contre le règlement d'un autre.
            if compte.est_collectif and ligne.tiers_id != premiere.tiers_id:
                raise ValidationMetier(
                    "Toutes les lignes doivent porter sur le même tiers (compte collectif)."
                )
            ecriture = self._obtenir_ecriture_ou_lever(ligne.ecriture_id)
            if ecriture.statut != StatutEcriture.VALIDEE.value:
                raise ValidationMetier(
                    "Seules les lignes d'écritures validées peuvent être lettrées — une "
                    "écriture en brouillon reste modifiable."
                )

        solde = sum((ligne.debit - ligne.credit for ligne in lignes), Decimal("0"))
        if solde != 0:
            raise ValidationMetier(f"Le lettrage n'est pas équilibré : solde {solde} ≠ 0.")

        code = f"LET{uuid.uuid4().hex[:10].upper()}"
        for ligne in lignes:
            ligne.code_lettrage = code
        self.db.flush()

        self.journal_activite.enregistrer(
            module="comptabilite",
            type_action=TypeAction.VALIDER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Compte",
            objet_id=compte.id,
            description=f"Lettrage manuel ({code}) du compte {compte.numero} : {len(lignes)} ligne(s).",
            valeurs_apres={"code_lettrage": code},
        )
        return code

    def delettrer(self, code_lettrage: str, *, auteur_id: uuid.UUID) -> None:
        lignes = self.lignes_ecriture.lister_par_code_lettrage(code_lettrage)
        if not lignes:
            raise RessourceIntrouvable("Aucun lettrage trouvé pour ce code.")
        compte_id = lignes[0].compte_id
        for ligne in lignes:
            ligne.code_lettrage = None
        self.db.flush()

        self.journal_activite.enregistrer(
            module="comptabilite",
            type_action=TypeAction.ANNULER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Compte",
            objet_id=compte_id,
            description=f"Annulation du lettrage {code_lettrage}.",
            valeurs_avant={"code_lettrage": code_lettrage},
        )

    # --- Aides internes -------------------------------------------------------

    def _obtenir_compte_ou_lever(self, compte_id: uuid.UUID) -> Compte:
        compte = self.comptes.obtenir(compte_id)
        if compte is None:
            raise RessourceIntrouvable("Compte introuvable.")
        return compte

    def _obtenir_extension_ou_lever(self, compte_id: uuid.UUID) -> Compte:
        compte = self._obtenir_compte_ou_lever(compte_id)
        if compte.entreprise_id is None:
            raise AccesRefuse(
                "Ce compte fait partie du référentiel global ; il ne peut pas être "
                "modifié depuis une entreprise."
            )
        return compte

    def _obtenir_journal_ou_lever(self, journal_id: uuid.UUID) -> Journal:
        journal = self.journaux.obtenir(journal_id)
        if journal is None:
            raise RessourceIntrouvable("Journal introuvable.")
        return journal

    def _obtenir_ecriture_ou_lever(self, ecriture_id: uuid.UUID) -> Ecriture:
        ecriture = self.ecritures.obtenir(ecriture_id)
        if ecriture is None:
            raise RessourceIntrouvable("Écriture introuvable.")
        return ecriture

    def _obtenir_exercice_ou_lever(self, exercice_id: uuid.UUID) -> Exercice:
        exercice = self.exercices.obtenir(exercice_id)
        if exercice is None:
            raise RessourceIntrouvable("Exercice introuvable.")
        return exercice

    def _verifier_brouillon(self, ecriture: Ecriture) -> None:
        if ecriture.statut != StatutEcriture.BROUILLON.value:
            raise ValidationMetier(
                "Cette écriture est validée : elle ne peut plus être modifiée ni "
                "supprimée. Utilisez l'extourne pour la corriger."
            )

    def _verifier_exercice_ouvert(self, exercice: Exercice) -> None:
        if exercice.statut == StatutExercice.OUVERT.value:
            return
        # Paramétrable par entreprise (cahier, section 7.2 "selon
        # paramétrage") — voir `Entreprise.blocage_ecritures_cloture`.
        # `True` si l'entreprise est introuvable (ne devrait pas arriver,
        # mais on ne désactive jamais silencieusement un garde-fou sur un
        # état incohérent).
        entreprise = self.entreprises.obtenir(self.entreprise_id)
        if entreprise is not None and not entreprise.blocage_ecritures_cloture:
            return
        raise ValidationMetier("Impossible d'agir sur une écriture d'un exercice clôturé.")

    def _verifier_date_dans_exercice(self, date_ecriture: date, exercice: Exercice) -> None:
        if date_ecriture < exercice.date_debut or date_ecriture > exercice.date_fin:
            raise ValidationMetier("La date de l'écriture doit être comprise dans l'exercice.")

    def _verifier_equilibre(self, lignes: list) -> None:
        if len(lignes) < 2:
            raise ValidationMetier("Une écriture doit comporter au moins deux lignes.")
        total_debit = sum((ligne.debit for ligne in lignes), Decimal("0"))
        total_credit = sum((ligne.credit for ligne in lignes), Decimal("0"))
        if total_debit != total_credit:
            raise ValidationMetier(
                "L'écriture n'est pas équilibrée : total débit "
                f"{total_debit} ≠ total crédit {total_credit}."
            )

    def _valider_lignes(self, lignes: list[LigneSaisie]) -> None:
        self._verifier_equilibre(lignes)
        for ligne in lignes:
            if (ligne.debit > 0) == (ligne.credit > 0):
                raise ValidationMetier(
                    "Chaque ligne doit être soit débitrice, soit créditrice (jamais "
                    "les deux, jamais ni l'une ni l'autre)."
                )
            compte = self._obtenir_compte_ou_lever(ligne.compte_id)
            if not compte.actif:
                raise ValidationMetier(f"Le compte {compte.numero} est désactivé.")
            if ligne.tiers_id is not None:
                if not compte.lettrable:
                    raise ValidationMetier(
                        f"Le compte {compte.numero} n'est pas lettrable ; il ne peut "
                        "pas porter de tiers."
                    )
                if self.tiers.obtenir(ligne.tiers_id) is None:
                    raise RessourceIntrouvable("Tiers introuvable.")

    def _remplacer_lignes(
        self, ecriture_id: uuid.UUID, lignes: list[LigneSaisie], *, date_ecriture: date
    ) -> None:
        for ligne in lignes:
            self.lignes_ecriture.ajouter(
                LigneEcriture(
                    ecriture_id=ecriture_id,
                    compte_id=ligne.compte_id,
                    tiers_id=ligne.tiers_id,
                    libelle=ligne.libelle,
                    debit=ligne.debit,
                    credit=ligne.credit,
                    date_echeance=self._calculer_date_echeance(ligne, date_ecriture),
                )
            )

    def _calculer_date_echeance(self, ligne: LigneSaisie, date_ecriture: date) -> date | None:
        """Échéancier clients/fournisseurs (voir la note de tête de fichier
        de models.py) : une échéance explicite est toujours respectée telle
        quelle ; à défaut, dérivée de `Tiers.delai_paiement_jours` quand le
        tiers et ce délai sont connus, sinon NULL (pas d'échéance connue)."""
        if ligne.date_echeance is not None:
            return ligne.date_echeance
        if ligne.tiers_id is None:
            return None
        tiers = self.tiers.obtenir(ligne.tiers_id)
        if tiers is None or tiers.delai_paiement_jours is None:
            return None
        return date_ecriture + timedelta(days=tiers.delai_paiement_jours)
    #Nouvelle modification