"""Modèles du module paie.

Portée volontairement limitée à ce premier passage (voir l'échange qui a
précédé ce fichier) : aucune formule fiscale ou sociale n'est codée en
dur (pas de taux CNPS, pas de barème ITS) — tous les montants d'un
bulletin sont SAISIS par le comptable, le service ne fait que les
totaliser. Les règles de calcul précises pourront s'ajouter plus tard,
une fois confirmées, sans remettre en cause ce schéma.

Mise à jour lors de la passe de consolidation comptable (génération
d'écritures depuis `immobilisations`/`paie`/`stocks`) : la note de tête
de fichier annonçait que l'affectation des comptes se ferait "au niveau
de la génération de l'écriture de paie" — c'est ce que fait maintenant
`RubriquePaie.compte_comptable_id` (nullable : une rubrique existante
sans compte reste utilisable pour saisir des bulletins, seule la
génération d'écriture l'exige). `BulletinPaie.ecriture_id` (nullable,
`SET NULL`) suit le même principe que `LigneAmortissement.ecriture_id`
dans `immobilisations` : `None` tant que le bulletin validé n'a pas
d'écriture postée.

Quatre tables :

- `Employe` : la fiche salarié. Volontairement SANS compte comptable
  rattaché — contrairement à `CompteBancaire`/`Immobilisation`, la paie
  poste en pratique sur des comptes de charges partagés (661 "salaires",
  431 "CNPS"...), pas un compte par employé ; leur affectation se fera au
  niveau de la génération de l'écriture de paie, hors de la portée de ce
  premier passage (voir la note de tête de fichier de `service.py`).
- `RubriquePaie` : le référentiel des éléments constitutifs d'un
  bulletin (salaire de base, prime de transport, retenue CNPS...), propre
  à chaque entreprise (contrairement au plan comptable, pas de
  référentiel partagé — le cahier ne le demande pas). `type_rubrique`
  (`gain`/`retenue`) détermine si son montant s'ajoute au brut ou aux
  retenues ; le signe n'est donc jamais saisi sur la ligne elle-même
  (`LigneBulletin.montant` reste toujours positif).
- `BulletinPaie` : l'en-tête, pour un employé et une période (mois en
  pratique, mais les deux dates bornent une période quelconque, comme
  `Exercice.date_debut`/`date_fin`). Statuts `brouillon`/`valide`, sur le
  même principe d'immuabilité que `Ecriture` : une fois validé, un
  bulletin ne se modifie plus (voir `service.py`).
- `LigneBulletin` : le détail. Pas de `HorodatageMixin` (comme
  `LigneEcriture`) : une ligne vit et meurt avec son bulletin.
"""

import uuid
from datetime import date
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base import Base
from app.shared.mixins import EntrepriseMixin, HorodatageMixin, IdentifiantMixin


class StatutEmploye(StrEnum):
    ACTIF = "actif"
    INACTIF = "inactif"


class TypeRubriquePaie(StrEnum):
    GAIN = "gain"
    RETENUE = "retenue"


class StatutBulletin(StrEnum):
    BROUILLON = "brouillon"
    VALIDE = "valide"


class Employe(IdentifiantMixin, HorodatageMixin, EntrepriseMixin, Base):
    __tablename__ = "employes"
    __table_args__ = (
        UniqueConstraint("entreprise_id", "matricule"),
        CheckConstraint("salaire_base > 0", name="salaire_base_positif"),
        CheckConstraint(
            "date_sortie IS NULL OR date_sortie >= date_embauche", name="dates_coherentes"
        ),
        CheckConstraint("statut IN ('actif', 'inactif')", name="statut_valide"),
    )

    matricule: Mapped[str] = mapped_column(String(30), nullable=False)
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    prenom: Mapped[str] = mapped_column(String(100), nullable=False)
    poste: Mapped[str | None] = mapped_column(String(150), nullable=True)
    date_embauche: Mapped[date] = mapped_column(Date, nullable=False)
    date_sortie: Mapped[date | None] = mapped_column(Date, nullable=True)
    salaire_base: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    statut: Mapped[str] = mapped_column(String(20), nullable=False, default=StatutEmploye.ACTIF.value)


class RubriquePaie(IdentifiantMixin, HorodatageMixin, EntrepriseMixin, Base):
    __tablename__ = "rubriques_paie"
    __table_args__ = (
        UniqueConstraint("entreprise_id", "code"),
        CheckConstraint("type_rubrique IN ('gain', 'retenue')", name="type_valide"),
    )

    code: Mapped[str] = mapped_column(String(30), nullable=False)
    libelle: Mapped[str] = mapped_column(String(150), nullable=False)
    type_rubrique: Mapped[str] = mapped_column(String(20), nullable=False)
    actif: Mapped[bool] = mapped_column(nullable=False, default=True)
    # Nullable : voir la note de tête de fichier — seule la génération
    # d'écriture (`ServicePaie.generer_ecriture_bulletin`) l'exige.
    compte_comptable_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comptes.id", ondelete="RESTRICT"), nullable=True, index=True
    )


class BulletinPaie(IdentifiantMixin, HorodatageMixin, EntrepriseMixin, Base):
    __tablename__ = "bulletins_paie"
    __table_args__ = (
        UniqueConstraint("employe_id", "periode_debut", "periode_fin"),
        CheckConstraint("periode_fin > periode_debut", name="periode_coherente"),
        CheckConstraint("statut IN ('brouillon', 'valide')", name="statut_valide"),
        CheckConstraint("salaire_brut >= 0", name="salaire_brut_positif"),
        CheckConstraint("total_retenues >= 0", name="total_retenues_positif"),
    )

    employe_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    exercice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exercices.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    periode_debut: Mapped[date] = mapped_column(Date, nullable=False)
    periode_fin: Mapped[date] = mapped_column(Date, nullable=False)
    statut: Mapped[str] = mapped_column(
        String(20), nullable=False, default=StatutBulletin.BROUILLON.value
    )
    # Totaux calculés par le service à partir des lignes (voir
    # `ServicePaie._recalculer_totaux`) — jamais saisis directement.
    salaire_brut: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    total_retenues: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    net_a_payer: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    # Renseigné une fois le bulletin validé comptabilisé (voir la note de
    # tête de fichier) — jamais à la création du bulletin.
    ecriture_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ecritures.id", ondelete="SET NULL"), nullable=True
    )


class LigneBulletin(IdentifiantMixin, EntrepriseMixin, Base):
    """Pas de `HorodatageMixin` : comme `LigneEcriture`, une ligne vit et
    meurt avec son bulletin."""

    __tablename__ = "lignes_bulletin"
    __table_args__ = (
        CheckConstraint("montant >= 0", name="montant_positif"),
    )

    bulletin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bulletins_paie.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rubrique_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rubriques_paie.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    libelle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Toujours positif : le signe (gain ou retenue) vient de
    # `RubriquePaie.type_rubrique`, jamais stocké ici (voir la note de
    # tête de fichier).
    montant: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)