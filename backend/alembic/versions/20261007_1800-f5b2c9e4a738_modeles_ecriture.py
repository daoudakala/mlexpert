"""modeles ecriture

Revision ID: f5b2c9e4a738
Revises: e3a4b1f8d627
Create Date: 2026-10-07 18:00:00.000000

Crée les tables `modeles_ecriture` et `lignes_modele_ecriture` (cahier des
charges, section 8.2 "Saisie par modèle") et ajoute les codes de
permission `modele_ecriture.*` au catalogue (même mécanisme
`INSERT ... ON CONFLICT DO UPDATE` que les migrations précédentes, pour
rester idempotent si rejouée sur une base déjà peuplée par un script de
seed). Un modèle fige le compte et le sens de chaque ligne, jamais le
montant — voir `app/modules/comptabilite/models.py::ModeleEcriture`.
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f5b2c9e4a738'
down_revision: Union[str, Sequence[str], None] = 'e3a4b1f8d627'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PERMISSIONS = {
    "modele_ecriture.consulter": "Modèles d'écriture — Consulter",
    "modele_ecriture.creer": "Modèles d'écriture — Créer",
    "modele_ecriture.modifier": "Modèles d'écriture — Modifier",
}


def upgrade() -> None:
    op.create_table(
        'modeles_ecriture',
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('libelle', sa.String(length=150), nullable=False),
        sa.Column('journal_id', sa.UUID(), nullable=False),
        sa.Column('actif', sa.Boolean(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('cree_le', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('modifie_le', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('entreprise_id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ['entreprise_id'], ['entreprises.id'],
            name=op.f('fk_modeles_ecriture_entreprise_id_entreprises'), ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['journal_id'], ['journaux.id'],
            name=op.f('fk_modeles_ecriture_journal_id_journaux'), ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_modeles_ecriture')),
        sa.UniqueConstraint('entreprise_id', 'code', name=op.f('uq_modeles_ecriture_entreprise_id_code')),
    )
    op.create_index(op.f('ix_modeles_ecriture_entreprise_id'), 'modeles_ecriture', ['entreprise_id'], unique=False)
    op.create_index(op.f('ix_modeles_ecriture_journal_id'), 'modeles_ecriture', ['journal_id'], unique=False)

    op.create_table(
        'lignes_modele_ecriture',
        sa.Column('modele_id', sa.UUID(), nullable=False),
        sa.Column('compte_id', sa.UUID(), nullable=False),
        sa.Column('sens', sa.String(length=10), nullable=False),
        sa.Column('libelle', sa.String(length=255), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('entreprise_id', sa.UUID(), nullable=False),
        sa.CheckConstraint("sens IN ('debit', 'credit')", name=op.f('ck_lignes_modele_ecriture_sens_ligne_modele_valide')),
        sa.ForeignKeyConstraint(
            ['compte_id'], ['comptes.id'],
            name=op.f('fk_lignes_modele_ecriture_compte_id_comptes'), ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['entreprise_id'], ['entreprises.id'],
            name=op.f('fk_lignes_modele_ecriture_entreprise_id_entreprises'), ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['modele_id'], ['modeles_ecriture.id'],
            name=op.f('fk_lignes_modele_ecriture_modele_id_modeles_ecriture'), ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_lignes_modele_ecriture')),
    )
    op.create_index(op.f('ix_lignes_modele_ecriture_compte_id'), 'lignes_modele_ecriture', ['compte_id'], unique=False)
    op.create_index(op.f('ix_lignes_modele_ecriture_entreprise_id'), 'lignes_modele_ecriture', ['entreprise_id'], unique=False)
    op.create_index(op.f('ix_lignes_modele_ecriture_modele_id'), 'lignes_modele_ecriture', ['modele_id'], unique=False)

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
    op.drop_index(op.f('ix_lignes_modele_ecriture_modele_id'), table_name='lignes_modele_ecriture')
    op.drop_index(op.f('ix_lignes_modele_ecriture_entreprise_id'), table_name='lignes_modele_ecriture')
    op.drop_index(op.f('ix_lignes_modele_ecriture_compte_id'), table_name='lignes_modele_ecriture')
    op.drop_table('lignes_modele_ecriture')
    op.drop_index(op.f('ix_modeles_ecriture_journal_id'), table_name='modeles_ecriture')
    op.drop_index(op.f('ix_modeles_ecriture_entreprise_id'), table_name='modeles_ecriture')
    op.drop_table('modeles_ecriture')
