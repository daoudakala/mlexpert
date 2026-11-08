"""Schémas Pydantic du module entreprises."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EntrepriseCreation(BaseModel):
    raison_sociale: str = Field(min_length=1, max_length=255)
    sigle: str | None = Field(default=None, max_length=50)
    forme_juridique: str | None = Field(default=None, max_length=100)
    activite: str | None = Field(default=None, max_length=255)
    adresse: str | None = None
    email_contact: str | None = None
    telephone_contact: str | None = Field(default=None, max_length=30)
    referentiel_comptable: str = Field(default="SYSCOHADA", max_length=50)
    devise: str = Field(default="XOF", min_length=3, max_length=3)
    secteur: str | None = Field(default=None, max_length=100)
    taille: str | None = Field(default=None, max_length=50)
    niveau_risque: str | None = Field(default=None, max_length=50)
    priorite: str | None = Field(default=None, max_length=50)
    blocage_ecritures_cloture: bool = True


class EntrepriseMiseAJour(BaseModel):
    raison_sociale: str | None = Field(default=None, min_length=1, max_length=255)
    sigle: str | None = Field(default=None, max_length=50)
    forme_juridique: str | None = Field(default=None, max_length=100)
    activite: str | None = Field(default=None, max_length=255)
    adresse: str | None = None
    email_contact: str | None = None
    telephone_contact: str | None = Field(default=None, max_length=30)
    referentiel_comptable: str | None = Field(default=None, max_length=50)
    devise: str | None = Field(default=None, min_length=3, max_length=3)
    secteur: str | None = Field(default=None, max_length=100)
    taille: str | None = Field(default=None, max_length=50)
    niveau_risque: str | None = Field(default=None, max_length=50)
    priorite: str | None = Field(default=None, max_length=50)
    blocage_ecritures_cloture: bool | None = None


class EntrepriseLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    raison_sociale: str
    sigle: str | None
    forme_juridique: str | None
    activite: str | None
    adresse: str | None
    email_contact: str | None
    telephone_contact: str | None
    referentiel_comptable: str
    devise: str
    secteur: str | None
    taille: str | None
    niveau_risque: str | None
    priorite: str | None
    statut: str
    blocage_ecritures_cloture: bool
    cree_le: datetime