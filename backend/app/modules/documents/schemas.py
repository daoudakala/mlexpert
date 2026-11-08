"""Schémas Pydantic du module documents.

Pas de schéma de création à corps JSON : le dépôt se fait par upload
multipart (`fichier: UploadFile` + champs `Form(...)`, voir `router.py`),
pas par un `BaseModel` — un fichier binaire ne se prête pas à un corps
JSON. `DocumentMiseAJour`, en revanche, ne touche que des métadonnées et
reste un JSON classique.
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.documents.models import CategorieDocument


class DocumentMiseAJour(BaseModel):
    categorie: CategorieDocument | None = None
    description: str | None = Field(default=None, max_length=500)
    date_document: date | None = None
    date_expiration: date | None = None


class DocumentLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entreprise_id: uuid.UUID
    categorie: str
    nom_fichier: str
    type_mime: str
    taille_octets: int
    description: str | None
    date_document: date | None
    date_expiration: date | None
    exercice_id: uuid.UUID | None
    depose_par_id: uuid.UUID
    visible_client: bool
    tiers_id: uuid.UUID | None
    ecriture_id: uuid.UUID | None
    cree_le: datetime


class DocumentRattachementEcriture(BaseModel):
    ecriture_id: uuid.UUID