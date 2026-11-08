"""lettrage manuel (comptes generaux / tiers)

Revision ID: b3e6f1a9c852
Revises: a1c3d8e2f647
Create Date: 2026-10-07 20:10:00.000000

Pas de changement de schéma : `lignes_ecriture.code_lettrage` existe déjà
(posé pour le rapprochement bancaire de `tresorerie`) et sert aussi de
support de stockage au lettrage manuel (cahier, section 8.2) — voir
`app/modules/comptabilite/service.py::ServiceComptabilite.lettrer`. Cette
migration ajoute seulement les codes de permission `lettrage.creer` et
`lettrage.annuler` au catalogue (la lecture des lignes candidates reste
couverte par `ecriture.consulter`, déjà au catalogue).
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3e6f1a9c852'
down_revision: Union[str, Sequence[str], None] = 'a1c3d8e2f647'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PERMISSIONS = {
    "lettrage.creer": "Lettrage manuel — Créer",
    "lettrage.annuler": "Lettrage manuel — Annuler",
}


def upgrade() -> None:
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