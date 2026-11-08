"""ecritures recurrentes

Revision ID: c4f7a2d1e963
Revises: b3e6f1a9c852
Create Date: 2026-10-07 21:30:00.000000

Cahier, section 8.4 "Écritures récurrentes" : deux nouvelles tables,
`ecritures_recurrentes` (le patron : journal, périodicité, fenêtre de
validité, prochaine échéance) et `lignes_ecriture_recurrente` (compte +
sens + montant FIXE, à la différence d'un modèle — voir la docstring de
`EcritureRecurrente` dans `app/modules/comptabilite/models.py`), plus les
codes de permission `ecriture_recurrente.*` au catalogue (même mécanisme
`INSERT ... ON CONFLICT DO UPDATE` que les migrations précédentes).
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4f7a2d1e963'
down_revision: Union[str, Sequence[str], None] = 'b3e6f1a9c852'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PERMISSIONS = {
    "ecriture_recurrente.consulter": "Écritures récurrentes — Consulter",
    "ecriture_recurrente.creer": "Écritures récurrentes — Créer",
    "ecriture_recurrente.modifier": "Écritures récurrentes — Modifier",
    "ecriture_recurrente.generer": "Écritures récurrentes — Générer les échéances",
}


def upgrade() -> None:
    op.create_table(
        'ecritures_recurrentes',
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('libelle', sa.String(length=150), nullable=False),
        sa.Column('journal_id', sa.UUID(), nullable=False),
        sa.Column('periodicite', sa.String(length=20), nullable=False),
        sa.Column('reference_piece', sa.String(length=100), nullable=True),
        sa.Column('date_debut', sa.Date(), nullable=False),
        sa.Column('date_fin', sa.Date(), nullable=True),
        sa.Column('prochaine_echeance', sa.Date(), nullable=False),
        sa.Column('actif', sa.Boolean(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('cree_le', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('modifie_le', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('entreprise_id', sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "periodicite IN ('mensuelle', 'trimestrielle', 'annuelle')",
            name=op.f('ck_ecritures_recurrentes_periodicite_recurrence_valide'),
        ),
        sa.ForeignKeyConstraint(
            ['entreprise_id'], ['entreprises.id'],
            name=op.f('fk_ecritures_recurrentes_entreprise_id_entreprises'), ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['journal_id'], ['journaux.id'],
            name=op.f('fk_ecritures_recurrentes_journal_id_journaux'), ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_ecritures_recurrentes')),
        sa.UniqueConstraint('entreprise_id', 'code', name=op.f('uq_ecritures_recurrentes_entreprise_id_code')),
    )
    op.create_index(op.f('ix_ecritures_recurrentes_entreprise_id'), 'ecritures_recurrentes', ['entreprise_id'], unique=False)
    op.create_index(op.f('ix_ecritures_recurrentes_journal_id'), 'ecritures_recurrentes', ['journal_id'], unique=False)

    op.create_table(
        'lignes_ecriture_recurrente',
        sa.Column('ecriture_recurrente_id', sa.UUID(), nullable=False),
        sa.Column('compte_id', sa.UUID(), nullable=False),
        sa.Column('sens', sa.String(length=10), nullable=False),
        sa.Column('montant', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('libelle', sa.String(length=255), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('entreprise_id', sa.UUID(), nullable=False),
        sa.CheckConstraint("sens IN ('debit', 'credit')", name=op.f('ck_lignes_ecriture_recurrente_sens_ligne_recurrente_valide')),
        sa.CheckConstraint("montant > 0", name=op.f('ck_lignes_ecriture_recurrente_montant_ligne_recurrente_positif')),
        sa.ForeignKeyConstraint(
            ['compte_id'], ['comptes.id'],
            name=op.f('fk_lignes_ecriture_recurrente_compte_id_comptes'), ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['ecriture_recurrente_id'], ['ecritures_recurrentes.id'],
            name=op.f('fk_lignes_ecriture_recurrente_ecriture_recurrente_id_ecritures_recurrentes'), ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['entreprise_id'], ['entreprises.id'],
            name=op.f('fk_lignes_ecriture_recurrente_entreprise_id_entreprises'), ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_lignes_ecriture_recurrente')),
    )
    op.create_index(op.f('ix_lignes_ecriture_recurrente_compte_id'), 'lignes_ecriture_recurrente', ['compte_id'], unique=False)
    op.create_index(op.f('ix_lignes_ecriture_recurrente_ecriture_recurrente_id'), 'lignes_ecriture_recurrente', ['ecriture_recurrente_id'], unique=False)
    op.create_index(op.f('ix_lignes_ecriture_recurrente_entreprise_id'), 'lignes_ecriture_recurrente', ['entreprise_id'], unique=False)

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
    op.drop_index(op.f('ix_lignes_ecriture_recurrente_entreprise_id'), table_name='lignes_ecriture_recurrente')
    op.drop_index(op.f('ix_lignes_ecriture_recurrente_ecriture_recurrente_id'), table_name='lignes_ecriture_recurrente')
    op.drop_index(op.f('ix_lignes_ecriture_recurrente_compte_id'), table_name='lignes_ecriture_recurrente')
    op.drop_table('lignes_ecriture_recurrente')
    op.drop_index(op.f('ix_ecritures_recurrentes_journal_id'), table_name='ecritures_recurrentes')
    op.drop_index(op.f('ix_ecritures_recurrentes_entreprise_id'), table_name='ecritures_recurrentes')
    op.drop_table('ecritures_recurrentes')