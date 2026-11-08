"""Règles métier du module provisions.

`ServiceProvisions` : construit avec `(db, entreprise_id)`, comme
`ServiceImmobilisations`.

Contrairement au plan d'amortissement (calculé puis comptabilisé en deux
temps), une dotation ou une reprise de provision est une opération
comptable immédiate : `constituer_provision`/`reprendre_provision`
créent l'écriture ET le `MouvementProvision` en un seul appel — il n'y a
pas de phase "prévue" séparée (voir la note de tête de fichier de
`models.py`).

Vérification de classe de compte à la création de la fiche, sur le
même principe que `immobilisations` (`CLASSE_COMPTE_IMMOBILISATION`/
`CLASSE_COMPTE_DOTATION`) : `compte_dotation_id` doit être une charge
(classe 6), `compte_reprise_id` un produit (classe 7), et
`compte_provision_id` la classe attendue selon le TYPE de provision —
classe 4 (comptes de tiers) pour une dépréciation de créance, classe 3
pour une dépréciation de stock, classe 1 pour une provision pour risques
et charges (passif) — d'où `CLASSE_PROVISION_PAR_TYPE` plutôt qu'une
classe unique.

Une reprise ne peut jamais dépasser `montant_actuel` : le service
refuse plutôt que de laisser le solde de la provision devenir négatif.
Une dotation ultérieure sur une provision déjà `soldee` la fait
redevenir `active` (une provision soldée n'est pas un état terminal,
contrairement à une immobilisation cédée/réformée)."""

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import RessourceIntrouvable, ValidationMetier
from app.modules.comptabilite.models import Ecriture
from app.modules.comptabilite.repository import RepositoryComptes
from app.modules.comptabilite.service import LigneSaisie, ServiceComptabilite
from app.modules.exercices.models import Exercice, StatutExercice
from app.modules.exercices.repository import RepositoryExercice
from app.modules.journal_activite.models import TypeAction
from app.modules.journal_activite.service import ServiceJournalActivite
from app.modules.provisions.models import (
    MouvementProvision,
    Provision,
    StatutProvision,
    TypeMouvementProvision,
    TypeProvision,
)
from app.modules.provisions.repository import RepositoryMouvementsProvision, RepositoryProvisions
from app.modules.tiers.repository import RepositoryTiers

CLASSE_COMPTE_CHARGE = 6
CLASSE_COMPTE_PRODUIT = 7
CLASSE_PROVISION_PAR_TYPE: dict[str, int] = {
    TypeProvision.DEPRECIATION_CREANCE.value: 4,
    TypeProvision.DEPRECIATION_STOCK.value: 3,
    TypeProvision.RISQUE_CHARGE.value: 1,
}


@dataclass
class ProvisionCreation:
    libelle: str
    type_provision: TypeProvision
    compte_dotation_id: uuid.UUID
    compte_provision_id: uuid.UUID
    compte_reprise_id: uuid.UUID
    tiers_id: uuid.UUID | None = None


class ServiceProvisions:
    def __init__(self, db: Session, entreprise_id: uuid.UUID) -> None:
        self.db = db
        self.entreprise_id = entreprise_id
        self.provisions = RepositoryProvisions(db, entreprise_id)
        self.mouvements = RepositoryMouvementsProvision(db, entreprise_id)
        self.comptes = RepositoryComptes(db, entreprise_id)
        self.exercices = RepositoryExercice(db, entreprise_id)
        self.tiers = RepositoryTiers(db, entreprise_id)
        self.journal_activite = ServiceJournalActivite(db)

    # --- Provisions ------------------------------------------------------------

    def creer_provision(self, donnees: ProvisionCreation, *, auteur_id: uuid.UUID) -> Provision:
        compte_dotation = self._obtenir_compte_ou_lever(donnees.compte_dotation_id)
        self._verifier_classe(compte_dotation, CLASSE_COMPTE_CHARGE, "de charge (dotation)")
        compte_reprise = self._obtenir_compte_ou_lever(donnees.compte_reprise_id)
        self._verifier_classe(compte_reprise, CLASSE_COMPTE_PRODUIT, "de produit (reprise)")
        compte_provision = self._obtenir_compte_ou_lever(donnees.compte_provision_id)
        classe_attendue = CLASSE_PROVISION_PAR_TYPE[donnees.type_provision.value]
        self._verifier_classe(compte_provision, classe_attendue, "de provision pour ce type")

        if donnees.tiers_id is not None and self.tiers.obtenir(donnees.tiers_id) is None:
            raise RessourceIntrouvable("Tiers introuvable.")

        provision = Provision(
            libelle=donnees.libelle,
            type_provision=donnees.type_provision.value,
            tiers_id=donnees.tiers_id,
            compte_dotation_id=donnees.compte_dotation_id,
            compte_provision_id=donnees.compte_provision_id,
            compte_reprise_id=donnees.compte_reprise_id,
            montant_actuel=Decimal("0"),
            statut=StatutProvision.ACTIVE.value,
        )
        self.provisions.ajouter(provision)
        self.journal_activite.enregistrer(
            module="provisions",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Provision",
            objet_id=provision.id,
            description=f"Création de la provision '{donnees.libelle}' ({donnees.type_provision.value}).",
            valeurs_apres={"libelle": donnees.libelle, "type_provision": donnees.type_provision.value},
        )
        return provision

    def modifier_provision(
        self,
        provision_id: uuid.UUID,
        *,
        auteur_id: uuid.UUID,
        libelle: str | None = None,
        tiers_id: uuid.UUID | None = None,
    ) -> Provision:
        """Mise à jour volontairement limitée aux champs descriptifs — même
        raisonnement que `ServiceImmobilisations.modifier_immobilisation` :
        changer les comptes ou le type invaliderait les mouvements déjà
        enregistrés."""
        provision = self._obtenir_provision_ou_lever(provision_id)
        if tiers_id is not None and self.tiers.obtenir(tiers_id) is None:
            raise RessourceIntrouvable("Tiers introuvable.")

        if libelle is not None:
            provision.libelle = libelle
        if tiers_id is not None:
            provision.tiers_id = tiers_id
        self.db.flush()

        self.journal_activite.enregistrer(
            module="provisions",
            type_action=TypeAction.MODIFIER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Provision",
            objet_id=provision.id,
            description=f"Modification de la provision '{provision.libelle}'.",
        )
        return provision

    def obtenir_provision(self, provision_id: uuid.UUID) -> Provision:
        return self._obtenir_provision_ou_lever(provision_id)

    def lister_provisions(
        self, *, type_provision: str | None = None, statut: str | None = None
    ) -> list[Provision]:
        return self.provisions.lister(type_provision=type_provision, statut=statut)

    # --- Mouvements (dotation / reprise) ---------------------------------------

    def constituer_provision(
        self,
        provision_id: uuid.UUID,
        *,
        exercice_id: uuid.UUID,
        journal_id: uuid.UUID,
        date_mouvement: date,
        montant: Decimal,
        auteur_id: uuid.UUID,
    ) -> Ecriture:
        provision = self._obtenir_provision_ou_lever(provision_id)
        exercice = self._obtenir_exercice_ouvert_ou_lever(exercice_id)

        service_comptabilite = ServiceComptabilite(self.db, self.entreprise_id)
        ecriture = service_comptabilite.creer_ecriture(
            auteur_id=auteur_id,
            journal_id=journal_id,
            exercice_id=exercice_id,
            date_ecriture=date_mouvement,
            libelle=f"Dotation provision {provision.libelle} - exercice {exercice.date_debut.year}",
            lignes=[
                LigneSaisie(compte_id=provision.compte_dotation_id, debit=montant),
                LigneSaisie(compte_id=provision.compte_provision_id, credit=montant),
            ],
        )

        mouvement = MouvementProvision(
            provision_id=provision.id,
            exercice_id=exercice_id,
            type_mouvement=TypeMouvementProvision.DOTATION.value,
            montant=montant,
            date_mouvement=date_mouvement,
            ecriture_id=ecriture.id,
        )
        self.mouvements.ajouter(mouvement)

        provision.montant_actuel += montant
        provision.statut = StatutProvision.ACTIVE.value
        self.db.flush()

        self.journal_activite.enregistrer(
            module="provisions",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="MouvementProvision",
            objet_id=mouvement.id,
            description=f"Dotation de {montant} pour la provision '{provision.libelle}'.",
            valeurs_apres={"ecriture_id": str(ecriture.id), "montant_actuel": str(provision.montant_actuel)},
        )
        return ecriture

    def reprendre_provision(
        self,
        provision_id: uuid.UUID,
        *,
        exercice_id: uuid.UUID,
        journal_id: uuid.UUID,
        date_mouvement: date,
        montant: Decimal,
        auteur_id: uuid.UUID,
    ) -> Ecriture:
        provision = self._obtenir_provision_ou_lever(provision_id)
        if montant > provision.montant_actuel:
            raise ValidationMetier(
                f"Le montant de la reprise ({montant}) ne peut pas dépasser le montant "
                f"actuel de la provision ({provision.montant_actuel})."
            )
        exercice = self._obtenir_exercice_ouvert_ou_lever(exercice_id)

        service_comptabilite = ServiceComptabilite(self.db, self.entreprise_id)
        ecriture = service_comptabilite.creer_ecriture(
            auteur_id=auteur_id,
            journal_id=journal_id,
            exercice_id=exercice_id,
            date_ecriture=date_mouvement,
            libelle=f"Reprise provision {provision.libelle} - exercice {exercice.date_debut.year}",
            lignes=[
                LigneSaisie(compte_id=provision.compte_provision_id, debit=montant),
                LigneSaisie(compte_id=provision.compte_reprise_id, credit=montant),
            ],
        )

        mouvement = MouvementProvision(
            provision_id=provision.id,
            exercice_id=exercice_id,
            type_mouvement=TypeMouvementProvision.REPRISE.value,
            montant=montant,
            date_mouvement=date_mouvement,
            ecriture_id=ecriture.id,
        )
        self.mouvements.ajouter(mouvement)

        provision.montant_actuel -= montant
        provision.statut = (
            StatutProvision.SOLDEE.value if provision.montant_actuel == 0 else StatutProvision.ACTIVE.value
        )
        self.db.flush()

        self.journal_activite.enregistrer(
            module="provisions",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="MouvementProvision",
            objet_id=mouvement.id,
            description=f"Reprise de {montant} pour la provision '{provision.libelle}'.",
            valeurs_apres={"ecriture_id": str(ecriture.id), "montant_actuel": str(provision.montant_actuel)},
        )
        return ecriture

    def lister_mouvements(self, provision_id: uuid.UUID) -> list[MouvementProvision]:
        self._obtenir_provision_ou_lever(provision_id)
        return self.mouvements.lister_pour_provision(provision_id)

    # --- Aides internes ----------------------------------------------------------

    def _obtenir_provision_ou_lever(self, provision_id: uuid.UUID) -> Provision:
        provision = self.provisions.obtenir(provision_id)
        if provision is None:
            raise RessourceIntrouvable("Provision introuvable.")
        return provision

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

    def _obtenir_exercice_ouvert_ou_lever(self, exercice_id: uuid.UUID) -> Exercice:
        exercice = self.exercices.obtenir(exercice_id)
        if exercice is None:
            raise RessourceIntrouvable("Exercice introuvable.")
        if exercice.statut != StatutExercice.OUVERT.value:
            raise ValidationMetier("Impossible d'enregistrer un mouvement sur un exercice clôturé.")
        return exercice