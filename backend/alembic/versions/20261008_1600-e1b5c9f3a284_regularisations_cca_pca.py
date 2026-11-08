"""regularisations cca pca

Revision ID: e1b5c9f3a284
Revises: d8a4b3e6f172
Create Date: 2026-10-08 16:00:00.000000

Cahier, section 8 "Écritures d'inventaire / de régularisation", point 3
"Charges et produits constatés d'avance (CCA/PCA)" : une seule nouvelle
table, `regularisations_cca_pca` (l'événement de régularisation, lié
directement à son écriture dès sa création — voir la docstring de
`app/modules/regularisations/models.py`), plus les codes de permission
`regularisation.*` au catalogue (même mécanisme `INSERT ... ON CONFLICT
DO UPDATE` que les migrations précédentes).
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1b5c9f3a284'
down_revision: Union[str, Sequence[str], None] = 'd8a4b3e6f172'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PERMISSIONS = {
    "regularisation.consulter": "Régularisations CCA/PCA — Consulter",
    "regularisation.creer": "Régularisations CCA/PCA — Créer",
}


def upgrade() -> None:
    op.create_table(
        'regularisations_cca_pca',
        sa.Column('libelle', sa.String(length=255), nullable=False),
        sa.Column('type_regularisation', sa.String(length=30), nullable=False),
        sa.Column('exercice_id', sa.UUID(), nullable=False),
        sa.Column('compte_origine_id', sa.UUID(), nullable=False),
        sa.Column('compte_regularisation_id', sa.UUID(), nullable=False),
        sa.Column('montant', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('date_regularisation', sa.Date(), nullable=False),
        sa.Column('ecriture_id', sa.UUID(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('cree_le', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('modifie_le', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('entreprise_id', sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "type_regularisation IN ('charge_constatee_avance', 'produit_constate_avance')",
            name=op.f('ck_regularisations_cca_pca_type_regularisation_valide'),
        ),
        sa.CheckConstraint("montant > 0", name=op.f('ck_regularisations_cca_pca_montant_positif')),
        sa.ForeignKeyConstraint(
            ['compte_origine_id'], ['comptes.id'],
            name=op.f('fk_regularisations_cca_pca_compte_origine_id_comptes'), ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['compte_regularisation_id'], ['comptes.id'],
            name=op.f('fk_regularisations_cca_pca_compte_regularisation_id_comptes'), ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['ecriture_id'], ['ecritures.id'],
            name=op.f('fk_regularisations_cca_pca_ecriture_id_ecritures'), ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['entreprise_id'], ['entreprises.id'],
            name=op.f('fk_regularisations_cca_pca_entreprise_id_entreprises'), ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['exercice_id'], ['exercices.id'],
            name=op.f('fk_regularisations_cca_pca_exercice_id_exercices'), ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_regularisations_cca_pca')),
    )
    op.create_index(op.f('ix_regularisations_cca_pca_compte_origine_id'), 'regularisations_cca_pca', ['compte_origine_id'], unique=False)
    op.create_index(op.f('ix_regularisations_cca_pca_compte_regularisation_id'), 'regularisations_cca_pca', ['compte_regularisation_id'], unique=False)
    op.create_index(op.f('ix_regularisations_cca_pca_ecriture_id'), 'regularisations_cca_pca', ['ecriture_id'], unique=False)
    op.create_index(op.f('ix_regularisations_cca_pca_entreprise_id'), 'regularisations_cca_pca', ['entreprise_id'], unique=False)
    op.create_index(op.f('ix_regularisations_cca_pca_exercice_id'), 'regularisations_cca_pca', ['exercice_id'], unique=False)

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
    op.drop_index(op.f('ix_regularisations_cca_pca_exercice_id'), table_name='regularisations_cca_pca')
    op.drop_index(op.f('ix_regularisations_cca_pca_entreprise_id'), table_name='regularisations_cca_pca')
    op.drop_index(op.f('ix_regularisations_cca_pca_ecriture_id'), table_name='regularisations_cca_pca')
    op.drop_index(op.f('ix_regularisations_cca_pca_compte_regularisation_id'), table_name='regularisations_cca_pca')
    op.drop_index(op.f('ix_regularisations_cca_pca_compte_origine_id'), table_name='regularisations_cca_pca')
    op.drop_table('regularisations_cca_pca')