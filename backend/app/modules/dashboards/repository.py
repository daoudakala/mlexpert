"""Accès aux données du module dashboards.

Pas de `models.py` pour ce module : contrairement aux autres, il ne
persiste rien — c'est une couche de LECTURE pure, qui agrège les données
déjà stockées par `comptabilite` (`Ecriture`/`LigneEcriture`/`Compte`).
`RepositoryReporting` interroge donc directement les modèles d'un autre
module plutôt que d'hériter de `Repository`/`RepositoryEntreprise` (qui
gèrent un seul modèle CRUD, pas des agrégations inter-tables) — c'est la
même logique qui a fait préférer un repository dédié à `Compte` dans
`comptabilite/repository.py` plutôt que de forcer les classes génériques.

Toutes les requêtes filtrent explicitement `Ecriture.statut == 'validee'`
: un brouillon ne doit jamais apparaître dans une balance, un grand livre
ou un résultat — seule une écriture validée est définitive.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.modules.comptabilite.models import (
    Compte,
    Ecriture,
    Journal,
    LigneEcriture,
    StatutEcriture,
    TypeJournal,
)
from app.modules.exercices.models import Exercice, StatutExercice
from app.modules.portail_client.models import DemandeDocument, StatutDemandeDocument
from app.modules.tiers.models import Tiers
from app.modules.tresorerie.models import CompteBancaire, LigneReleve, ReleveBancaire


class RepositoryReporting:
    def __init__(self, db: Session, entreprise_id: uuid.UUID) -> None:
        self.db = db
        self.entreprise_id = entreprise_id

    def totaux_par_compte(
        self,
        exercice_id: uuid.UUID,
        *,
        date_debut: date | None = None,
        date_fin: date | None = None,
    ) -> list[tuple[uuid.UUID, str, str, int, Decimal, Decimal]]:
        """(compte_id, numero, libelle, classe, total_debit, total_credit)
        pour chaque compte mouvementé sur cet exercice, écritures validées
        uniquement. Base de la balance générale, du bilan et du compte de
        résultat détaillé (voir `service.py`) — `classe` ne sert qu'à ces
        deux derniers, la balance générale l'ignore simplement.

        `date_debut` / `date_fin` (facultatifs, inclusifs) restreignent aux
        écritures de cette période — utilisés par le tableau de bord
        (filtre par période) ; sans eux, tout l'exercice est pris."""
        requete = (
            select(
                Compte.id,
                Compte.numero,
                Compte.libelle,
                Compte.classe,
                func.coalesce(func.sum(LigneEcriture.debit), 0),
                func.coalesce(func.sum(LigneEcriture.credit), 0),
            )
            .select_from(LigneEcriture)
            .join(Ecriture, LigneEcriture.ecriture_id == Ecriture.id)
            .join(Compte, LigneEcriture.compte_id == Compte.id)
            .where(
                Ecriture.entreprise_id == self.entreprise_id,
                Ecriture.exercice_id == exercice_id,
                Ecriture.statut == StatutEcriture.VALIDEE.value,
            )
            .group_by(Compte.id, Compte.numero, Compte.libelle, Compte.classe)
            .order_by(Compte.numero)
        )
        if date_debut is not None:
            requete = requete.where(Ecriture.date_ecriture >= date_debut)
        if date_fin is not None:
            requete = requete.where(Ecriture.date_ecriture <= date_fin)
        return list(self.db.execute(requete).all())

    def totaux_balance_detaillee(
        self,
        exercice_id: uuid.UUID,
        *,
        date_debut: date,
        date_fin: date,
    ) -> list[tuple[uuid.UUID, str, str, int, Decimal, Decimal, Decimal, Decimal]]:
        """(compte_id, numero, libelle, classe, an_debit, an_credit,
        mv_debit, mv_credit) pour la balance générale à colonnes.

        - À-nouveaux = écritures du journal de report à nouveau (type
          `a_nouveaux`) + toutes les écritures antérieures à `date_debut` ;
        - Mouvements = écritures des autres journaux entre `date_debut` et
          `date_fin` inclus.
        Les écritures postérieures à `date_fin` sont ignorées ; validées
        uniquement. Sur l'exercice entier (`date_debut` = début d'exercice)
        les à-nouveaux se réduisent donc au journal RAN."""
        est_ran = Journal.type_journal == TypeJournal.A_NOUVEAUX.value
        est_an = est_ran | (Ecriture.date_ecriture < date_debut)
        est_mv = ~est_ran & (Ecriture.date_ecriture >= date_debut)

        def somme(condition, colonne):
            return func.coalesce(func.sum(case((condition, colonne), else_=0)), 0)

        requete = (
            select(
                Compte.id,
                Compte.numero,
                Compte.libelle,
                Compte.classe,
                somme(est_an, LigneEcriture.debit),
                somme(est_an, LigneEcriture.credit),
                somme(est_mv, LigneEcriture.debit),
                somme(est_mv, LigneEcriture.credit),
            )
            .select_from(LigneEcriture)
            .join(Ecriture, LigneEcriture.ecriture_id == Ecriture.id)
            .join(Journal, Ecriture.journal_id == Journal.id)
            .join(Compte, LigneEcriture.compte_id == Compte.id)
            .where(
                Ecriture.entreprise_id == self.entreprise_id,
                Ecriture.exercice_id == exercice_id,
                Ecriture.statut == StatutEcriture.VALIDEE.value,
                Ecriture.date_ecriture <= date_fin,
            )
            .group_by(Compte.id, Compte.numero, Compte.libelle, Compte.classe)
            .order_by(Compte.numero)
        )
        return list(self.db.execute(requete).all())

    def _filtre_comptes_journal(self, requete, *, compte_debut, compte_fin, journal_id):
        """Filtres communs au grand livre général : plage de numéros de
        compte (bornes incluses ; `compte_fin` couvre aussi les comptes dont
        le numéro commence par elle, ex. « 41 » inclut 411000) et journal."""
        if compte_debut:
            requete = requete.where(Compte.numero >= compte_debut)
        if compte_fin:
            requete = requete.where(Compte.numero <= compte_fin + "~")
        if journal_id is not None:
            requete = requete.where(Ecriture.journal_id == journal_id)
        return requete

    def lignes_grand_livre_general(
        self,
        exercice_id: uuid.UUID,
        *,
        date_debut: date,
        date_fin: date,
        compte_debut: str | None = None,
        compte_fin: str | None = None,
        journal_id: uuid.UUID | None = None,
    ) -> list[tuple]:
        """(compte_id, numero_compte, libelle_compte, ligne_id, ecriture_id,
        date_ecriture, code_journal, numero_ecriture, libelle_ligne,
        libelle_ecriture, debit, credit, code_lettrage) de toutes les lignes
        de la période, triées par compte puis par date ; écritures validées
        uniquement, TOUS journaux (le report à nouveau y figure aussi)."""
        requete = (
            select(
                Compte.id,
                Compte.numero,
                Compte.libelle,
                LigneEcriture.id,
                Ecriture.id,
                Ecriture.date_ecriture,
                Journal.code,
                Ecriture.numero,
                LigneEcriture.libelle,
                Ecriture.libelle,
                LigneEcriture.debit,
                LigneEcriture.credit,
                LigneEcriture.code_lettrage,
            )
            .select_from(LigneEcriture)
            .join(Ecriture, LigneEcriture.ecriture_id == Ecriture.id)
            .join(Journal, Ecriture.journal_id == Journal.id)
            .join(Compte, LigneEcriture.compte_id == Compte.id)
            .where(
                Ecriture.entreprise_id == self.entreprise_id,
                Ecriture.exercice_id == exercice_id,
                Ecriture.statut == StatutEcriture.VALIDEE.value,
                Ecriture.date_ecriture >= date_debut,
                Ecriture.date_ecriture <= date_fin,
            )
            .order_by(Compte.numero, Ecriture.date_ecriture, Ecriture.numero, LigneEcriture.id)
        )
        requete = self._filtre_comptes_journal(
            requete, compte_debut=compte_debut, compte_fin=compte_fin, journal_id=journal_id
        )
        return list(self.db.execute(requete).all())

    def soldes_anterieurs_grand_livre(
        self,
        exercice_id: uuid.UUID,
        *,
        avant: date,
        compte_debut: str | None = None,
        compte_fin: str | None = None,
        journal_id: uuid.UUID | None = None,
    ) -> dict[uuid.UUID, Decimal]:
        """{compte_id: solde (débit − crédit)} des écritures validées de
        l'exercice datées AVANT `avant` — point de départ du solde cumulé
        quand la période demandée ne commence pas au début de l'exercice."""
        requete = (
            select(
                Compte.id,
                func.coalesce(func.sum(LigneEcriture.debit - LigneEcriture.credit), 0),
            )
            .select_from(LigneEcriture)
            .join(Ecriture, LigneEcriture.ecriture_id == Ecriture.id)
            .join(Compte, LigneEcriture.compte_id == Compte.id)
            .where(
                Ecriture.entreprise_id == self.entreprise_id,
                Ecriture.exercice_id == exercice_id,
                Ecriture.statut == StatutEcriture.VALIDEE.value,
                Ecriture.date_ecriture < avant,
            )
            .group_by(Compte.id)
        )
        requete = self._filtre_comptes_journal(
            requete, compte_debut=compte_debut, compte_fin=compte_fin, journal_id=journal_id
        )
        return {compte_id: solde for compte_id, solde in self.db.execute(requete).all()}

    def totaux_par_classe(self, exercice_id: uuid.UUID, classes: tuple[int, ...]) -> dict[int, tuple[Decimal, Decimal]]:
        """{classe: (total_debit, total_credit)} pour les classes
        demandées — sert au compte de résultat sommaire (classes 6 et 7)."""
        requete = (
            select(
                Compte.classe,
                func.coalesce(func.sum(LigneEcriture.debit), 0),
                func.coalesce(func.sum(LigneEcriture.credit), 0),
            )
            .select_from(LigneEcriture)
            .join(Ecriture, LigneEcriture.ecriture_id == Ecriture.id)
            .join(Compte, LigneEcriture.compte_id == Compte.id)
            .where(
                Ecriture.entreprise_id == self.entreprise_id,
                Ecriture.exercice_id == exercice_id,
                Ecriture.statut == StatutEcriture.VALIDEE.value,
                Compte.classe.in_(classes),
            )
            .group_by(Compte.classe)
        )
        return {ligne[0]: (ligne[1], ligne[2]) for ligne in self.db.execute(requete).all()}

    def lignes_grand_livre(
        self, compte_id: uuid.UUID, exercice_id: uuid.UUID
    ) -> list[tuple[uuid.UUID, date, uuid.UUID, str | None, str | None, str, Decimal, Decimal]]:
        """(ligne_id, date_ecriture, ecriture_id, numero_ecriture,
        libelle_ligne, libelle_ecriture, debit, credit), triées
        chronologiquement — le solde progressif se calcule en Python (voir
        `service.py`), pas ici : une somme cumulative correcte dépend de
        l'ordre déjà appliqué, plus simple à garantir dans le code
        appelant qu'avec une fenêtre SQL. `libelle_ligne` est nullable
        (voir `LigneEcriture.libelle`) : le service retombe sur le
        libellé de l'écriture quand la ligne n'en a pas de propre."""
        requete = (
            select(
                LigneEcriture.id,
                Ecriture.date_ecriture,
                Ecriture.id,
                Ecriture.numero,
                LigneEcriture.libelle,
                Ecriture.libelle,
                LigneEcriture.debit,
                LigneEcriture.credit,
            )
            .select_from(LigneEcriture)
            .join(Ecriture, LigneEcriture.ecriture_id == Ecriture.id)
            .where(
                Ecriture.entreprise_id == self.entreprise_id,
                Ecriture.exercice_id == exercice_id,
                Ecriture.statut == StatutEcriture.VALIDEE.value,
                LigneEcriture.compte_id == compte_id,
            )
            .order_by(Ecriture.date_ecriture, Ecriture.numero)
        )
        return list(self.db.execute(requete).all())

    def lignes_echeancier(
        self, *, colonne_compte_collectif
    ) -> list[tuple[uuid.UUID, date, uuid.UUID, str | None, str, uuid.UUID, str, str, str | None, Decimal, Decimal, date | None]]:
        """Lignes NON lettrées (`code_lettrage IS NULL`) portant un tiers,
        écritures validées uniquement — base de l'échéancier et de la
        balance âgée (cahier, sections 8.4 et 13.2/13.3 ; voir
        `service.py`). `colonne_compte_collectif` sélectionne le rôle
        (`Tiers.compte_collectif_client_id` ou
        `Tiers.compte_collectif_fournisseur_id`) : le filtre compare le
        `compte_id` RÉEL de la ligne à cette colonne (et pas seulement sa
        présence sur le tiers), pour qu'un tiers "les deux" n'apparaisse
        comme client que sur les lignes effectivement portées par son
        compte collectif client, jamais mélangé avec ses lignes
        fournisseur (voir `models.py` du module tiers : pas de sous-compte
        dédié par tiers, un seul compte collectif partagé + `tiers_id`).

        Retourne (ligne_id, date_ecriture, ecriture_id, numero_ecriture,
        libelle_ecriture, tiers_id, code_tiers, raison_sociale, libelle_ligne,
        debit, credit, date_echeance), triées par date d'échéance (les
        échéances inconnues — NULL — en dernier)."""
        requete = (
            select(
                LigneEcriture.id,
                Ecriture.date_ecriture,
                Ecriture.id,
                Ecriture.numero,
                Ecriture.libelle,
                Tiers.id,
                Tiers.code,
                Tiers.raison_sociale,
                LigneEcriture.libelle,
                LigneEcriture.debit,
                LigneEcriture.credit,
                LigneEcriture.date_echeance,
            )
            .select_from(LigneEcriture)
            .join(Ecriture, LigneEcriture.ecriture_id == Ecriture.id)
            .join(Tiers, LigneEcriture.tiers_id == Tiers.id)
            .where(
                Ecriture.entreprise_id == self.entreprise_id,
                Ecriture.statut == StatutEcriture.VALIDEE.value,
                LigneEcriture.code_lettrage.is_(None),
                LigneEcriture.compte_id == colonne_compte_collectif,
            )
            .order_by(LigneEcriture.date_echeance.asc().nulls_last(), Ecriture.date_ecriture)
        )
        return list(self.db.execute(requete).all())

    # --- Tableaux de bord Direction / Comptabilité (Étape 5) ----------------
    # Même logique que les méthodes ci-dessus : agrégations en lecture seule
    # sur des modèles d'autres modules (tresorerie, exercices, portail_client),
    # consommées par `ServiceReporting.tableau_direction`/`tableau_comptabilite`.

    def comptes_bancaires_actifs(self) -> list[tuple[uuid.UUID, Decimal]]:
        """(compte_comptable_id, solde_initial) de chaque compte bancaire
        actif de l'entreprise — base du calcul de trésorerie disponible
        du tableau Direction : le solde comptable courant de chaque
        compte se retrouve ensuite via `totaux_par_compte` (déjà filtré
        sur les écritures validées), additionné à ce solde initial."""
        requete = select(CompteBancaire.compte_comptable_id, CompteBancaire.solde_initial).where(
            CompteBancaire.entreprise_id == self.entreprise_id,
            CompteBancaire.actif.is_(True),
        )
        return list(self.db.execute(requete).all())

    def compter_ecritures_brouillon(self) -> int:
        requete = (
            select(func.count())
            .select_from(Ecriture)
            .where(
                Ecriture.entreprise_id == self.entreprise_id,
                Ecriture.statut == StatutEcriture.BROUILLON.value,
            )
        )
        return self.db.scalar(requete) or 0

    def compter_lignes_bancaires_non_lettrees(self) -> int:
        """Proxy pour "rapprochements en attente" (cahier, section 22) :
        aucun concept de "rapprochement" à proprement parler dans ce
        projet (voir tresorerie/models.py), seulement des lignes de relevé
        dont le `code_lettrage` reste NULL — c'est ce compte qui sert
        d'indicateur, toutes entreprises confondues sur tous ses comptes
        bancaires (pas un seul)."""
        requete = (
            select(func.count())
            .select_from(LigneReleve)
            .join(ReleveBancaire, LigneReleve.releve_id == ReleveBancaire.id)
            .where(
                LigneReleve.entreprise_id == self.entreprise_id,
                LigneReleve.code_lettrage.is_(None),
            )
        )
        return self.db.scalar(requete) or 0

    def compter_exercices_ouverts_avant(self, seuil: date) -> int:
        requete = (
            select(func.count())
            .select_from(Exercice)
            .where(
                Exercice.entreprise_id == self.entreprise_id,
                Exercice.statut == StatutExercice.OUVERT.value,
                Exercice.date_fin <= seuil,
            )
        )
        return self.db.scalar(requete) or 0

    def compter_demandes_non_traitees(self) -> int:
        requete = (
            select(func.count())
            .select_from(DemandeDocument)
            .where(
                DemandeDocument.entreprise_id == self.entreprise_id,
                DemandeDocument.statut == StatutDemandeDocument.EN_ATTENTE.value,
            )
        )
        return self.db.scalar(requete) or 0