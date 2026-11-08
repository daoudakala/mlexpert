"""Schémas Pydantic du module paie.

Mêmes conventions que `immobilisations`/`tresorerie` : les schémas de
création dupliquent une partie des vérifications déjà faites par
`ServicePaie` (montants positifs, cohérence des dates, période fin >
début) pour un 422 immédiat, avant même d'atteindre le service.

`BulletinCreation.lignes` réutilise le même schéma `LigneBulletinSaisie`
que pour une mise à jour (`BulletinMiseAJourLignes`) : dans les deux cas,
c'est une liste de (rubrique, montant) à revalider et retotaliser.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.paie.models import TypeRubriquePaie


# --- Employés ----------------------------------------------------------------


class EmployeCreation(BaseModel):
    matricule: str = Field(min_length=1, max_length=30)
    nom: str = Field(min_length=1, max_length=100)
    prenom: str = Field(min_length=1, max_length=100)
    poste: str | None = Field(default=None, max_length=150)
    date_embauche: date
    salaire_base: Decimal = Field(gt=0)


class EmployeMiseAJour(BaseModel):
    nom: str | None = Field(default=None, min_length=1, max_length=100)
    prenom: str | None = Field(default=None, min_length=1, max_length=100)
    poste: str | None = Field(default=None, max_length=150)
    salaire_base: Decimal | None = Field(default=None, gt=0)


class EmployeDesactivation(BaseModel):
    date_sortie: date


class EmployeLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entreprise_id: uuid.UUID
    matricule: str
    nom: str
    prenom: str
    poste: str | None
    date_embauche: date
    date_sortie: date | None
    salaire_base: Decimal
    statut: str
    cree_le: datetime


# --- Rubriques de paie ---------------------------------------------------------


class RubriquePaieCreation(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    libelle: str = Field(min_length=1, max_length=150)
    type_rubrique: TypeRubriquePaie
    # Optionnel à la création : une rubrique reste utilisable pour saisir
    # des bulletins sans compte affecté — seule la génération d'écriture
    # l'exige (voir `ServicePaie.generer_ecriture_bulletin`).
    compte_comptable_id: uuid.UUID | None = None


class RubriqueCompteComptable(BaseModel):
    compte_comptable_id: uuid.UUID


class RubriquePaieLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entreprise_id: uuid.UUID
    code: str
    libelle: str
    type_rubrique: str
    actif: bool
    compte_comptable_id: uuid.UUID | None


# --- Bulletins de paie ---------------------------------------------------------


class LigneBulletinSaisie(BaseModel):
    rubrique_id: uuid.UUID
    montant: Decimal = Field(ge=0)
    libelle: str | None = Field(default=None, max_length=255)


class BulletinCreation(BaseModel):
    employe_id: uuid.UUID
    exercice_id: uuid.UUID
    periode_debut: date
    periode_fin: date
    lignes: list[LigneBulletinSaisie] = Field(min_length=1)

    @model_validator(mode="after")
    def verifier_periode(self) -> "BulletinCreation":
        if self.periode_fin <= self.periode_debut:
            raise ValueError("La période de fin doit être postérieure à la période de début.")
        return self


class BulletinMiseAJourLignes(BaseModel):
    lignes: list[LigneBulletinSaisie] = Field(min_length=1)


class LigneBulletinLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    bulletin_id: uuid.UUID
    rubrique_id: uuid.UUID
    libelle: str | None
    montant: Decimal


class BulletinLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entreprise_id: uuid.UUID
    employe_id: uuid.UUID
    exercice_id: uuid.UUID
    periode_debut: date
    periode_fin: date
    statut: str
    salaire_brut: Decimal
    total_retenues: Decimal
    net_a_payer: Decimal
    ecriture_id: uuid.UUID | None
    cree_le: datetime


class GenerationEcritureBulletinDemande(BaseModel):
    """Le journal et le compte de net-à-payer sont fournis à l'appel plutôt
    que déduits : voir la note de `ServicePaie.generer_ecriture_bulletin`."""

    journal_id: uuid.UUID
    compte_net_a_payer_id: uuid.UUID