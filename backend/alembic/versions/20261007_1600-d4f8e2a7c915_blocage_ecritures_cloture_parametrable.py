"""blocage écritures clôture paramétrable

Revision ID: d4f8e2a7c915
Revises: c8e71fa2b4d3
Create Date: 2026-10-07 16:00:00.000000

Ajoute `entreprises.blocage_ecritures_cloture` (cahier, section 7.2 :
"blocage des écritures après clôture selon paramétrage"). `server_default
'true'` préserve le comportement historique — strict et non
paramétrable — pour toute entreprise déjà en base, voir le docstring de
`models.py`.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4f8e2a7c915'
down_revision: Union[str, Sequence[str], None] = 'c8e71fa2b4d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'entreprises',
        sa.Column(
            'blocage_ecritures_cloture',
            sa.Boolean(),
            server_default=sa.text('true'),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column('entreprises', 'blocage_ecritures_cloture')
