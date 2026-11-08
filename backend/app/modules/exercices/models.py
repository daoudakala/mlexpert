"""Modèles du module exercices.

Deux tables (cahier des charges, section 7.2) :

- `Exercice` : la période comptable annuelle d'une entreprise. Le lien
  `exercice_precedent_id` porte la comparaison N/N-1 et les à-nouveaux
  (report du solde de clôture de N-1 comme solde d'ouverture de N).
- `Periode` : un découpage plus fin à l'intérieur d'un exercice (ex. un
  mois), utilisé par les contrôles de saisie (section 8.5 : "Période
  clôturée"). Elle porte elle-même `entreprise_id` (via `EntrepriseMixin`),
  dénormalisé depuis son exercice : c'est ce que `RepositoryEntreprise`
  filtre directement, sans jointure vers `Exercice` à chaque requête. La
  cohérence entre les deux colonnes est garantie par le service, pas par
  la base (voir `service.py`).

`AffectationMixin.exercice_id_restreint` (module `droits`) référence déjà
`exercices.id` : c'est cette dépendance qui rendait `droits` impossible à
migrer avant ce module.
"""

import uuid
from datetime import date
from enum import StrEnum

from sqlalchemy import CheckConstraint, Date, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base import Base
from app.shared.mixins import EntrepriseMixin, HorodatageMixin, IdentifiantMixin


class StatutExercice(StrEnum):
    OUVERT = "ouvert"
    CLOTURE = "cloture"


class StatutPeriode(StrEnum):
    OUVERTE = "ouverte"
    CLOTUREE = "cloturee"


class Exercice(IdentifiantMixin, HorodatageMixin, EntrepriseMixin, Base):
    __tablename__ = "exercices"
    __table_args__ = (
        CheckConstraint("date_fin > date_debut", name="dates_coherentes"),
        CheckConstraint("statut IN ('ouvert', 'cloture')", name="statut_valide"),
    )

    date_debut: Mapped[date] = mapped_column(Date, nullable=False)
    date_fin: Mapped[date] = mapped_column(Date, nullable=False)
    statut: Mapped[str] = mapped_column(
        String(20), nullable=False, default=StatutExercice.OUVERT.value
    )

    # Autoréférence pour la comparaison N/N-1 et les à-nouveaux.
    exercice_precedent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("exercices.id", ondelete="SET NULL"),
        nullable=True,
    )


class Periode(IdentifiantMixin, HorodatageMixin, EntrepriseMixin, Base):
    __tablename__ = "periodes"
    __table_args__ = (
        CheckConstraint("date_fin > date_debut", name="dates_coherentes"),
        CheckConstraint("statut IN ('ouverte', 'cloturee')", name="statut_valide"),
    )

    exercice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("exercices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    libelle: Mapped[str | None] = mapped_column(String(50), nullable=True)
    date_debut: Mapped[date] = mapped_column(Date, nullable=False)
    date_fin: Mapped[date] = mapped_column(Date, nullable=False)
    statut: Mapped[str] = mapped_column(
        String(20), nullable=False, default=StatutPeriode.OUVERTE.value
    )