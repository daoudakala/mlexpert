"""Schémas Pydantic du module dashboards.

`from_attributes=True` sur chaque schéma permet de valider directement
les dataclasses retournées par `service.py` (`LigneBalance`,
`LigneGrandLivre`, `CompteResultatSommaire`) — pas des modèles
SQLAlchemy, mais Pydantic les lit de la même façon par attribut.
"""

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class LigneBalanceLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    compte_id: uuid.UUID
    numero: str
    libelle: str
    total_debit: Decimal
    total_credit: Decimal
    solde: Decimal


class LigneGrandLivreLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ligne_ecriture_id: uuid.UUID
    date_ecriture: date
    ecriture_id: uuid.UUID
    numero_ecriture: str | None
    libelle: str
    debit: Decimal
    credit: Decimal
    solde_progressif: Decimal


class LigneBalanceCompareeLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    compte_id: uuid.UUID
    numero: str
    libelle: str
    solde_n: Decimal
    solde_n1: Decimal | None
    variation_montant: Decimal | None
    variation_pourcentage: float | None


class CompteResultatSommaireLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    exercice_id: uuid.UUID
    total_charges: Decimal
    total_produits: Decimal
    resultat_net: Decimal


class BilanLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    exercice_id: uuid.UUID
    immobilisations: Decimal
    stocks: Decimal
    creances: Decimal
    tresorerie_actif: Decimal
    total_actif: Decimal
    ressources_durables: Decimal
    dettes_circulantes: Decimal
    tresorerie_passif: Decimal
    total_passif: Decimal
    equilibre: bool


class CompteResultatDetailleLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    exercice_id: uuid.UUID
    total_charges_exploitation: Decimal
    total_produits_exploitation: Decimal
    resultat_exploitation: Decimal
    total_charges_financieres: Decimal
    total_produits_financiers: Decimal
    resultat_financier: Decimal
    resultat_activites_ordinaires: Decimal
    total_charges_hao: Decimal
    total_produits_hao: Decimal
    resultat_hao: Decimal
    resultat_net: Decimal


class LigneEcheanceLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ligne_ecriture_id: uuid.UUID
    ecriture_id: uuid.UUID
    numero_ecriture: str | None
    date_ecriture: date
    tiers_id: uuid.UUID
    code_tiers: str
    raison_sociale_tiers: str
    libelle: str
    montant: Decimal
    date_echeance: date | None
    jours_retard: int | None


class TableauDirectionLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    exercice_id: uuid.UUID | None
    tresorerie_disponible: Decimal
    creances_clients_ouvertes: Decimal
    dettes_fournisseurs_ouvertes: Decimal
    echeances_clients_en_retard: int
    echeances_fournisseurs_en_retard: int
    resultat_net_exercice: Decimal | None


class LignePrevisionTresorerieLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date_echeance: date
    libelle: str
    montant: Decimal
    solde_cumule: Decimal


class PrevisionTresorerieLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    solde_actuel: Decimal
    horizon_jours: int
    lignes: list[LignePrevisionTresorerieLecture]
    solde_final_projete: Decimal
    montant_sans_echeance_clients: Decimal
    montant_sans_echeance_fournisseurs: Decimal


class TableauComptabiliteLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ecritures_brouillon: int
    lignes_bancaires_non_lettrees: int
    clotures_a_venir: int
    demandes_non_traitees: int


class TrancheAgeeLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tiers_id: uuid.UUID
    code_tiers: str
    raison_sociale_tiers: str
    non_echu: Decimal
    jours_0_30: Decimal
    jours_31_60: Decimal
    jours_61_90: Decimal
    jours_plus_90: Decimal
    echeance_inconnue: Decimal
    total: Decimal