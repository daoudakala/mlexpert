"""hiérarchie comptes parent/enfant

Revision ID: b2d4f8a913c6
Revises: 9a3c7e5b4d21
Create Date: 2026-10-07 14:30:00.000000

Ajoute `comptes.compte_parent_id`, une auto-référence nullable vers
`comptes.id` (`ON DELETE RESTRICT`, voir la note de tête de fichier de
`models.py` : un compte ayant des enfants ne peut jamais se retrouver
orphelin). Purement additif : toutes les lignes existantes prennent
`compte_parent_id = NULL`, ce qui revient à dire qu'aucun compte
existant n'a de parent — correct, la notion n'existait pas avant cette
migration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b2d4f8a913c6'
down_revision: Union[str, Sequence[str], None] = '9a3c7e5b4d21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "comptes",
        sa.Column("compte_parent_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_comptes_compte_parent_id", "comptes", ["compte_parent_id"], unique=False
    )
    op.create_foreign_key(
        "fk_comptes_compte_parent_id_comptes",
        "comptes",
        "comptes",
        ["compte_parent_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_comptes_compte_parent_id_comptes", "comptes", type_="foreignkey")
    op.drop_index("ix_comptes_compte_parent_id", table_name="comptes")
    op.drop_column("comptes", "compte_parent_id")
