"""Schémas Pydantic du module comptabilite.

`CompteCreation` sert aux deux routes de création (compte global et
extension d'entreprise) : le corps de la requête est identique, seule
l'URL — et donc le service appelé — change ce que devient `entreprise_id`.

Partie transactionnelle : `LigneEcritureSaisie.verifier_debit_xor_credit`
et `EcritureCreation.verifier_equilibre` dupliquent des vérifications déjà
faites par `ServiceComptabilite` — volontairement : une erreur 422 avec un
message clair avant même d'atteindre le service est un meilleur retour
qu'une exception métier générique, pour le même contrôle.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.comptabilite.models import PeriodiciteRecurrence, SensLigne, TypeJournal


class CompteCreation(BaseModel):
    numero: str = Field(min_length=1, max_length=20)
    libelle: str = Field(min_length=2, max_length=255)
    classe: int = Field(ge=1, le=9)
    lettrable: bool = False
    est_collectif: bool = False
    # Sous-compte (hiérarchie parent/enfant, voir models.py) : optionnel,
    # vérifié côté service (classe identique au parent, numéro préfixé
    # par celui du parent).
    compte_parent_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def verifier_coherence_collectif(self) -> "CompteCreation":
        if self.est_collectif and not self.lettrable:
            raise ValueError("Un compte collectif doit être lettrable.")
        return self


class CompteLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    numero: str
    libelle: str
    classe: int
    lettrable: bool
    est_collectif: bool
    actif: bool
    # Nul pour un compte du référentiel global, renseigné pour une
    # extension propre à une entreprise (voir models.py).
    entreprise_id: uuid.UUID | None
    compte_parent_id: uuid.UUID | None
    cree_le: datetime


class CompteImportIgnore(BaseModel):
    """Une ligne du fichier importé qui n'a pas donné lieu à la création
    d'un compte — numéro/libellé manquant, numéro déjà pris, etc. Le
    fichier d'origine ne porte ni classe ni booléens : seules des erreurs
    de format ou des doublons font échouer une ligne, jamais une règle
    métier plus fine (voir `ServiceComptabilite.importer_comptes`)."""

    numero: str
    libelle: str
    raison: str


class CompteImportResultat(BaseModel):
    comptes_crees: list[CompteLecture]
    ignores: list[CompteImportIgnore]


class JournalCreation(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    libelle: str = Field(min_length=2, max_length=150)
    type_journal: TypeJournal


class JournalLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entreprise_id: uuid.UUID
    code: str
    libelle: str
    type_journal: str
    actif: bool
    cree_le: datetime


class LigneModeleSaisie(BaseModel):
    compte_id: uuid.UUID
    sens: SensLigne
    libelle: str | None = Field(default=None, max_length=255)


class LigneModeleLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    compte_id: uuid.UUID
    sens: str
    libelle: str | None


class ModeleEcritureCreation(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    libelle: str = Field(min_length=2, max_length=150)
    journal_id: uuid.UUID
    lignes: list[LigneModeleSaisie] = Field(min_length=2)


class ModeleEcritureMiseAJour(BaseModel):
    """Mise à jour partielle (voir `ServiceComptabilite.modifier_modele`).
    Fournir `lignes` remplace l'intégralité des lignes existantes, comme
    `EcritureMiseAJour`."""

    code: str | None = Field(default=None, min_length=1, max_length=20)
    libelle: str | None = Field(default=None, min_length=2, max_length=150)
    journal_id: uuid.UUID | None = None
    actif: bool | None = None
    lignes: list[LigneModeleSaisie] | None = Field(default=None, min_length=2)


class ModeleEcritureLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entreprise_id: uuid.UUID
    code: str
    libelle: str
    journal_id: uuid.UUID
    actif: bool
    cree_le: datetime


class ModeleEcritureAvecLignes(ModeleEcritureLecture):
    lignes: list[LigneModeleLecture] = []


class MontantLigneModele(BaseModel):
    ligne_modele_id: uuid.UUID
    montant: Decimal = Field(ge=0)


class AppliquerModeleDonnees(BaseModel):
    exercice_id: uuid.UUID
    date_ecriture: date
    libelle: str | None = Field(default=None, min_length=2, max_length=255)
    reference_piece: str | None = Field(default=None, max_length=100)
    lignes: list[MontantLigneModele] = Field(min_length=2)


class LigneEcritureRecurrenteSaisie(BaseModel):
    compte_id: uuid.UUID
    sens: SensLigne
    montant: Decimal = Field(gt=0)
    libelle: str | None = Field(default=None, max_length=255)


class LigneEcritureRecurrenteLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    compte_id: uuid.UUID
    sens: str
    montant: Decimal
    libelle: str | None


class EcritureRecurrenteCreation(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    libelle: str = Field(min_length=2, max_length=150)
    journal_id: uuid.UUID
    periodicite: PeriodiciteRecurrence
    date_debut: date
    date_fin: date | None = None
    reference_piece: str | None = Field(default=None, max_length=100)
    lignes: list[LigneEcritureRecurrenteSaisie] = Field(min_length=2)

    @model_validator(mode="after")
    def verifier_date_fin(self) -> "EcritureRecurrenteCreation":
        if self.date_fin is not None and self.date_fin < self.date_debut:
            raise ValueError("La date de fin ne peut pas être antérieure à la date de début.")
        return self


class EcritureRecurrenteMiseAJour(BaseModel):
    """Mise à jour partielle. `date_debut` n'est volontairement pas
    modifiable (voir `ServiceComptabilite.modifier_ecriture_recurrente`).
    Fournir `lignes` remplace l'intégralité des lignes existantes."""

    code: str | None = Field(default=None, min_length=1, max_length=20)
    libelle: str | None = Field(default=None, min_length=2, max_length=150)
    journal_id: uuid.UUID | None = None
    periodicite: PeriodiciteRecurrence | None = None
    date_fin: date | None = None
    reference_piece: str | None = Field(default=None, max_length=100)
    actif: bool | None = None
    lignes: list[LigneEcritureRecurrenteSaisie] | None = Field(default=None, min_length=2)


class EcritureRecurrenteLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entreprise_id: uuid.UUID
    code: str
    libelle: str
    journal_id: uuid.UUID
    periodicite: str
    reference_piece: str | None
    date_debut: date
    date_fin: date | None
    prochaine_echeance: date
    actif: bool
    cree_le: datetime


class EcritureRecurrenteAvecLignes(EcritureRecurrenteLecture):
    lignes: list[LigneEcritureRecurrenteLecture] = []


class LigneEcritureSaisie(BaseModel):
    compte_id: uuid.UUID
    debit: Decimal = Field(default=Decimal("0"), ge=0)
    credit: Decimal = Field(default=Decimal("0"), ge=0)
    tiers_id: uuid.UUID | None = None
    libelle: str | None = Field(default=None, max_length=255)
    # Optionnelle : si absente et que la ligne porte un tiers_id, le service
    # la calcule depuis Tiers.delai_paiement_jours (voir la note de tête de
    # fichier de models.py). Laisser à None force un calcul automatique ;
    # la renseigner explicitement l'impose telle quelle.
    date_echeance: date | None = None

    @model_validator(mode="after")
    def verifier_debit_xor_credit(self) -> "LigneEcritureSaisie":
        if (self.debit > 0) == (self.credit > 0):
            raise ValueError(
                "Une ligne doit être soit débitrice, soit créditrice (jamais les "
                "deux, jamais ni l'une ni l'autre)."
            )
        return self


class LigneEcritureLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    compte_id: uuid.UUID
    tiers_id: uuid.UUID | None
    libelle: str | None
    debit: Decimal
    credit: Decimal
    code_lettrage: str | None
    date_echeance: date | None


# --- Lettrage manuel (section 8.2) ------------------------------------------


class LigneLettrageLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ecriture_id: uuid.UUID
    date_ecriture: date
    numero: str | None
    reference_piece: str | None
    libelle_ecriture: str
    libelle_ligne: str | None
    debit: Decimal
    credit: Decimal
    tiers_id: uuid.UUID | None
    code_lettrage: str | None


class LettrageDemande(BaseModel):
    ligne_ecriture_ids: list[uuid.UUID] = Field(min_length=2)


class LettrageReponse(BaseModel):
    code_lettrage: str


class DelettrageDemande(BaseModel):
    code_lettrage: str = Field(min_length=1, max_length=20)


class EcritureCreation(BaseModel):
    journal_id: uuid.UUID
    # Facultatif : à défaut, l'exercice qui couvre `date_ecriture` est
    # retrouvé automatiquement par le service.
    exercice_id: uuid.UUID | None = None
    date_ecriture: date
    libelle: str = Field(min_length=2, max_length=255)
    reference_piece: str | None = Field(default=None, max_length=100)
    lignes: list[LigneEcritureSaisie] = Field(min_length=2)

    @model_validator(mode="after")
    def verifier_equilibre(self) -> "EcritureCreation":
        total_debit = sum((ligne.debit for ligne in self.lignes), Decimal("0"))
        total_credit = sum((ligne.credit for ligne in self.lignes), Decimal("0"))
        if total_debit != total_credit:
            raise ValueError(
                f"L'écriture n'est pas équilibrée : total débit {total_debit} ≠ "
                f"total crédit {total_credit}."
            )
        return self


class EcritureMiseAJour(BaseModel):
    """Mise à jour partielle d'un brouillon (voir
    `ServiceComptabilite.modifier_ecriture`). Fournir `lignes` remplace
    l'intégralité des lignes existantes, jamais une fusion partielle."""

    date_ecriture: date | None = None
    libelle: str | None = Field(default=None, min_length=2, max_length=255)
    reference_piece: str | None = Field(default=None, max_length=100)
    lignes: list[LigneEcritureSaisie] | None = Field(default=None, min_length=2)

    @model_validator(mode="after")
    def verifier_equilibre(self) -> "EcritureMiseAJour":
        if self.lignes is not None:
            total_debit = sum((ligne.debit for ligne in self.lignes), Decimal("0"))
            total_credit = sum((ligne.credit for ligne in self.lignes), Decimal("0"))
            if total_debit != total_credit:
                raise ValueError(
                    f"L'écriture n'est pas équilibrée : total débit {total_debit} ≠ "
                    f"total crédit {total_credit}."
                )
        return self


class EcritureDuplication(BaseModel):
    date_ecriture: date
    exercice_id: uuid.UUID | None = None
    libelle: str | None = Field(default=None, min_length=2, max_length=255)


class EcritureExtourne(BaseModel):
    date_ecriture: date
    libelle: str | None = Field(default=None, max_length=255)


class EcritureLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entreprise_id: uuid.UUID
    journal_id: uuid.UUID
    exercice_id: uuid.UUID
    date_ecriture: date
    libelle: str
    reference_piece: str | None
    statut: str
    numero: str | None
    ecriture_extournee_id: uuid.UUID | None
    cree_le: datetime


class EcritureAvecLignes(EcritureLecture):
    lignes: list[LigneEcritureLecture] = []


class EcritureImportIgnoree(BaseModel):
    """Un groupe de lignes (même journal/date/pièce) qui n'a pas donné
    lieu à une écriture — voir `ServiceComptabilite.importer_ecritures`."""

    journal: str
    date: str
    piece: str
    raison: str


class EcritureImportResultat(BaseModel):
    ecritures_creees: list[EcritureAvecLignes]
    ignorees: list[EcritureImportIgnoree]


class GenerationEcheancesDemande(BaseModel):
    jusquau: date


class EcheanceIgnoreeLecture(BaseModel):
    date_echeance: date
    raison: str


class GenerationEcheancesResultat(BaseModel):
    ecritures_creees: list[EcritureLecture]
    ignorees: list[EcheanceIgnoreeLecture]


class ANouveauxDemande(BaseModel):
    """Corps optionnel de la génération des à-nouveaux : `regenerer` extourne
    les à-nouveaux existants puis les refait (motif obligatoire, tracé)."""

    regenerer: bool = False
    motif: str | None = Field(default=None, max_length=255)


class MouvementJournalTresorerie(BaseModel):
    ecriture_id: uuid.UUID
    date_ecriture: date
    numero: str | None
    libelle: str
    compte_numero: str
    debit: Decimal
    credit: Decimal
    solde_cumule: Decimal


class ResumeJournalTresorerie(BaseModel):
    journal_id: uuid.UUID
    date_debut: date
    date_fin: date
    solde_initial: Decimal
    total_debit: Decimal
    total_credit: Decimal
    solde_final: Decimal
    mouvements: list[MouvementJournalTresorerie] = []