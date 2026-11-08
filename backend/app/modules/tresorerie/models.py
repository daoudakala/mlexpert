"""Modèles du module tresorerie (relevés bancaires et rapprochement).

Trois tables :

- `CompteBancaire` : le pivot entre le monde bancaire (relevés) et le
  monde comptable. Il rattache un compte bancaire/caisse physique à la
  fois à un `Journal` (module `comptabilite`, type `banque` ou `caisse`)
  et à un `Compte` de la classe 5 — c'est sur ce couple que les écritures
  de trésorerie sont saisies et que les relevés se rapprochent. Un
  `Journal` ne correspond jamais qu'à UN SEUL compte bancaire (contrainte
  unique sur `journal_id`) : c'est la modélisation la plus simple qui
  couvre le cas réel (un compte bancaire physique = un journal dédié).
- `ReleveBancaire` : l'en-tête d'un relevé bancaire importé ou saisi pour
  un `CompteBancaire`, sur une période donnée (du solde de début au solde
  de fin).
- `LigneReleve` : une opération du relevé (une ligne de banque), à
  rapprocher avec une ou plusieurs `LigneEcriture` existantes du module
  `comptabilite`.

Rapprochement : PAS de table dédiée. `LigneReleve` porte la même colonne
`code_lettrage` que `LigneEcriture` (module `comptabilite`) — rapprocher
consiste à poser le MÊME code sur une ou plusieurs lignes de relevé et une
ou plusieurs lignes d'écriture dont les montants s'équilibrent ; la
recherche des lignes partageant un code est ce qui matérialise le lien,
exactement comme le lettrage clients/fournisseurs (`tiers`). Ça évite une
table de liaison supplémentaire et réutilise un mécanisme déjà en place.
Comme pour `LigneEcriture.code_lettrage`, seul le stockage du résultat est
fait ici — pas de moteur de proposition automatique de rapprochement à ce
stade (voir la note équivalente dans `comptabilite/models.py`).

Contrairement à `Ecriture`, un `ReleveBancaire` n'a pas de statut
brouillon/validé : un relevé bancaire est un fait extérieur (ce que la
banque a communiqué), pas une écriture comptable — il n'y a donc rien à
"valider" au sens métier ; le service peut toujours corriger une ligne mal
saisie sans que ça pose de problème d'immuabilité comptable.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base import Base
from app.shared.mixins import EntrepriseMixin, HorodatageMixin, IdentifiantMixin


class CompteBancaire(IdentifiantMixin, HorodatageMixin, EntrepriseMixin, Base):
    __tablename__ = "comptes_bancaires"
    __table_args__ = (UniqueConstraint("journal_id"),)

    libelle: Mapped[str] = mapped_column(String(150), nullable=False)
    banque: Mapped[str | None] = mapped_column(String(150), nullable=True)
    numero_compte: Mapped[str | None] = mapped_column(String(50), nullable=True)
    iban: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Le journal (banque/caisse) sur lequel les écritures de ce compte sont
    # saisies (module comptabilite). RESTRICT : un journal utilisé par un
    # compte bancaire ne peut pas disparaître sous ses pieds.
    journal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journaux.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Le compte comptable (classe 5) porté par ce compte bancaire. La
    # cohérence classe==5 n'est pas vérifiable par un CHECK inter-tables :
    # c'est le service qui la garantit à la création (voir service.py).
    compte_comptable_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comptes.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    solde_initial: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    actif: Mapped[bool] = mapped_column(nullable=False, default=True)


class ReleveBancaire(IdentifiantMixin, HorodatageMixin, EntrepriseMixin, Base):
    __tablename__ = "releves_bancaires"
    __table_args__ = (
        CheckConstraint("date_fin > date_debut", name="dates_coherentes"),
    )

    compte_bancaire_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("comptes_bancaires.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    date_debut: Mapped[date] = mapped_column(Date, nullable=False)
    date_fin: Mapped[date] = mapped_column(Date, nullable=False)
    solde_debut: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    solde_fin: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)


class LigneReleve(IdentifiantMixin, EntrepriseMixin, Base):
    """Pas de `HorodatageMixin` : comme `LigneEcriture`, une ligne vit et
    meurt avec son relevé ; `cree_le` du relevé parent suffit."""

    __tablename__ = "lignes_releve"
    __table_args__ = (
        CheckConstraint(
            "(debit > 0 AND credit = 0) OR (debit = 0 AND credit > 0)",
            name="debit_xor_credit",
        ),
    )

    releve_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("releves_bancaires.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date_operation: Mapped[date] = mapped_column(Date, nullable=False)
    libelle: Mapped[str] = mapped_column(String(255), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Mêmes conventions que LigneEcriture : soit débitrice (sortie d'argent
    # du point de vue du compte bancaire), soit créditrice, jamais les deux.
    debit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    credit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    # Renseigné par le service au rapprochement (voir la note de tête de
    # fichier) : partagé avec les `LigneEcriture` rapprochées.
    code_lettrage: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)