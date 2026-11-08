"""Schémas Pydantic du module exercices."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExerciceCreation(BaseModel):
    date_debut: date
    date_fin: date
    exercice_precedent_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def verifier_dates(self) -> "ExerciceCreation":
        if self.date_fin <= self.date_debut:
            raise ValueError("La date de fin doit être postérieure à la date de début.")
        return self


class ExerciceLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entreprise_id: uuid.UUID
    date_debut: date
    date_fin: date
    statut: str
    exercice_precedent_id: uuid.UUID | None
    cree_le: datetime


class PeriodeCreation(BaseModel):
    date_debut: date
    date_fin: date
    libelle: str | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def verifier_dates(self) -> "PeriodeCreation":
        if self.date_fin <= self.date_debut:
            raise ValueError("La date de fin doit être postérieure à la date de début.")
        return self


class PeriodeLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entreprise_id: uuid.UUID
    exercice_id: uuid.UUID
    libelle: str | None
    date_debut: date
    date_fin: date
    statut: str
    cree_le: datetime