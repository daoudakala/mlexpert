"""type journal à-nouveaux

Revision ID: e3a4b1f8d627
Revises: d4f8e2a7c915
Create Date: 2026-10-07 17:00:00.000000

Ajoute 'a_nouveaux' aux valeurs autorisées de `journaux.type_journal`
(cahier, section 7.2 "gestion des à-nouveaux") — purement une contrainte
CHECK à élargir, pas de colonne nouvelle.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e3a4b1f8d627'
down_revision: Union[str, Sequence[str], None] = 'd4f8e2a7c915'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ANCIENNE_CONTRAINTE = (
    "type_journal IN ('achats', 'ventes', 'banque', 'caisse', 'operations_diverses')"
)
NOUVELLE_CONTRAINTE = (
    "type_journal IN ('achats', 'ventes', 'banque', 'caisse', "
    "'operations_diverses', 'a_nouveaux')"
)


def upgrade() -> None:
    op.drop_constraint("type_journal_valide", "journaux", type_="check")
    op.create_check_constraint("type_journal_valide", "journaux", NOUVELLE_CONTRAINTE)


def downgrade() -> None:
    op.drop_constraint("type_journal_valide", "journaux", type_="check")
    op.create_check_constraint("type_journal_valide", "journaux", ANCIENNE_CONTRAINTE)
