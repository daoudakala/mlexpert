"""Schémas Pydantic du module regularisations.

Une seule opération de saisie (`RegularisationCreation`) : la régularisation
ET son écriture naissent ensemble (voir `models.py`), il n'y a donc pas de
distinction création de fiche / génération d'écriture comme pour
`immobilisations` ou `provisions`.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.regularisations.models import TypeRegularisation


class RegularisationCreation(BaseModel):
    libelle: str = Field(min_length=2, max_length=255)
    type_regularisation: TypeRegularisation
    exercice_id: uuid.UUID
    compte_origine_id: uuid.UUID
    compte_regularisation_id: uuid.UUID
    journal_id: uuid.UUID
    date_regularisation: date
    montant: Decimal = Field(gt=0)


class RegularisationLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entreprise_id: uuid.UUID
    libelle: str
    type_regularisation: str
    exercice_id: uuid.UUID
    compte_origine_id: uuid.UUID
    compte_regularisation_id: uuid.UUID
    montant: Decimal
    date_regularisation: date
    ecriture_id: uuid.UUID
    cree_le: datetime