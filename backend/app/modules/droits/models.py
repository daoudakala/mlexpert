"""Modèles du module droits : rôles, permissions, affectations.

C'est le socle du contrôle d'accès de MLexpert (cahier des charges,
section 6 et Annexe B) :

- `Role` / `Permission` / `RolePermission` : un rôle regroupe des
  permissions (ex. le rôle "Collaborateur comptable" a les permissions
  `ecriture.creer`, `ecriture.modifier`, `tiers.consulter`...).
- `Affectation` : le pivot qui relie un utilisateur, une entreprise et un
  rôle. C'est elle que `api/deps.py` consulte pour établir le contexte
  d'une requête (voir shared/repository.py pour ce que ce contexte
  déclenche ensuite).
- `AttributionRoleGlobal` : rôles de plateforme (ex. Administrateur), qui
  ne dépendent d'aucune entreprise. Table séparée de `Affectation` pour
  respecter le point 14 de l'Annexe B : l'administrateur technique n'a pas
  automatiquement les droits métier de validation sur une entreprise.

Le code d'une permission suit la convention `<module>.<action>`, avec les
9 actions du cahier (section 6) : consulter, creer, modifier, valider,
annuler, exporter, supprimer, archiver, administrer. Ex. `tiers.creer`,
`ecriture.valider`, `journal_activite.exporter`.
"""

import uuid

from sqlalchemy import Boolean, Date, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base import Base
from app.shared.mixins import HorodatageMixin, IdentifiantMixin


class Role(IdentifiantMixin, HorodatageMixin, Base):
    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    libelle: Mapped[str] = mapped_column(String(100), nullable=False)
    # Rôle de plateforme (ex. Administrateur) : utilisable dans
    # AttributionRoleGlobal mais pas dans Affectation, et inversement
    # pour un rôle métier (ex. Collaborateur comptable).
    est_role_plateforme: Mapped[bool] = mapped_column(Boolean, default=False)

    permissions: Mapped[list["RolePermission"]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )


class Permission(IdentifiantMixin, HorodatageMixin, Base):
    __tablename__ = "permissions"

    # Convention : "<module>.<action>", ex. "tiers.creer".
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    libelle: Mapped[str] = mapped_column(String(150), nullable=False)


class RolePermission(IdentifiantMixin, Base):
    __tablename__ = "roles_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id"),
    )

    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        nullable=False,
    )

    role: Mapped["Role"] = relationship(back_populates="permissions")
    permission: Mapped["Permission"] = relationship()


class Affectation(IdentifiantMixin, HorodatageMixin, Base):
    """Lie un utilisateur à une entreprise avec un rôle.

    Hypothèse retenue (à confirmer) : un utilisateur a un seul rôle ACTIF
    par entreprise, d'où l'index unique PARTIEL sur
    (utilisateur_id, entreprise_id) — restreint aux lignes `actif=True`
    (voir migration `b5e3a8d2c761`). Volontairement partiel et non une
    `UniqueConstraint` classique : un utilisateur retiré d'une entreprise
    (`actif=False`, via `ServiceDroits.retirer_affectation`) doit pouvoir
    y être ré-affecté plus tard sans que l'ancienne ligne inactive ne
    bloque l'insertion de la nouvelle — l'historique s'accumule alors en
    plusieurs lignes inactives pour la même paire, ce qui est voulu (audit).
    `module_restreint` et `exercice_id_restreint` sont optionnels : vides,
    ils signifient "tout le périmètre du rôle".
    """

    __tablename__ = "affectations"
    __table_args__ = (
        Index(
            "uq_affectations_utilisateur_entreprise_actif",
            "utilisateur_id",
            "entreprise_id",
            unique=True,
            postgresql_where=text("actif"),
        ),
    )

    utilisateur_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("utilisateurs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entreprise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entreprises.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False
    )

    # Restrictions optionnelles du périmètre de l'affectation.
    module_restreint: Mapped[str | None] = mapped_column(String(50), nullable=True)
    exercice_id_restreint: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exercices.id", ondelete="SET NULL"), nullable=True
    )
    # Rattache ce compte à SON dossier client (portail) : nullable, une
    # affectation "cabinet" classique (collaborateur interne) n'en a pas
    # besoin. Posé par `ServiceDroits.inviter_utilisateur` quand le rôle
    # choisi porte une permission `portail_client.*` — voir
    # `portail_client/service.py` pour l'usage (filtrage des documents
    # visibles par client).
    tiers_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tiers.id", ondelete="SET NULL"), nullable=True, index=True
    )

    actif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    date_debut: Mapped[Date | None] = mapped_column(Date, nullable=True)
    date_fin: Mapped[Date | None] = mapped_column(Date, nullable=True)

    role: Mapped["Role"] = relationship()


class AttributionRoleGlobal(IdentifiantMixin, HorodatageMixin, Base):
    """Rôles de plateforme, indépendants de toute entreprise.

    Table volontairement séparée de `Affectation` (Annexe B, point 14) :
    un Administrateur plateforme n'obtient aucun droit métier sur une
    entreprise via cette table, il lui faut une Affectation dédiée.
    """

    __tablename__ = "attributions_roles_globaux"
    __table_args__ = (
        UniqueConstraint("utilisateur_id", "role_id"),
    )

    utilisateur_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("utilisateurs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False
    )
    actif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    role: Mapped["Role"] = relationship()