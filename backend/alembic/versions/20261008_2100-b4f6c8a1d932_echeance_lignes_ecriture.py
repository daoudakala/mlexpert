"""échéancier clients/fournisseurs — date_echeance sur lignes_ecriture

Revision ID: b4f6c8a1d932
Revises: a93d4f6e2b17
Create Date: 2026-10-08 21:00:00.000000

Cahier, sections 8.4 ("Échéanciers clients/fournisseurs") et 13.2/13.3
(échéances, échéances dépassées) : ajoute `date_echeance` (nullable) sur
`lignes_ecriture`. Voir la docstring de tête de fichier de
`app/modules/comptabilite/models.py` pour le détail du calcul (auto, via
`Tiers.delai_paiement_jours`, ou saisie explicite).

Colonne nullable sur une table existante : aucune donnée à migrer.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4f6c8a1d932'
down_revision: Union[str, Sequence[str], None] = 'a93d4f6e2b17'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('lignes_ecriture', sa.Column('date_echeance', sa.Date(), nullable=True))
    op.create_index(
        op.f('ix_lignes_ecriture_date_echeance'), 'lignes_ecriture', ['date_echeance'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_lignes_ecriture_date_echeance'), table_name='lignes_ecriture')
    op.drop_column('lignes_ecriture', 'date_echeance')