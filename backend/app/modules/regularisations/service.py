"""Règles métier du module regularisations.

`ServiceRegularisations` : construit avec `(db, entreprise_id)`, comme
`ServiceProvisions`.

Génère l'écriture de régularisation, selon 4 cas :

- CCA (charge constatée d'avance) : débit du compte de régularisation
  (476), crédit du compte de charge d'origine — RETIRE du résultat de
  l'exercice la part de la charge qui concerne l'exercice suivant.
- PCA (produit constaté d'avance) : débit du compte de produit
  d'origine, crédit du compte de régularisation (477) — RETIRE du
  résultat la part du produit qui concerne l'exercice suivant.
- Charge à payer (FNP) : débit du compte de charge d'origine, crédit du
  compte de régularisation (408) — AJOUTE au résultat de l'exercice une
  charge pas encore facturée mais qui lui appartient.
- Produit à recevoir : débit du compte de régularisation (418), crédit
  du compte de produit d'origine — AJOUTE au résultat de l'exercice un
  produit pas encore facturé mais qui lui appartient.

Autrement dit, charge à payer / produit à recevoir sont le miroir exact
de CCA/PCA : même paire de classes de comptes par type (`CLASSE_ORIGINE_PAR_TYPE`),
mais le sens débit/crédit s'inverse puisqu'il s'agit d'ajouter plutôt que
de retirer.

`compte_origine_id` doit être une charge (classe 6) pour une CCA ou une
charge à payer, un produit (classe 7) pour une PCA ou un produit à
recevoir. `compte_regularisation_id` doit toujours être classe 4, quel
que soit le type (476, 477, 408, 418 sont tous des comptes de
régularisation de bilan).

L'extourne au début de l'exercice suivant n'est pas traitée ici : voir la
note de tête de fichier de `models.py` — c'est `ServiceComptabilite.extourner_ecriture`,
déjà existant, qui s'en charge, sur l'écriture générée ici.
"""

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import RessourceIntrouvable, ValidationMetier
from app.modules.comptabilite.models import Ecriture
from app.modules.comptabilite.repository import RepositoryComptes
from app.modules.comptabilite.service import LigneSaisie, ServiceComptabilite
from app.modules.exercices.models import StatutExercice
from app.modules.exercices.repository import RepositoryExercice
from app.modules.journal_activite.models import TypeAction
from app.modules.journal_activite.service import ServiceJournalActivite
from app.modules.regularisations.models import Regularisation, TypeRegularisation
from app.modules.regularisations.repository import RepositoryRegularisations

CLASSE_COMPTE_REGULARISATION = 4
CLASSE_ORIGINE_PAR_TYPE: dict[str, int] = {
    TypeRegularisation.CHARGE_CONSTATEE_AVANCE.value: 6,
    TypeRegularisation.PRODUIT_CONSTATE_AVANCE.value: 7,
    TypeRegularisation.CHARGE_A_PAYER.value: 6,
    TypeRegularisation.PRODUIT_A_RECEVOIR.value: 7,
}

# Libellé affiché en préfixe de l'écriture générée, par type.
PREFIXE_LIBELLE_PAR_TYPE: dict[str, str] = {
    TypeRegularisation.CHARGE_CONSTATEE_AVANCE.value: "Charge constatée d'avance",
    TypeRegularisation.PRODUIT_CONSTATE_AVANCE.value: "Produit constaté d'avance",
    TypeRegularisation.CHARGE_A_PAYER.value: "Charge à payer",
    TypeRegularisation.PRODUIT_A_RECEVOIR.value: "Produit à recevoir",
}

# Sens de l'écriture par type : True si le compte d'ORIGINE est débité
# (et le compte de régularisation crédité), False si c'est l'inverse.
# CCA et produit à recevoir débitent la régularisation ; charge à payer
# et PCA débitent l'origine — voir la docstring de tête de fichier.
ORIGINE_AU_DEBIT_PAR_TYPE: dict[str, bool] = {
    TypeRegularisation.CHARGE_CONSTATEE_AVANCE.value: False,
    TypeRegularisation.PRODUIT_CONSTATE_AVANCE.value: True,
    TypeRegularisation.CHARGE_A_PAYER.value: True,
    TypeRegularisation.PRODUIT_A_RECEVOIR.value: False,
}


@dataclass
class RegularisationCreation:
    libelle: str
    type_regularisation: TypeRegularisation
    exercice_id: uuid.UUID
    compte_origine_id: uuid.UUID
    compte_regularisation_id: uuid.UUID
    journal_id: uuid.UUID
    date_regularisation: date
    montant: Decimal


class ServiceRegularisations:
    def __init__(self, db: Session, entreprise_id: uuid.UUID) -> None:
        self.db = db
        self.entreprise_id = entreprise_id
        self.regularisations = RepositoryRegularisations(db, entreprise_id)
        self.comptes = RepositoryComptes(db, entreprise_id)
        self.exercices = RepositoryExercice(db, entreprise_id)
        self.journal_activite = ServiceJournalActivite(db)

    def creer_regularisation(
        self, donnees: RegularisationCreation, *, auteur_id: uuid.UUID
    ) -> Regularisation:
        compte_origine = self._obtenir_compte_ou_lever(donnees.compte_origine_id)
        classe_attendue = CLASSE_ORIGINE_PAR_TYPE[donnees.type_regularisation.value]
        self._verifier_classe(compte_origine, classe_attendue, "d'origine pour ce type")
        compte_regularisation = self._obtenir_compte_ou_lever(donnees.compte_regularisation_id)
        self._verifier_classe(compte_regularisation, CLASSE_COMPTE_REGULARISATION, "de régularisation")

        exercice = self.exercices.obtenir(donnees.exercice_id)
        if exercice is None:
            raise RessourceIntrouvable("Exercice introuvable.")
        if exercice.statut != StatutExercice.OUVERT.value:
            raise ValidationMetier("Impossible d'enregistrer une régularisation sur un exercice clôturé.")

        origine_au_debit = ORIGINE_AU_DEBIT_PAR_TYPE[donnees.type_regularisation.value]
        if origine_au_debit:
            lignes = [
                LigneSaisie(compte_id=donnees.compte_origine_id, debit=donnees.montant),
                LigneSaisie(compte_id=donnees.compte_regularisation_id, credit=donnees.montant),
            ]
        else:
            lignes = [
                LigneSaisie(compte_id=donnees.compte_regularisation_id, debit=donnees.montant),
                LigneSaisie(compte_id=donnees.compte_origine_id, credit=donnees.montant),
            ]
        prefixe_libelle = PREFIXE_LIBELLE_PAR_TYPE[donnees.type_regularisation.value]

        service_comptabilite = ServiceComptabilite(self.db, self.entreprise_id)
        ecriture = service_comptabilite.creer_ecriture(
            auteur_id=auteur_id,
            journal_id=donnees.journal_id,
            exercice_id=donnees.exercice_id,
            date_ecriture=donnees.date_regularisation,
            libelle=f"{prefixe_libelle} - {donnees.libelle}",
            lignes=lignes,
        )

        regularisation = Regularisation(
            libelle=donnees.libelle,
            type_regularisation=donnees.type_regularisation.value,
            exercice_id=donnees.exercice_id,
            compte_origine_id=donnees.compte_origine_id,
            compte_regularisation_id=donnees.compte_regularisation_id,
            montant=donnees.montant,
            date_regularisation=donnees.date_regularisation,
            ecriture_id=ecriture.id,
        )
        self.regularisations.ajouter(regularisation)

        self.journal_activite.enregistrer(
            module="regularisations",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Regularisation",
            objet_id=regularisation.id,
            description=f"Régularisation '{donnees.libelle}' ({donnees.type_regularisation.value}) : {donnees.montant}.",
            valeurs_apres={"ecriture_id": str(ecriture.id), "montant": str(donnees.montant)},
        )
        return regularisation

    def obtenir_regularisation(self, regularisation_id: uuid.UUID) -> Regularisation:
        regularisation = self.regularisations.obtenir(regularisation_id)
        if regularisation is None:
            raise RessourceIntrouvable("Régularisation introuvable.")
        return regularisation

    def lister_regularisations(
        self, *, type_regularisation: str | None = None, exercice_id: uuid.UUID | None = None
    ) -> list[Regularisation]:
        return self.regularisations.lister(type_regularisation=type_regularisation, exercice_id=exercice_id)

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