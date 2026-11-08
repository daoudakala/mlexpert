"""Modèles du module provisions (point 8.2 du cahier — "Écritures
d'inventaire / de régularisation", provisions pour dépréciation et pour
risques et charges).

Deux tables, sur le même principe que `immobilisations.Immobilisation` /
`LigneAmortissement` (un en-tête descriptif, un détail des mouvements) :

- `Provision` : la fiche descriptive — type, libellé, tiers concerné le
  cas échéant (dépréciation de créance), et TROIS comptes rattachés :
  `compte_dotation_id` (charge, classe 68/69, débité à la constitution),
  `compte_provision_id` (29x/39x/49x/15x selon le type, crédité à la
  constitution puis débité à la reprise) et `compte_reprise_id` (produit,
  classe 78, crédité à la reprise). Trois comptes et non deux comme
  l'immobilisation : la reprise d'une provision crédite un compte de
  PRODUIT distinct du compte de charge utilisé à la constitution — ce
  n'est pas une simple contre-passation du même compte.
- `MouvementProvision` : l'historique des constitutions (`dotation`) et
  reprises (`reprise`) — chacune une opération comptable immédiate (pas
  de phase "prévue" sans écriture, à la différence de
  `LigneAmortissement` dont le plan est calculé à l'avance indépendamment
  de sa comptabilisation) : `ecriture_id` n'est donc jamais nul.

`montant_actuel` sur `Provision` est dénormalisé — la somme des
dotations moins la somme des reprises — pour éviter de recalculer cette
agrégation à chaque lecture de la fiche ; le service le maintient à
jour à chaque mouvement, comme `cumul_amortissements` sur
`LigneAmortissement`. `statut` passe de `active` à `soldee` quand
`montant_actuel` atteint zéro ; il n'y a pas d'état "partiellement
reprise" distinct de `active`, une reprise partielle restant une
provision active avec un montant réduit.

Le rattachement à un tiers (`tiers_id`) n'a de sens métier que pour une
dépréciation de créance, mais n'est pas contraint par un `CHECK` selon le
type : comme `fournisseur_id` sur `Immobilisation`, c'est laissé
optionnel et non normatif à ce stade plutôt que figé par une contrainte
qui compliquerait l'évolution future (ex. provision pour dépréciation
d'un compte courant associé).
"""

import uuid
from datetime import date
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base import Base
from app.shared.mixins import EntrepriseMixin, HorodatageMixin, IdentifiantMixin


class TypeProvision(StrEnum):
    DEPRECIATION_CREANCE = "depreciation_creance"
    DEPRECIATION_STOCK = "depreciation_stock"
    RISQUE_CHARGE = "risque_charge"


class StatutProvision(StrEnum):
    ACTIVE = "active"
    SOLDEE = "soldee"


class TypeMouvementProvision(StrEnum):
    DOTATION = "dotation"
    REPRISE = "reprise"


class Provision(IdentifiantMixin, HorodatageMixin, EntrepriseMixin, Base):
    __tablename__ = "provisions"
    __table_args__ = (
        CheckConstraint(
            "type_provision IN ('depreciation_creance', 'depreciation_stock', 'risque_charge')",
            name="type_provision_valide",
        ),
        CheckConstraint(
            "statut IN ('active', 'soldee')",
            name="statut_valide",
        ),
        CheckConstraint("montant_actuel >= 0", name="montant_actuel_positif"),
    )

    libelle: Mapped[str] = mapped_column(String(255), nullable=False)
    type_provision: Mapped[str] = mapped_column(String(30), nullable=False)

    # Optionnel : voir la note de tête de fichier (pertinent surtout pour
    # une dépréciation de créance, non contraint par type).
    tiers_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tiers.id", ondelete="RESTRICT"), nullable=True, index=True
    )

    compte_dotation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comptes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    compte_provision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comptes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    compte_reprise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comptes.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    # Dénormalisé — voir la note de tête de fichier.
    montant_actuel: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    statut: Mapped[str] = mapped_column(
        String(20), nullable=False, default=StatutProvision.ACTIVE.value
    )


class MouvementProvision(IdentifiantMixin, EntrepriseMixin, Base):
    """Pas de `HorodatageMixin` : `date_mouvement` porte déjà la date
    métier, et le mouvement est immuable une fois créé (comme une
    `Ecriture` validée) — `cree_le` de la provision parente et de
    l'écriture liée suffisent à l'audit."""

    __tablename__ = "mouvements_provision"
    __table_args__ = (
        CheckConstraint(
            "type_mouvement IN ('dotation', 'reprise')",
            name="type_mouvement_valide",
        ),
        CheckConstraint("montant > 0", name="montant_positif"),
    )

    provision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("provisions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exercice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exercices.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    type_mouvement: Mapped[str] = mapped_column(String(20), nullable=False)
    montant: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    date_mouvement: Mapped[date] = mapped_column(Date, nullable=False)

    # Jamais nul : contrairement à `LigneAmortissement.ecriture_id`, un
    # mouvement de provision naît toujours AVEC son écriture (voir la note
    # de tête de fichier) — pas de phase "prévue" préalable.
    ecriture_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ecritures.id", ondelete="RESTRICT"), nullable=False, index=True
    )