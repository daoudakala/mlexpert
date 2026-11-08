"""Schémas Pydantic du module provisions.

Pas de schéma de saisie pour `MouvementProvision` au sens d'un CRUD
libre : un mouvement se DÉCLENCHE (`DotationDemande` / `RepriseDemande`),
il ne se crée pas depuis un corps de requête arbitraire — même principe
que `LigneAmortissement` dans `immobilisations/schemas.py`.
"""

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.provisions.models import TypeProvision


class ProvisionCreation(BaseModel):
    libelle: str = Field(min_length=2, max_length=255)
    type_provision: TypeProvision
    tiers_id: uuid.UUID | None = None
    compte_dotation_id: uuid.UUID
    compte_provision_id: uuid.UUID
    compte_reprise_id: uuid.UUID


class ProvisionMiseAJour(BaseModel):
    """Volontairement limité aux champs descriptifs, sur le modèle de
    `ImmobilisationMiseAJour` — les comptes et le type ne se changent pas
    après coup (des mouvements peuvent déjà s'appuyer dessus)."""

    libelle: str | None = Field(default=None, min_length=2, max_length=255)
    tiers_id: uuid.UUID | None = None


class ProvisionLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entreprise_id: uuid.UUID
    libelle: str
    type_provision: str
    tiers_id: uuid.UUID | None
    compte_dotation_id: uuid.UUID
    compte_provision_id: uuid.UUID
    compte_reprise_id: uuid.UUID
    montant_actuel: Decimal
    statut: str


class MouvementProvisionLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provision_id: uuid.UUID
    exercice_id: uuid.UUID
    type_mouvement: str
    montant: Decimal
    date_mouvement: date
    ecriture_id: uuid.UUID


class DotationDemande(BaseModel):
    exercice_id: uuid.UUID
    journal_id: uuid.UUID
    date_mouvement: date
    montant: Decimal = Field(gt=0)


class RepriseDemande(BaseModel):
    exercice_id: uuid.UUID
    journal_id: uuid.UUID
    date_mouvement: date
    montant: Decimal = Field(gt=0)