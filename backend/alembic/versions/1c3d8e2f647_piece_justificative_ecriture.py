"""piece justificative rattachable a une ecriture

Revision ID: a1c3d8e2f647
Revises: f5b2c9e4a738
Create Date: 2026-10-07 19:00:00.000000

Ajoute `documents.ecriture_id` (NULLABLE, `ondelete=SET NULL`) : un
document déjà déposé peut être rattaché après coup à une écriture comme
pièce justificative (cahier des charges, section 8.2) — voir la note de
tête de fichier de `app/modules/documents/models.py::Document` pour la
distinction avec le `ecriture_id` d'autres modules (immobilisations,
paie, stocks), qui porte le sens inverse. Pas de nouveau code de
permission : le rattachement/détachement passe par `document.modifier`,
déjà au catalogue.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c3d8e2f647'
down_revision: Union[str, Sequence[str], None] = 'f5b2c9e4a738'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('ecriture_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_documents_ecriture_id'), 'documents', ['ecriture_id'], unique=False)
    op.create_foreign_key(
        op.f('fk_documents_ecriture_id_ecritures'),
        'documents', 'ecritures',
        ['ecriture_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint(op.f('fk_documents_ecriture_id_ecritures'), 'documents', type_='foreignkey')
    op.drop_index(op.f('ix_documents_ecriture_id'), table_name='documents')
    op.drop_column('documents', 'ecriture_id')