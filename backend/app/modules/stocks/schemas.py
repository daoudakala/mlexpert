"""Schémas Pydantic du module stocks.

Même convention que `paie`/`immobilisations` : les schémas de création
dupliquent les vérifications de base déjà faites par `ServiceStocks`
(quantités et coûts positifs) pour un 422 immédiat.

Deux schémas de création de mouvement distincts (`MouvementEntreeCreation`
et `MouvementSortieCreation`) plutôt qu'un seul avec un champ optionnel
`cout_unitaire` : une sortie ne se saisit jamais avec un coût (il est
calculé par le service selon la méthode de l'article — voir
`service.py`), donc l'exposer sur le schéma de sortie inviterait à la
confusion.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.stocks.models import MethodeValorisation


# --- Articles ------------------------------------------------------------------


class ArticleCreation(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    libelle: str = Field(min_length=1, max_length=150)
    unite: str = Field(min_length=1, max_length=20)
    methode_valorisation: MethodeValorisation
    compte_stock_id: uuid.UUID


class ArticleMiseAJour(BaseModel):
    """Volontairement limité aux champs descriptifs (voir
    `ServiceStocks.modifier_article`) : la méthode de valorisation et le
    compte de stock ne se changent pas une fois l'article créé."""

    libelle: str | None = Field(default=None, min_length=1, max_length=150)
    unite: str | None = Field(default=None, min_length=1, max_length=20)


class ArticleLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entreprise_id: uuid.UUID
    code: str
    libelle: str
    unite: str
    methode_valorisation: str
    compte_stock_id: uuid.UUID
    actif: bool
    quantite_en_stock: Decimal
    cout_unitaire_moyen: Decimal
    valeur_stock: Decimal
    cree_le: datetime


# --- Mouvements ------------------------------------------------------------------


class MouvementEntreeCreation(BaseModel):
    article_id: uuid.UUID
    date_mouvement: date
    quantite: Decimal = Field(gt=0)
    cout_unitaire: Decimal = Field(ge=0)
    reference: str | None = Field(default=None, max_length=100)
    libelle: str | None = Field(default=None, max_length=255)
    tiers_id: uuid.UUID | None = None


class MouvementSortieCreation(BaseModel):
    article_id: uuid.UUID
    date_mouvement: date
    quantite: Decimal = Field(gt=0)
    reference: str | None = Field(default=None, max_length=100)
    libelle: str | None = Field(default=None, max_length=255)
    tiers_id: uuid.UUID | None = None


class MouvementStockLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entreprise_id: uuid.UUID
    article_id: uuid.UUID
    type_mouvement: str
    date_mouvement: date
    quantite: Decimal
    cout_unitaire: Decimal
    cout_total: Decimal
    reference: str | None
    libelle: str | None
    tiers_id: uuid.UUID | None
    ecriture_id: uuid.UUID | None
    cree_le: datetime


class LigneConsommationLotLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    mouvement_sortie_id: uuid.UUID
    lot_id: uuid.UUID
    quantite_consommee: Decimal
    cout_unitaire: Decimal


class GenerationEcritureMouvementDemande(BaseModel):
    """Le journal et le compte de contrepartie sont fournis à l'appel
    plutôt que déduits : voir la note de
    `ServiceStocks.generer_ecriture_mouvement`."""

    journal_id: uuid.UUID
    compte_contrepartie_id: uuid.UUID


# --- Inventaires physiques -------------------------------------------------------


class InventairePhysiqueCreation(BaseModel):
    """`journal_id`/`compte_contrepartie_id` sont optionnels : ils ne sont
    nécessaires que si le comptage fait apparaître un écart (voir
    `ServiceStocks.creer_inventaire_physique`), qui rejette leur absence
    dans ce cas précis plutôt que de les rendre obligatoires à tort quand
    l'écart est nul."""

    article_id: uuid.UUID
    exercice_id: uuid.UUID
    date_inventaire: date
    quantite_physique: Decimal = Field(ge=0)
    journal_id: uuid.UUID | None = None
    compte_contrepartie_id: uuid.UUID | None = None


class InventairePhysiqueLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entreprise_id: uuid.UUID
    article_id: uuid.UUID
    exercice_id: uuid.UUID
    date_inventaire: date
    quantite_theorique: Decimal
    quantite_physique: Decimal
    ecart: Decimal
    mouvement_ajustement_id: uuid.UUID | None
    cree_le: datetime