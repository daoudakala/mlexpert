"""module notifications

Revision ID: f58b78994a51
Revises: b4f6c8a1d932
Create Date: 2026-10-09 12:00:00.000000

Crée les deux tables de l'infrastructure de notifications (cahier des
charges, sections 20 et 24 — voir la docstring de
`app/modules/notifications/models.py`) et ajoute la permission
`notification.consulter` au catalogue (même mécanique que la migration
9a3c7e5b4d21 "catalogue des permissions" : `ON CONFLICT DO UPDATE` sur le
libellé, idempotent).
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f58b78994a51'
down_revision: Union[str, Sequence[str], None] = 'b4f6c8a1d932'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("cree_le", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("modifie_le", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("entreprise_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("destinataire_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type_notification", sa.String(length=50), nullable=False),
        sa.Column("niveau_criticite", sa.String(length=20), nullable=False),
        sa.Column("canal", sa.String(length=20), nullable=False),
        sa.Column("titre", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("type_objet", sa.String(length=100), nullable=True),
        sa.Column("objet_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("lu", sa.Boolean(), nullable=False),
        sa.Column("lu_le", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["entreprise_id"], ["entreprises.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["destinataire_id"], ["utilisateurs.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_notifications_entreprise_id", "notifications", ["entreprise_id"])
    op.create_index("ix_notifications_destinataire_id", "notifications", ["destinataire_id"])
    op.create_index("ix_notifications_type_notification", "notifications", ["type_notification"])
    op.create_index("ix_notifications_objet_id", "notifications", ["objet_id"])
    op.create_index("ix_notifications_lu", "notifications", ["lu"])

    op.create_table(
        "preferences_notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("cree_le", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("modifie_le", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("utilisateur_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type_notification", sa.String(length=50), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("niveau_minimum", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(["utilisateur_id"], ["utilisateurs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "utilisateur_id", "type_notification", name="uq_preference_utilisateur_type"
        ),
    )
    op.create_index(
        "ix_preferences_notifications_utilisateur_id", "preferences_notifications", ["utilisateur_id"]
    )

    permissions = sa.table(
        "permissions",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String),
        sa.column("libelle", sa.String),
    )
    insertion = postgresql.insert(permissions).values(
        [{"id": uuid.uuid4(), "code": "notification.consulter", "libelle": "Notifications — Consulter"}]
    )
    insertion = insertion.on_conflict_do_update(
        index_elements=["code"], set_={"libelle": insertion.excluded.libelle}
    )
    op.get_bind().execute(insertion)


def downgrade() -> None:
    op.get_bind().execute(sa.text("DELETE FROM permissions WHERE code = 'notification.consulter'"))
    op.drop_table("preferences_notifications")
    op.drop_table("notifications")