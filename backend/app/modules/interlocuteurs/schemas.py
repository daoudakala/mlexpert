"""Schémas Pydantic du module interlocuteurs."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class InterlocuteurCreation(BaseModel):
    nom: str = Field(min_length=1, max_length=255)
    role: str
    fonction: str | None = Field(default=None, max_length=150)
    email: str | None = Field(default=None, max_length=255)
    telephone: str | None = Field(default=None, max_length=30)
    pourcentage_detention: float | None = Field(default=None, ge=0, le=100)
    notes: str | None = Field(default=None, max_length=500)


class InterlocuteurMiseAJour(BaseModel):
    """Mise à jour partielle : seuls les champs fournis sont modifiés (voir
    `ServiceInterlocuteurs.modifier_interlocuteur`), même convention que
    `TiersMiseAJour`/`DocumentMiseAJour`."""

    nom: str | None = Field(default=None, min_length=1, max_length=255)
    role: str | None = None
    fonction: str | None = Field(default=None, max_length=150)
    email: str | None = Field(default=None, max_length=255)
    telephone: str | None = Field(default=None, max_length=30)
    pourcentage_detention: float | None = Field(default=None, ge=0, le=100)
    notes: str | None = Field(default=None, max_length=500)


class InterlocuteurLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entreprise_id: uuid.UUID
    nom: str
    role: str
    fonction: str | None
    email: str | None
    telephone: str | None
    pourcentage_detention: float | None
    notes: str | None
    actif: bool
    cree_le: datetime
