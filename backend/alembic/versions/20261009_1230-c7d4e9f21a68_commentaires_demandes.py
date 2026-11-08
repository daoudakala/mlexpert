"""commentaires_demandes

Revision ID: c7d4e9f21a68
Revises: f58b78994a51
Create Date: 2026-10-09 12:30:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "c7d4e9f21a68"
down_revision = "f58b78994a51"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "commentaires_demandes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cree_le", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("modifie_le", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("entreprise_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("demande_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("auteur_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message", sa.String(length=2000), nullable=False),
        sa.ForeignKeyConstraint(["entreprise_id"], ["entreprises.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["demande_id"], ["demandes_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["auteur_id"], ["utilisateurs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_commentaires_demandes_entreprise_id", "commentaires_demandes", ["entreprise_id"]
    )
    op.create_index(
        "ix_commentaires_demandes_demande_id", "commentaires_demandes", ["demande_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_commentaires_demandes_demande_id", table_name="commentaires_demandes")
    op.drop_index("ix_commentaires_demandes_entreprise_id", table_name="commentaires_demandes")
    op.drop_table("commentaires_demandes")