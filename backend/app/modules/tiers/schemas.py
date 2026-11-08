"""Schémas Pydantic du module tiers."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TiersCreation(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    raison_sociale: str = Field(min_length=2, max_length=255)
    nif: str | None = Field(default=None, max_length=50)
    rccm: str | None = Field(default=None, max_length=50)
    adresse: str | None = None
    email: str | None = Field(default=None, max_length=255)
    telephone: str | None = Field(default=None, max_length=30)
    delai_paiement_jours: int | None = Field(default=None, ge=0)
    plafond_credit: Decimal | None = Field(default=None, ge=0)
    compte_collectif_client_id: uuid.UUID | None = None
    compte_collectif_fournisseur_id: uuid.UUID | None = None
    # Voir `ServiceTiers.creer_tiers` : un NIF déjà vu ne bloque pas la
    # création, seulement une première tentative sans confirmation.
    confirmer_malgre_doublon: bool = False

    @model_validator(mode="after")
    def verifier_au_moins_un_role(self) -> "TiersCreation":
        if self.compte_collectif_client_id is None and self.compte_collectif_fournisseur_id is None:
            raise ValueError("Un tiers doit être client, fournisseur, ou les deux.")
        return self


class TiersMiseAJour(BaseModel):
    """Mise à jour partielle : seuls les champs fournis sont modifiés
    (voir `ServiceTiers.modifier_tiers`). `code` et les comptes collectifs
    ne se modifient pas par cette route (voir `TiersComptesCollectifs`)."""

    raison_sociale: str | None = Field(default=None, min_length=2, max_length=255)
    nif: str | None = Field(default=None, max_length=50)
    rccm: str | None = Field(default=None, max_length=50)
    adresse: str | None = None
    email: str | None = Field(default=None, max_length=255)
    telephone: str | None = Field(default=None, max_length=30)
    delai_paiement_jours: int | None = Field(default=None, ge=0)
    plafond_credit: Decimal | None = Field(default=None, ge=0)


class TiersComptesCollectifs(BaseModel):
    """Les deux valeurs sont toujours remplacées ensemble (voir
    `ServiceTiers.modifier_comptes_collectifs`)."""

    compte_collectif_client_id: uuid.UUID | None
    compte_collectif_fournisseur_id: uuid.UUID | None

    @model_validator(mode="after")
    def verifier_au_moins_un_role(self) -> "TiersComptesCollectifs":
        if self.compte_collectif_client_id is None and self.compte_collectif_fournisseur_id is None:
            raise ValueError("Un tiers doit être client, fournisseur, ou les deux.")
        return self


class TiersLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entreprise_id: uuid.UUID
    code: str
    raison_sociale: str
    nif: str | None
    rccm: str | None
    adresse: str | None
    email: str | None
    telephone: str | None
    delai_paiement_jours: int | None
    plafond_credit: Decimal | None
    actif: bool
    compte_collectif_client_id: uuid.UUID | None
    compte_collectif_fournisseur_id: uuid.UUID | None
    est_client: bool
    est_fournisseur: bool
    cree_le: datetime