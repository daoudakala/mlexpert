"""Règles métier du module immobilisations.

`ServiceImmobilisations` : construit avec `(db, entreprise_id)`, comme
`ServiceTresorerie`.

Calcul du plan d'amortissement — génération ligne par ligne, pas d'un
coup pour toute la durée : contrairement à un relevé bancaire, les
exercices futurs n'existent pas forcément encore en base au moment où
l'immobilisation est créée (ils sont créés au fil du temps, module
`exercices`). `generer_ligne_amortissement` calcule donc UNE ligne à la
fois, pour un exercice déjà existant et ouvert, en s'appuyant sur les
lignes déjà générées pour connaître le cumul et la valeur nette
comptable de départ. Les exercices doivent être traités dans l'ordre
chronologique (pas de saut, pas de génération rétroactive) : c'est ce qui
garantit que le cumul reste correct sans avoir à tout recalculer.

Prorata temporis : la première ligne (ou toute ligne dont l'exercice
commence avant la mise en service) est proratisée sur le nombre de mois
d'utilisation, selon la convention SYSCOHADA du mois de 30 jours (un mois
plein = 30 jours, arrondi à l'entier le plus proche, borné à
[1, 12]) — une simplification assumée : un décompte jour par jour donnerait
un résultat légèrement différent, mais c'est la convention usuelle pour ce
calcul en pratique comptable OHADA.

Deux méthodes :

- `lineaire` : taux annuel constant = 1 / durée, appliqué à la base
  amortissable constante (valeur d'origine − valeur résiduelle).
- `degressif` : `taux_degressif` (fourni sur la fiche, pas calculé à
  partir d'un coefficient OHADA par tranche de durée — cahier des
  charges non normatif là-dessus à ce stade) appliqué à la valeur nette
  comptable de DÉBUT de période, donc décroissante d'année en année.
  Limite connue, assumée à ce stade : la règle OHADA de bascule
  automatique vers le linéaire dès que l'annuité linéaire sur la durée
  résiduelle dépasserait l'annuité dégressive n'est PAS implémentée —
  le dégressif reste dégressif jusqu'à la dernière ligne, qui absorbe
  simplement le solde restant pour atteindre la valeur résiduelle
  exactement (voir `_calculer_dotation`).

Chaque ligne est bornée pour ne jamais amortir sous la valeur résiduelle :
si la dotation théorique dépasserait ce qui reste à amortir, elle est
plafonnée à ce reliquat — cette ligne devient alors, de fait, la dernière
du plan.
"""

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import RessourceIntrouvable, ValidationMetier
from app.modules.comptabilite.models import Ecriture
from app.modules.comptabilite.repository import RepositoryComptes
from app.modules.comptabilite.service import LigneSaisie, ServiceComptabilite
from app.modules.exercices.models import StatutExercice
from app.modules.exercices.repository import RepositoryExercice
from app.modules.immobilisations.models import (
    Immobilisation,
    LigneAmortissement,
    MethodeAmortissement,
    StatutImmobilisation,
    StatutLigneAmortissement,
)
from app.modules.immobilisations.repository import RepositoryImmobilisations, RepositoryLignesAmortissement
from app.modules.journal_activite.models import TypeAction
from app.modules.journal_activite.service import ServiceJournalActivite
from app.modules.tiers.repository import RepositoryTiers

CLASSE_COMPTE_IMMOBILISATION = 2
CLASSE_COMPTE_DOTATION = 6


def _mois_periode(debut: date, fin: date) -> int:
    """Nombre de mois d'utilisation entre `debut` et `fin` (inclus), selon
    la convention SYSCOHADA du mois de 30 jours — voir la note de tête de
    fichier. Toujours compris entre 1 et 12."""
    jours = (fin - debut).days + 1
    mois = round(jours / 30)
    return max(1, min(12, mois))


@dataclass
class CessionDemande:
    date_sortie: date
    prix_cession: Decimal
    journal_id: uuid.UUID
    compte_tresorerie_id: uuid.UUID
    compte_produit_cession_id: uuid.UUID
    compte_valeur_comptable_sortie_id: uuid.UUID


@dataclass
class ReformeDemande:
    date_sortie: date
    journal_id: uuid.UUID
    compte_valeur_comptable_sortie_id: uuid.UUID


@dataclass
class ImmobilisationCreation:
    libelle: str
    date_acquisition: date
    date_mise_en_service: date
    valeur_origine: Decimal
    duree_amortissement_annees: int
    compte_immobilisation_id: uuid.UUID
    compte_amortissement_id: uuid.UUID
    compte_dotation_id: uuid.UUID
    valeur_residuelle: Decimal = Decimal("0")
    methode_amortissement: MethodeAmortissement = MethodeAmortissement.LINEAIRE
    taux_degressif: Decimal | None = None
    categorie: str | None = None
    numero_inventaire: str | None = None
    fournisseur_id: uuid.UUID | None = None


class ServiceImmobilisations:
    def __init__(self, db: Session, entreprise_id: uuid.UUID) -> None:
        self.db = db
        self.entreprise_id = entreprise_id
        self.immobilisations = RepositoryImmobilisations(db, entreprise_id)
        self.lignes_amortissement = RepositoryLignesAmortissement(db, entreprise_id)
        self.comptes = RepositoryComptes(db, entreprise_id)
        self.exercices = RepositoryExercice(db, entreprise_id)
        self.tiers = RepositoryTiers(db, entreprise_id)
        self.journal_activite = ServiceJournalActivite(db)

    # --- Immobilisations -----------------------------------------------------

    def creer_immobilisation(self, donnees: ImmobilisationCreation, *, auteur_id: uuid.UUID) -> Immobilisation:
        self._valider_donnees_creation(donnees)

        compte_immo = self._obtenir_compte_ou_lever(donnees.compte_immobilisation_id)
        self._verifier_classe(compte_immo, CLASSE_COMPTE_IMMOBILISATION, "d'immobilisation")
        compte_amort = self._obtenir_compte_ou_lever(donnees.compte_amortissement_id)
        self._verifier_classe(compte_amort, CLASSE_COMPTE_IMMOBILISATION, "d'amortissement")
        compte_dotation = self._obtenir_compte_ou_lever(donnees.compte_dotation_id)
        self._verifier_classe(compte_dotation, CLASSE_COMPTE_DOTATION, "de dotation aux amortissements")

        if donnees.fournisseur_id is not None and self.tiers.obtenir(donnees.fournisseur_id) is None:
            raise RessourceIntrouvable("Fournisseur introuvable.")

        immobilisation = Immobilisation(
            libelle=donnees.libelle,
            categorie=donnees.categorie,
            numero_inventaire=donnees.numero_inventaire,
            date_acquisition=donnees.date_acquisition,
            date_mise_en_service=donnees.date_mise_en_service,
            valeur_origine=donnees.valeur_origine,
            valeur_residuelle=donnees.valeur_residuelle,
            duree_amortissement_annees=donnees.duree_amortissement_annees,
            methode_amortissement=donnees.methode_amortissement.value,
            taux_degressif=donnees.taux_degressif,
            compte_immobilisation_id=donnees.compte_immobilisation_id,
            compte_amortissement_id=donnees.compte_amortissement_id,
            compte_dotation_id=donnees.compte_dotation_id,
            fournisseur_id=donnees.fournisseur_id,
        )
        self.immobilisations.ajouter(immobilisation)
        self.journal_activite.enregistrer(
            module="immobilisations",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Immobilisation",
            objet_id=immobilisation.id,
            description=f"Création de l'immobilisation '{donnees.libelle}'.",
            valeurs_apres={"libelle": donnees.libelle, "valeur_origine": str(donnees.valeur_origine)},
        )
        return immobilisation

    def modifier_immobilisation(
        self,
        immobilisation_id: uuid.UUID,
        *,
        auteur_id: uuid.UUID,
        libelle: str | None = None,
        categorie: str | None = None,
        numero_inventaire: str | None = None,
        fournisseur_id: uuid.UUID | None = None,
    ) -> Immobilisation:
        """Mise à jour volontairement limitée aux champs descriptifs : la
        valeur, la durée, la méthode et les comptes rattachés ne se
        modifient pas ici — les changer invaliderait un plan
        d'amortissement déjà généré (voir la note de tête de fichier sur
        la portée limitée de ce premier passage)."""
        immobilisation = self._obtenir_immobilisation_ou_lever(immobilisation_id)
        if fournisseur_id is not None and self.tiers.obtenir(fournisseur_id) is None:
            raise RessourceIntrouvable("Fournisseur introuvable.")

        if libelle is not None:
            immobilisation.libelle = libelle
        if categorie is not None:
            immobilisation.categorie = categorie
        if numero_inventaire is not None:
            immobilisation.numero_inventaire = numero_inventaire
        if fournisseur_id is not None:
            immobilisation.fournisseur_id = fournisseur_id
        self.db.flush()

        self.journal_activite.enregistrer(
            module="immobilisations",
            type_action=TypeAction.MODIFIER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Immobilisation",
            objet_id=immobilisation.id,
            description=f"Modification de l'immobilisation '{immobilisation.libelle}'.",
        )
        return immobilisation

    def obtenir_immobilisation(self, immobilisation_id: uuid.UUID) -> Immobilisation:
        return self._obtenir_immobilisation_ou_lever(immobilisation_id)

    def lister_immobilisations(self, *, statut: str | None = None) -> list[Immobilisation]:
        return self.immobilisations.lister(statut=statut)

    # --- Plan d'amortissement ------------------------------------------------

    def generer_ligne_amortissement(
        self, immobilisation_id: uuid.UUID, exercice_id: uuid.UUID, *, auteur_id: uuid.UUID
    ) -> LigneAmortissement:
        immobilisation = self._obtenir_immobilisation_ou_lever(immobilisation_id)
        if immobilisation.statut != StatutImmobilisation.EN_SERVICE.value:
            raise ValidationMetier(
                "Seule une immobilisation en service peut avoir une dotation générée."
            )

        exercice = self.exercices.obtenir(exercice_id)
        if exercice is None:
            raise RessourceIntrouvable("Exercice introuvable.")
        if exercice.statut != StatutExercice.OUVERT.value:
            raise ValidationMetier("Impossible de générer une dotation sur un exercice clôturé.")

        if self.lignes_amortissement.obtenir_pour_exercice(immobilisation_id, exercice_id) is not None:
            raise ValidationMetier("Cet exercice a déjà une ligne de plan d'amortissement.")

        lignes_existantes = self.lignes_amortissement.lister_pour_immobilisation(immobilisation_id)
        base_totale = immobilisation.valeur_origine - immobilisation.valeur_residuelle

        if lignes_existantes:
            derniere = lignes_existantes[-1]
            derniere_exercice = self.exercices.obtenir(derniere.exercice_id)
            if exercice.date_debut <= derniere_exercice.date_fin:
                raise ValidationMetier(
                    "Les exercices doivent être traités dans l'ordre chronologique : "
                    f"le dernier exercice traité se termine le {derniere_exercice.date_fin}."
                )
            if derniere.cumul_amortissements >= base_totale:
                raise ValidationMetier("Cette immobilisation est déjà totalement amortie.")
            cumul_avant = derniere.cumul_amortissements
            vnc_debut = derniere.valeur_nette_comptable
            debut_periode = exercice.date_debut
        else:
            if exercice.date_fin < immobilisation.date_mise_en_service:
                raise ValidationMetier(
                    "Cet exercice se termine avant la mise en service de l'immobilisation."
                )
            cumul_avant = Decimal("0")
            vnc_debut = immobilisation.valeur_origine
            debut_periode = max(immobilisation.date_mise_en_service, exercice.date_debut)

        mois = _mois_periode(debut_periode, exercice.date_fin)
        base_ligne, taux_applique, dotation = self._calculer_dotation(
            immobilisation=immobilisation,
            base_totale=base_totale,
            vnc_debut=vnc_debut,
            cumul_avant=cumul_avant,
            mois=mois,
        )

        cumul_apres = cumul_avant + dotation
        vnc_apres = immobilisation.valeur_origine - cumul_apres

        ligne = LigneAmortissement(
            immobilisation_id=immobilisation_id,
            exercice_id=exercice_id,
            base_amortissable=base_ligne,
            taux_applique=taux_applique,
            dotation=dotation,
            cumul_amortissements=cumul_apres,
            valeur_nette_comptable=vnc_apres,
            statut=StatutLigneAmortissement.PREVU.value,
        )
        self.lignes_amortissement.ajouter(ligne)
        self.journal_activite.enregistrer(
            module="immobilisations",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="LigneAmortissement",
            objet_id=ligne.id,
            description=(
                f"Génération de la dotation {exercice.date_debut.year} pour "
                f"'{immobilisation.libelle}' : {dotation}."
            ),
            valeurs_apres={"dotation": str(dotation), "cumul_amortissements": str(cumul_apres)},
        )
        return ligne

    def lister_lignes_amortissement(self, immobilisation_id: uuid.UUID) -> list[LigneAmortissement]:
        return self.lignes_amortissement.lister_pour_immobilisation(immobilisation_id)

    def generer_ecriture_amortissement(
        self, ligne_id: uuid.UUID, *, journal_id: uuid.UUID, auteur_id: uuid.UUID
    ) -> Ecriture:
        """Comptabilise une ligne de plan d'amortissement déjà générée :
        débit du compte de dotation (classe 6), crédit du compte
        d'amortissement (classe 28) — les deux comptes viennent de la
        fiche `Immobilisation`, déjà validés à sa création (voir
        `creer_immobilisation`), donc rien à revalider ici."""
        ligne = self.lignes_amortissement.obtenir(ligne_id)
        if ligne is None:
            raise RessourceIntrouvable("Ligne de plan d'amortissement introuvable.")
        if ligne.statut != StatutLigneAmortissement.PREVU.value:
            raise ValidationMetier("Cette ligne est déjà comptabilisée.")

        immobilisation = self._obtenir_immobilisation_ou_lever(ligne.immobilisation_id)
        exercice = self.exercices.obtenir(ligne.exercice_id)
        if exercice is None:
            raise RessourceIntrouvable("Exercice introuvable.")

        service_comptabilite = ServiceComptabilite(self.db, self.entreprise_id)
        ecriture = service_comptabilite.creer_ecriture(
            auteur_id=auteur_id,
            journal_id=journal_id,
            exercice_id=ligne.exercice_id,
            date_ecriture=exercice.date_fin,
            libelle=(
                f"Dotation amortissement {immobilisation.libelle} - "
                f"exercice {exercice.date_debut.year}"
            ),
            lignes=[
                LigneSaisie(compte_id=immobilisation.compte_dotation_id, debit=ligne.dotation),
                LigneSaisie(compte_id=immobilisation.compte_amortissement_id, credit=ligne.dotation),
            ],
        )

        ligne.ecriture_id = ecriture.id
        ligne.statut = StatutLigneAmortissement.COMPTABILISE.value
        self.db.flush()

        self.journal_activite.enregistrer(
            module="immobilisations",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="LigneAmortissement",
            objet_id=ligne.id,
            description=f"Génération de l'écriture de dotation pour '{immobilisation.libelle}'.",
            valeurs_apres={"ecriture_id": str(ecriture.id)},
        )
        return ecriture

    # --- Cession / mise au rebut ----------------------------------------------

    def ceder_immobilisation(
        self, immobilisation_id: uuid.UUID, donnees: CessionDemande, *, auteur_id: uuid.UUID
    ) -> Immobilisation:
        """Cède (vend) l'immobilisation : sort le bien du bilan (crédit
        valeur d'origine, débit cumul d'amortissements, débit valeur nette
        comptable) et constate le produit de cession (débit trésorerie,
        crédit compte de produit) dans une même écriture. La plus ou
        moins-value n'a pas de ligne dédiée : elle ressort naturellement
        de la différence entre le débit VNC (compte 81) et le crédit
        produit de cession (compte 82), comme le veut la méthode SYSCOHADA
        — voir la note de tête de fichier de `models.py`."""
        immobilisation = self._obtenir_immobilisation_ou_lever(immobilisation_id)
        if immobilisation.statut != StatutImmobilisation.EN_SERVICE.value:
            raise ValidationMetier("Seule une immobilisation en service peut être cédée.")
        if donnees.date_sortie < immobilisation.date_mise_en_service:
            raise ValidationMetier(
                "La date de sortie ne peut pas être antérieure à la mise en service."
            )
        if donnees.prix_cession < 0:
            raise ValidationMetier("Le prix de cession ne peut pas être négatif.")
        for compte_id in (
            donnees.compte_tresorerie_id,
            donnees.compte_produit_cession_id,
            donnees.compte_valeur_comptable_sortie_id,
        ):
            if self.comptes.obtenir(compte_id) is None:
                raise RessourceIntrouvable("Compte comptable introuvable.")

        exercice = self.exercices.obtenir_pour_date(donnees.date_sortie)
        if exercice is None:
            raise ValidationMetier(
                f"Aucun exercice ne couvre la date de sortie ({donnees.date_sortie})."
            )

        cumul, vnc = self._cumul_et_vnc(immobilisation)
        plus_ou_moins_value = donnees.prix_cession - vnc

        lignes_saisies = self._lignes_sortie_bien(
            immobilisation, cumul, vnc, donnees.compte_valeur_comptable_sortie_id
        )
        if donnees.prix_cession > 0:
            lignes_saisies.append(
                LigneSaisie(compte_id=donnees.compte_tresorerie_id, debit=donnees.prix_cession)
            )
            lignes_saisies.append(
                LigneSaisie(compte_id=donnees.compte_produit_cession_id, credit=donnees.prix_cession)
            )

        service_comptabilite = ServiceComptabilite(self.db, self.entreprise_id)
        ecriture = service_comptabilite.creer_ecriture(
            auteur_id=auteur_id,
            journal_id=donnees.journal_id,
            exercice_id=exercice.id,
            date_ecriture=donnees.date_sortie,
            libelle=f"Cession de {immobilisation.libelle}",
            lignes=lignes_saisies,
        )

        immobilisation.statut = StatutImmobilisation.CEDEE.value
        immobilisation.date_sortie = donnees.date_sortie
        immobilisation.prix_cession = donnees.prix_cession
        immobilisation.valeur_nette_comptable_sortie = vnc
        immobilisation.plus_ou_moins_value = plus_ou_moins_value
        immobilisation.ecriture_sortie_id = ecriture.id
        self.db.flush()

        self.journal_activite.enregistrer(
            module="immobilisations",
            type_action=TypeAction.MODIFIER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Immobilisation",
            objet_id=immobilisation.id,
            description=f"Cession de '{immobilisation.libelle}' pour {donnees.prix_cession}.",
            valeurs_avant={"statut": StatutImmobilisation.EN_SERVICE.value},
            valeurs_apres={
                "statut": StatutImmobilisation.CEDEE.value,
                "prix_cession": str(donnees.prix_cession),
                "plus_ou_moins_value": str(plus_ou_moins_value),
            },
        )
        return immobilisation

    def reformer_immobilisation(
        self, immobilisation_id: uuid.UUID, donnees: ReformeDemande, *, auteur_id: uuid.UUID
    ) -> Immobilisation:
        """Met au rebut l'immobilisation : sort le bien du bilan sans
        contrepartie financière (pas d'encaissement, pas de produit de
        cession) — même logique que `ceder_immobilisation` amputée de son
        second volet."""
        immobilisation = self._obtenir_immobilisation_ou_lever(immobilisation_id)
        if immobilisation.statut != StatutImmobilisation.EN_SERVICE.value:
            raise ValidationMetier("Seule une immobilisation en service peut être réformée.")
        if donnees.date_sortie < immobilisation.date_mise_en_service:
            raise ValidationMetier(
                "La date de sortie ne peut pas être antérieure à la mise en service."
            )
        if self.comptes.obtenir(donnees.compte_valeur_comptable_sortie_id) is None:
            raise RessourceIntrouvable("Compte comptable introuvable.")

        exercice = self.exercices.obtenir_pour_date(donnees.date_sortie)
        if exercice is None:
            raise ValidationMetier(
                f"Aucun exercice ne couvre la date de sortie ({donnees.date_sortie})."
            )

        cumul, vnc = self._cumul_et_vnc(immobilisation)

        service_comptabilite = ServiceComptabilite(self.db, self.entreprise_id)
        ecriture = service_comptabilite.creer_ecriture(
            auteur_id=auteur_id,
            journal_id=donnees.journal_id,
            exercice_id=exercice.id,
            date_ecriture=donnees.date_sortie,
            libelle=f"Mise au rebut de {immobilisation.libelle}",
            lignes=self._lignes_sortie_bien(
                immobilisation, cumul, vnc, donnees.compte_valeur_comptable_sortie_id
            ),
        )

        immobilisation.statut = StatutImmobilisation.REFORMEE.value
        immobilisation.date_sortie = donnees.date_sortie
        immobilisation.valeur_nette_comptable_sortie = vnc
        immobilisation.ecriture_sortie_id = ecriture.id
        self.db.flush()

        self.journal_activite.enregistrer(
            module="immobilisations",
            type_action=TypeAction.MODIFIER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Immobilisation",
            objet_id=immobilisation.id,
            description=f"Mise au rebut de '{immobilisation.libelle}'.",
            valeurs_avant={"statut": StatutImmobilisation.EN_SERVICE.value},
            valeurs_apres={"statut": StatutImmobilisation.REFORMEE.value},
        )
        return immobilisation

    # --- Aides internes -------------------------------------------------------

    def _cumul_et_vnc(self, immobilisation: Immobilisation) -> tuple[Decimal, Decimal]:
        """Cumul d'amortissements et valeur nette comptable au dernier
        état connu (dernière `LigneAmortissement` générée, ou aucune
        dotation si le plan n'a pas encore été généré) — voir la note de
        tête de fichier sur le choix de ne pas exiger une dotation à jour
        avant la sortie."""
        lignes = self.lignes_amortissement.lister_pour_immobilisation(immobilisation.id)
        cumul = lignes[-1].cumul_amortissements if lignes else Decimal("0")
        vnc = immobilisation.valeur_origine - cumul
        return cumul, vnc

    def _lignes_sortie_bien(
        self,
        immobilisation: Immobilisation,
        cumul: Decimal,
        vnc: Decimal,
        compte_valeur_comptable_sortie_id: uuid.UUID,
    ) -> list[LigneSaisie]:
        """Les lignes communes à la cession et à la réforme : solder le
        bien (crédit valeur d'origine) contre son cumul d'amortissements
        (débit) et sa valeur nette comptable (débit) — une ligne à montant
        nul est invalide pour `ServiceComptabilite`, donc chacune n'est
        ajoutée que si son montant est strictement positif."""
        lignes: list[LigneSaisie] = []
        if cumul > 0:
            lignes.append(LigneSaisie(compte_id=immobilisation.compte_amortissement_id, debit=cumul))
        if vnc > 0:
            lignes.append(
                LigneSaisie(compte_id=compte_valeur_comptable_sortie_id, debit=vnc)
            )
        lignes.append(
            LigneSaisie(compte_id=immobilisation.compte_immobilisation_id, credit=immobilisation.valeur_origine)
        )
        return lignes

    def _calculer_dotation(
        self,
        *,
        immobilisation: Immobilisation,
        base_totale: Decimal,
        vnc_debut: Decimal,
        cumul_avant: Decimal,
        mois: int,
    ) -> tuple[Decimal, Decimal, Decimal]:
        """Retourne (base utilisée pour cette ligne, taux appliqué en %,
        dotation calculée et plafonnée). Voir la note de tête de fichier
        pour la logique linéaire/dégressif et son prorata temporis.

        Important : en linéaire, la dotation se calcule sur la fraction
        EXACTE (1 / durée), jamais sur le taux arrondi à 2 décimales —
        arrondir d'abord introduirait une dérive inutile (ex. 33,33 % de
        600 000 = 199 980, contre 200 000 avec la fraction exacte 1/3).
        `taux_applique` reste arrondi à 2 décimales, mais uniquement pour
        l'affichage : ce n'est pas lui qui sert au calcul en linéaire."""
        if immobilisation.methode_amortissement == MethodeAmortissement.DEGRESSIF.value:
            base_ligne = vnc_debut
            taux_applique = immobilisation.taux_degressif
            dotation_theorique = (base_ligne * taux_applique / Decimal("100") * mois / Decimal("12")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        else:
            base_ligne = base_totale
            taux_applique = (Decimal("100") / immobilisation.duree_amortissement_annees).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            dotation_theorique = (
                base_ligne / immobilisation.duree_amortissement_annees * mois / Decimal("12")
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        reliquat = base_totale - cumul_avant
        dotation = min(dotation_theorique, reliquat)
        return base_ligne, taux_applique, dotation

    def _valider_donnees_creation(self, donnees: ImmobilisationCreation) -> None:
        if donnees.valeur_origine <= 0:
            raise ValidationMetier("La valeur d'origine doit être strictement positive.")
        if donnees.valeur_residuelle < 0 or donnees.valeur_residuelle >= donnees.valeur_origine:
            raise ValidationMetier(
                "La valeur résiduelle doit être positive ou nulle, et strictement "
                "inférieure à la valeur d'origine."
            )
        if donnees.duree_amortissement_annees <= 0:
            raise ValidationMetier("La durée d'amortissement doit être strictement positive.")
        if donnees.date_mise_en_service < donnees.date_acquisition:
            raise ValidationMetier(
                "La date de mise en service ne peut pas être antérieure à la date d'acquisition."
            )
        est_degressif = donnees.methode_amortissement == MethodeAmortissement.DEGRESSIF
        if est_degressif and donnees.taux_degressif is None:
            raise ValidationMetier("Un taux dégressif est requis pour la méthode dégressive.")
        if not est_degressif and donnees.taux_degressif is not None:
            raise ValidationMetier("Le taux dégressif ne s'applique qu'à la méthode dégressive.")

    def _obtenir_immobilisation_ou_lever(self, immobilisation_id: uuid.UUID) -> Immobilisation:
        immobilisation = self.immobilisations.obtenir(immobilisation_id)
        if immobilisation is None:
            raise RessourceIntrouvable("Immobilisation introuvable.")
        return immobilisation

    def _obtenir_compte_ou_lever(self, compte_id: uuid.UUID):
        compte = self.comptes.obtenir(compte_id)
        if compte is None:
            raise RessourceIntrouvable("Compte comptable introuvable.")
        return compte

    def _verifier_classe(self, compte, classe_attendue: int, libelle_role: str) -> None:
        if compte.classe != classe_attendue:
            raise ValidationMetier(
                f"Le compte {compte.numero} n'est pas un compte {libelle_role} "
                f"(classe {classe_attendue} attendue, classe {compte.classe} fournie)."
            )