"""provisions

Revision ID: d8a4b3e6f172
Revises: c4f7a2d1e963
Create Date: 2026-10-08 15:00:00.000000

Cahier, section 8 "Écritures d'inventaire / de régularisation", point 2
"Provisions" : deux nouvelles tables, `provisions` (la fiche : type,
libellé, tiers éventuel, trois comptes rattachés — dotation/provision/
reprise — et le montant actuel dénormalisé) et `mouvements_provision`
(l'historique des dotations et reprises, chacune liée à son écriture dès
sa création — voir la docstring de `app/modules/provisions/models.py`),
plus les codes de permission `provision.*` au catalogue (même mécanisme
`INSERT ... ON CONFLICT DO UPDATE` que les migrations précédentes).
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8a4b3e6f172'
down_revision: Union[str, Sequence[str], None] = 'c4f7a2d1e963'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PERMISSIONS = {
    "provision.consulter": "Provisions — Consulter",
    "provision.creer": "Provisions — Créer",
    "provision.modifier": "Provisions — Modifier",
    "provision.valider": "Provisions — Doter / reprendre",
}


def upgrade() -> None:
    op.create_table(
        'provisions',
        sa.Column('libelle', sa.String(length=255), nullable=False),
        sa.Column('type_provision', sa.String(length=30), nullable=False),
        sa.Column('tiers_id', sa.UUID(), nullable=True),
        sa.Column('compte_dotation_id', sa.UUID(), nullable=False),
        sa.Column('compte_provision_id', sa.UUID(), nullable=False),
        sa.Column('compte_reprise_id', sa.UUID(), nullable=False),
        sa.Column('montant_actuel', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('statut', sa.String(length=20), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('cree_le', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('modifie_le', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('entreprise_id', sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "type_provision IN ('depreciation_creance', 'depreciation_stock', 'risque_charge')",
            name=op.f('ck_provisions_type_provision_valide'),
        ),
        sa.CheckConstraint(
            "statut IN ('active', 'soldee')",
            name=op.f('ck_provisions_statut_valide'),
        ),
        sa.CheckConstraint("montant_actuel >= 0", name=op.f('ck_provisions_montant_actuel_positif')),
        sa.ForeignKeyConstraint(
            ['compte_dotation_id'], ['comptes.id'],
            name=op.f('fk_provisions_compte_dotation_id_comptes'), ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['compte_provision_id'], ['comptes.id'],
            name=op.f('fk_provisions_compte_provision_id_comptes'), ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['compte_reprise_id'], ['comptes.id'],
            name=op.f('fk_provisions_compte_reprise_id_comptes'), ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['entreprise_id'], ['entreprises.id'],
            name=op.f('fk_provisions_entreprise_id_entreprises'), ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['tiers_id'], ['tiers.id'],
            name=op.f('fk_provisions_tiers_id_tiers'), ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_provisions')),
    )
    op.create_index(op.f('ix_provisions_compte_dotation_id'), 'provisions', ['compte_dotation_id'], unique=False)
    op.create_index(op.f('ix_provisions_compte_provision_id'), 'provisions', ['compte_provision_id'], unique=False)
    op.create_index(op.f('ix_provisions_compte_reprise_id'), 'provisions', ['compte_reprise_id'], unique=False)
    op.create_index(op.f('ix_provisions_entreprise_id'), 'provisions', ['entreprise_id'], unique=False)
    op.create_index(op.f('ix_provisions_tiers_id'), 'provisions', ['tiers_id'], unique=False)

    op.create_table(
        'mouvements_provision',
        sa.Column('provision_id', sa.UUID(), nullable=False),
        sa.Column('exercice_id', sa.UUID(), nullable=False),
        sa.Column('type_mouvement', sa.String(length=20), nullable=False),
        sa.Column('montant', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('date_mouvement', sa.Date(), nullable=False),
        sa.Column('ecriture_id', sa.UUID(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('entreprise_id', sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "type_mouvement IN ('dotation', 'reprise')",
            name=op.f('ck_mouvements_provision_type_mouvement_valide'),
        ),
        sa.CheckConstraint("montant > 0", name=op.f('ck_mouvements_provision_montant_positif')),
        sa.ForeignKeyConstraint(
            ['ecriture_id'], ['ecritures.id'],
            name=op.f('fk_mouvements_provision_ecriture_id_ecritures'), ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['entreprise_id'], ['entreprises.id'],
            name=op.f('fk_mouvements_provision_entreprise_id_entreprises'), ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['exercice_id'], ['exercices.id'],
            name=op.f('fk_mouvements_provision_exercice_id_exercices'), ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['provision_id'], ['provisions.id'],
            name=op.f('fk_mouvements_provision_provision_id_provisions'), ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_mouvements_provision')),
    )
    op.create_index(op.f('ix_mouvements_provision_ecriture_id'), 'mouvements_provision', ['ecriture_id'], unique=False)
    op.create_index(op.f('ix_mouvements_provision_entreprise_id'), 'mouvements_provision', ['entreprise_id'], unique=False)
    op.create_index(op.f('ix_mouvements_provision_exercice_id'), 'mouvements_provision', ['exercice_id'], unique=False)
    op.create_index(op.f('ix_mouvements_provision_provision_id'), 'mouvements_provision', ['provision_id'], unique=False)

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
    op.drop_index(op.f('ix_mouvements_provision_provision_id'), table_name='mouvements_provision')
    op.drop_index(op.f('ix_mouvements_provision_exercice_id'), table_name='mouvements_provision')
    op.drop_index(op.f('ix_mouvements_provision_entreprise_id'), table_name='mouvements_provision')
    op.drop_index(op.f('ix_mouvements_provision_ecriture_id'), table_name='mouvements_provision')
    op.drop_table('mouvements_provision')
    op.drop_index(op.f('ix_provisions_tiers_id'), table_name='provisions')
    op.drop_index(op.f('ix_provisions_entreprise_id'), table_name='provisions')
    op.drop_index(op.f('ix_provisions_compte_reprise_id'), table_name='provisions')
    op.drop_index(op.f('ix_provisions_compte_provision_id'), table_name='provisions')
    op.drop_index(op.f('ix_provisions_compte_dotation_id'), table_name='provisions')
    op.drop_table('provisions')