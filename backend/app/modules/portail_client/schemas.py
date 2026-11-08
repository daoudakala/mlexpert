"""Schémas Pydantic du module portail_client.

Pas de schéma dédié pour les documents visibles : `DocumentLecture` du
module `documents` est réutilisé tel quel (mêmes champs, seul le filtre
`visible_client` change côté service) — inutile de dupliquer un schéma
identique.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DemandeDocumentCreation(BaseModel):
    libelle: str = Field(min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=500)


class DemandeDocumentTraitement(BaseModel):
    document_id: uuid.UUID


class DemandeDocumentRefus(BaseModel):
    motif: str = Field(min_length=2, max_length=500)


class DemandeDocumentLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entreprise_id: uuid.UUID
    libelle: str
    description: str | None
    statut: str
    reponse: str | None
    demandeur_id: uuid.UUID
    document_id: uuid.UUID | None
    traitee_par_id: uuid.UUID | None
    traitee_le: datetime | None
    cree_le: datetime


class CommentaireDemandeCreation(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class CommentaireDemandeLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    demande_id: uuid.UUID
    auteur_id: uuid.UUID
    message: str
    cree_le: datetime