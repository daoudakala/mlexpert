"""Schémas Pydantic du module immobilisations.

`ImmobilisationCreation.verifier_coherence` duplique une partie des
vérifications déjà faites par `ServiceImmobilisations._valider_donnees_creation`
— même choix que dans `comptabilite`/`tresorerie` : un 422 clair avant le
service plutôt qu'une exception métier générique, pour le même contrôle.

Pas de schéma de saisie pour `LigneAmortissement` : une ligne se GÉNÈRE
(calculée par le service), elle ne se saisit jamais directement — voir
`POST .../lignes-amortissement/{exercice_id}` dans `router.py`.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.immobilisations.models import MethodeAmortissement


class ImmobilisationCreation(BaseModel):
    libelle: str = Field(min_length=2, max_length=255)
    categorie: str | None = Field(default=None, max_length=100)
    numero_inventaire: str | None = Field(default=None, max_length=50)
    date_acquisition: date
    date_mise_en_service: date
    valeur_origine: Decimal = Field(gt=0)
    valeur_residuelle: Decimal = Field(default=Decimal("0"), ge=0)
    duree_amortissement_annees: int = Field(gt=0, le=100)
    methode_amortissement: MethodeAmortissement = MethodeAmortissement.LINEAIRE
    taux_degressif: Decimal | None = Field(default=None, gt=0, le=100)
    compte_immobilisation_id: uuid.UUID
    compte_amortissement_id: uuid.UUID
    compte_dotation_id: uuid.UUID
    fournisseur_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def verifier_coherence(self) -> "ImmobilisationCreation":
        if self.valeur_residuelle >= self.valeur_origine:
            raise ValueError("La valeur résiduelle doit être strictement inférieure à la valeur d'origine.")
        if self.date_mise_en_service < self.date_acquisition:
            raise ValueError("La date de mise en service ne peut pas être antérieure à la date d'acquisition.")
        est_degressif = self.methode_amortissement == MethodeAmortissement.DEGRESSIF
        if est_degressif and self.taux_degressif is None:
            raise ValueError("Un taux dégressif est requis pour la méthode dégressive.")
        if not est_degressif and self.taux_degressif is not None:
            raise ValueError("Le taux dégressif ne s'applique qu'à la méthode dégressive.")
        return self


class ImmobilisationMiseAJour(BaseModel):
    """Volontairement limité aux champs descriptifs (voir
    `ServiceImmobilisations.modifier_immobilisation`)."""

    libelle: str | None = Field(default=None, min_length=2, max_length=255)
    categorie: str | None = Field(default=None, max_length=100)
    numero_inventaire: str | None = Field(default=None, max_length=50)
    fournisseur_id: uuid.UUID | None = None


class ImmobilisationLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entreprise_id: uuid.UUID
    libelle: str
    categorie: str | None
    numero_inventaire: str | None
    date_acquisition: date
    date_mise_en_service: date
    valeur_origine: Decimal
    valeur_residuelle: Decimal
    duree_amortissement_annees: int
    methode_amortissement: str
    taux_degressif: Decimal | None
    statut: str
    compte_immobilisation_id: uuid.UUID
    compte_amortissement_id: uuid.UUID
    compte_dotation_id: uuid.UUID
    fournisseur_id: uuid.UUID | None
    ligne_acquisition_id: uuid.UUID | None
    date_sortie: date | None
    prix_cession: Decimal | None
    valeur_nette_comptable_sortie: Decimal | None
    plus_ou_moins_value: Decimal | None
    ecriture_sortie_id: uuid.UUID | None
    cree_le: datetime


class LigneAmortissementLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    immobilisation_id: uuid.UUID
    exercice_id: uuid.UUID
    base_amortissable: Decimal
    taux_applique: Decimal
    dotation: Decimal
    cumul_amortissements: Decimal
    valeur_nette_comptable: Decimal
    statut: str
    ecriture_id: uuid.UUID | None


class GenerationEcritureDemande(BaseModel):
    """Le journal est fourni à l'appel plutôt que déduit : voir la note de
    tête de fichier de `ServiceImmobilisations.generer_ecriture_amortissement`."""

    journal_id: uuid.UUID


class CessionDemande(BaseModel):
    date_sortie: date
    prix_cession: Decimal = Field(ge=0)
    journal_id: uuid.UUID
    compte_tresorerie_id: uuid.UUID
    compte_produit_cession_id: uuid.UUID
    compte_valeur_comptable_sortie_id: uuid.UUID


class ReformeDemande(BaseModel):
    date_sortie: date
    journal_id: uuid.UUID
    compte_valeur_comptable_sortie_id: uuid.UUID

class AcquisitionAConfirmer(BaseModel):
    """Une ligne d'écriture validée qui débite un compte d'immobilisation
    (21 à 27) et n'a pas encore de fiche — avec des propositions pour
    pré-remplir la confirmation."""

    ligne_ecriture_id: uuid.UUID
    ecriture_id: uuid.UUID
    date_acquisition: date
    numero_ecriture: str | None
    libelle: str
    compte_id: uuid.UUID
    compte_numero: str
    compte_libelle: str
    montant: Decimal
    tiers_id: uuid.UUID | None
    compte_amortissement_suggere_id: uuid.UUID | None
    compte_dotation_suggere_id: uuid.UUID | None


class ConfirmationAcquisition(BaseModel):
    """Les informations que l'écriture ne porte pas. La date d'acquisition,
    la valeur d'origine et le compte d'immobilisation viennent de la ligne
    d'écriture elle-même."""

    libelle: str = Field(min_length=2, max_length=255)
    categorie: str | None = Field(default=None, max_length=100)
    numero_inventaire: str | None = Field(default=None, max_length=50)
    date_mise_en_service: date | None = None  # défaut : date d'acquisition
    valeur_residuelle: Decimal = Field(default=Decimal("0"), ge=0)
    duree_amortissement_annees: int = Field(gt=0, le=100)
    methode_amortissement: MethodeAmortissement = MethodeAmortissement.LINEAIRE
    taux_degressif: Decimal | None = Field(default=None, gt=0, le=100)
    compte_amortissement_id: uuid.UUID
    compte_dotation_id: uuid.UUID
    fournisseur_id: uuid.UUID | None = None
    generer_plan: bool = True


class ConfirmationAcquisitionResultat(BaseModel):
    immobilisation: ImmobilisationLecture
    lignes_generees: int
    avertissement: str | None = None