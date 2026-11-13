"""Reprise automatique des immobilisations depuis les écritures.

- `immobilisations.ligne_acquisition_id` : lien (unique) vers la ligne
  d'écriture d'acquisition dont la fiche est issue.
- `acquisitions_ignorees` : lignes d'écriture sur un compte 21-27 que le
  comptable a choisi de ne pas reprendre.

Revision ID: f1c3e5a7b904
Revises: e9b2c4d6a813
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f1c3e5a7b904"
down_revision = "e9b2c4d6a813"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "immobilisations",
        sa.Column("ligne_acquisition_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_immobilisations_ligne_acquisition_id",
        "immobilisations",
        "lignes_ecriture",
        ["ligne_acquisition_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_immobilisations_ligne_acquisition_id", "immobilisations", ["ligne_acquisition_id"]
    )

    op.create_table(
        "acquisitions_ignorees",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "entreprise_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("entreprises.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "ligne_ecriture_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("lignes_ecriture.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.UniqueConstraint("ligne_ecriture_id", name="uq_acquisitions_ignorees_ligne_ecriture_id"),
    )


def downgrade() -> None:
    op.drop_table("acquisitions_ignorees")
    op.drop_constraint("uq_immobilisations_ligne_acquisition_id", "immobilisations", type_="unique")
    op.drop_constraint("fk_immobilisations_ligne_acquisition_id", "immobilisations", type_="foreignkey")
    op.drop_column("immobilisations", "ligne_acquisition_id")