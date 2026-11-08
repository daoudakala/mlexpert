"""inventaires physiques

Revision ID: a93d4f6e2b17
Revises: f27c6a8d9e15
Create Date: 2026-10-08 18:00:00.000000

Cahier, section 8, point 5 "Stocks (variation de stock en fin
d'exercice)" : table `inventaires_physiques` (comptage physique d'un
article, écart contre le stock théorique — voir la docstring de tête de
fichier de `app/modules/stocks/models.py`), plus les codes de permission
`inventaire_physique.consulter`/`inventaire_physique.creer`.
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a93d4f6e2b17'
down_revision: Union[str, Sequence[str], None] = 'f27c6a8d9e15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PERMISSIONS = {
    "inventaire_physique.consulter": "Inventaires physiques — Consulter",
    "inventaire_physique.creer": "Inventaires physiques — Créer",
}


def upgrade() -> None:
    op.create_table(
        'inventaires_physiques',
        sa.Column('article_id', sa.UUID(), nullable=False),
        sa.Column('exercice_id', sa.UUID(), nullable=False),
        sa.Column('date_inventaire', sa.Date(), nullable=False),
        sa.Column('quantite_theorique', sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column('quantite_physique', sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column('ecart', sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column('mouvement_ajustement_id', sa.UUID(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('cree_le', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('modifie_le', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('entreprise_id', sa.UUID(), nullable=False),
        sa.CheckConstraint('quantite_physique >= 0', name=op.f('ck_inventaires_physiques_quantite_physique_positive')),
        sa.ForeignKeyConstraint(
            ['article_id'], ['articles.id'],
            name=op.f('fk_inventaires_physiques_article_id_articles'), ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['entreprise_id'], ['entreprises.id'],
            name=op.f('fk_inventaires_physiques_entreprise_id_entreprises'), ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['exercice_id'], ['exercices.id'],
            name=op.f('fk_inventaires_physiques_exercice_id_exercices'), ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['mouvement_ajustement_id'], ['mouvements_stock.id'],
            name=op.f('fk_inventaires_physiques_mouvement_ajustement_id_mouvements_stock'), ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_inventaires_physiques')),
    )
    op.create_index(op.f('ix_inventaires_physiques_article_id'), 'inventaires_physiques', ['article_id'], unique=False)
    op.create_index(op.f('ix_inventaires_physiques_entreprise_id'), 'inventaires_physiques', ['entreprise_id'], unique=False)
    op.create_index(op.f('ix_inventaires_physiques_exercice_id'), 'inventaires_physiques', ['exercice_id'], unique=False)

    permissions = sa.table(
        "permissions",
        sa.column("id", sa.dialects.postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String),
        sa.column("libelle", sa.String),
    )
    connexion = op.get_bind()
    lignes = [{"id": uuid.uuid4(), "code": code, "libelle": libelle} for code, libelle in PERMISSIONS.items()]
    insertion = sa.dialects.postgresql.insert(permissions).values(lignes)
    insertion = insertion.on_conflict_do_update(
        index_elements=["code"], set_={"libelle": insertion.excluded.libelle}
    )
    connexion.execute(insertion)


def downgrade() -> None:
    connexion = op.get_bind()
    codes = tuple(PERMISSIONS.keys())
    connexion.execute(
        sa.text("DELETE FROM permissions WHERE code IN :codes").bindparams(
            sa.bindparam("codes", expanding=True)
        ),
        {"codes": codes},
    )
    op.drop_index(op.f('ix_inventaires_physiques_exercice_id'), table_name='inventaires_physiques')
    op.drop_index(op.f('ix_inventaires_physiques_entreprise_id'), table_name='inventaires_physiques')
    op.drop_index(op.f('ix_inventaires_physiques_article_id'), table_name='inventaires_physiques')
    op.drop_table('inventaires_physiques')