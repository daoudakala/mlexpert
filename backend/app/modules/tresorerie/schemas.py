"""Schémas Pydantic du module tresorerie.

`LigneReleveSaisie.verifier_debit_xor_credit` et
`CompteBancaireReleveCreation.verifier_coherence_soldes` dupliquent des
vérifications déjà faites par `ServiceTresorerie` — même choix que dans
`comptabilite/schemas.py` : un 422 clair avant le service plutôt qu'une
exception métier générique, pour le même contrôle.

`ReleveMiseAJour` ne duplique volontairement PAS la cohérence des
soldes : une mise à jour est partielle (solde ou lignes peuvent être
fournis séparément), et vérifier la cohérence demanderait de connaître
l'état actuel du relevé, que le schéma n'a pas — cette vérification-là
reste entièrement du ressort du service.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CompteBancaireCreation(BaseModel):
    journal_id: uuid.UUID
    compte_comptable_id: uuid.UUID
    libelle: str = Field(min_length=2, max_length=150)
    banque: str | None = Field(default=None, max_length=150)
    numero_compte: str | None = Field(default=None, max_length=50)
    iban: str | None = Field(default=None, max_length=50)
    solde_initial: Decimal = Field(default=Decimal("0"))


class CompteBancaireLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entreprise_id: uuid.UUID
    journal_id: uuid.UUID
    compte_comptable_id: uuid.UUID
    libelle: str
    banque: str | None
    numero_compte: str | None
    iban: str | None
    solde_initial: Decimal
    actif: bool
    cree_le: datetime


class LigneReleveSaisie(BaseModel):
    date_operation: date
    libelle: str = Field(min_length=1, max_length=255)
    debit: Decimal = Field(default=Decimal("0"), ge=0)
    credit: Decimal = Field(default=Decimal("0"), ge=0)
    reference: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def verifier_debit_xor_credit(self) -> "LigneReleveSaisie":
        if (self.debit > 0) == (self.credit > 0):
            raise ValueError(
                "Une ligne de relevé doit être soit débitrice, soit créditrice "
                "(jamais les deux, jamais ni l'une ni l'autre)."
            )
        return self


class LigneReleveLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    date_operation: date
    libelle: str
    reference: str | None
    debit: Decimal
    credit: Decimal
    code_lettrage: str | None


class ReleveCreation(BaseModel):
    date_debut: date
    date_fin: date
    solde_debut: Decimal
    solde_fin: Decimal
    reference: str | None = Field(default=None, max_length=100)
    lignes: list[LigneReleveSaisie] = Field(min_length=1)

    @model_validator(mode="after")
    def verifier_dates(self) -> "ReleveCreation":
        if self.date_fin <= self.date_debut:
            raise ValueError("La date de fin doit être postérieure à la date de début.")
        return self

    @model_validator(mode="after")
    def verifier_coherence_soldes(self) -> "ReleveCreation":
        mouvement = sum((l.credit - l.debit for l in self.lignes), Decimal("0"))
        if self.solde_debut + mouvement != self.solde_fin:
            raise ValueError(
                f"Le solde de fin ({self.solde_fin}) ne correspond pas au solde de "
                f"début ({self.solde_debut}) plus le mouvement des lignes ({mouvement})."
            )
        return self


class ReleveMiseAJour(BaseModel):
    solde_debut: Decimal | None = None
    solde_fin: Decimal | None = None
    reference: str | None = Field(default=None, max_length=100)
    lignes: list[LigneReleveSaisie] | None = Field(default=None, min_length=1)


class ReleveLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entreprise_id: uuid.UUID
    compte_bancaire_id: uuid.UUID
    date_debut: date
    date_fin: date
    solde_debut: Decimal
    solde_fin: Decimal
    reference: str | None
    cree_le: datetime


class ReleveAvecLignes(ReleveLecture):
    lignes: list[LigneReleveLecture] = []


class RapprochementDemande(BaseModel):
    ligne_releve_ids: list[uuid.UUID] = Field(min_length=1)
    ligne_ecriture_ids: list[uuid.UUID] = Field(min_length=1)


class RapprochementReponse(BaseModel):
    code_lettrage: str


class AnnulationRapprochementDemande(BaseModel):
    code_lettrage: str = Field(min_length=1, max_length=20)