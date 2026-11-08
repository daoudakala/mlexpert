"""module interlocuteurs

Revision ID: c8e71fa2b4d3
Revises: b2d4f8a913c6
Create Date: 2026-10-07 15:30:00.000000

Crée la table `interlocuteurs` (cahier des charges, section 7.1 :
dirigeants, associés, responsables financiers, comptables, contacts) et
ajoute les codes de permission `interlocuteur.*` au catalogue (même
mécanisme `INSERT ... ON CONFLICT DO UPDATE` que la migration
`9a3c7e5b4d21`, pour rester idempotent si rejouée sur une base déjà
peuplée par un script de seed).
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8e71fa2b4d3'
down_revision: Union[str, Sequence[str], None] = 'b2d4f8a913c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PERMISSIONS = {
    "interlocuteur.consulter": "Interlocuteurs — Consulter",
    "interlocuteur.creer": "Interlocuteurs — Créer",
    "interlocuteur.modifier": "Interlocuteurs — Modifier",
}


def upgrade() -> None:
    op.create_table(
        'interlocuteurs',
        sa.Column('nom', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=30), nullable=False),
        sa.Column('fonction', sa.String(length=150), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('telephone', sa.String(length=30), nullable=True),
        sa.Column('pourcentage_detention', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('notes', sa.String(length=500), nullable=True),
        sa.Column('actif', sa.Boolean(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('cree_le', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('modifie_le', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('entreprise_id', sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "role IN ('dirigeant', 'associe', 'responsable_financier', 'comptable', 'contact')",
            name=op.f('ck_interlocuteurs_role_interlocuteur_valide'),
        ),
        sa.CheckConstraint(
            "pourcentage_detention IS NULL OR "
            "(pourcentage_detention >= 0 AND pourcentage_detention <= 100)",
            name=op.f('ck_interlocuteurs_pourcentage_detention_valide'),
        ),
        sa.ForeignKeyConstraint(
            ['entreprise_id'], ['entreprises.id'],
            name=op.f('fk_interlocuteurs_entreprise_id_entreprises'), ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_interlocuteurs')),
    )
    op.create_index(op.f('ix_interlocuteurs_entreprise_id'), 'interlocuteurs', ['entreprise_id'], unique=False)
    op.create_index(op.f('ix_interlocuteurs_nom'), 'interlocuteurs', ['nom'], unique=False)
    op.create_index(op.f('ix_interlocuteurs_role'), 'interlocuteurs', ['role'], unique=False)

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
    op.drop_index(op.f('ix_interlocuteurs_role'), table_name='interlocuteurs')
    op.drop_index(op.f('ix_interlocuteurs_nom'), table_name='interlocuteurs')
    op.drop_index(op.f('ix_interlocuteurs_entreprise_id'), table_name='interlocuteurs')
    op.drop_table('interlocuteurs')
