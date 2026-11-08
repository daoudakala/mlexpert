"""permission notification.administrer

Revision ID: d4e8b1a7c3f9
Revises: c7d4e9f21a68
Create Date: 2026-10-09 13:00:00.000000

Ajoute la permission `notification.administrer` (Étape 5 — gate la route
de détection d'alertes `POST .../detecter-alertes`), même mécanique
idempotente que les migrations précédentes de permissions.
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd4e8b1a7c3f9'
down_revision: Union[str, Sequence[str], None] = 'c7d4e9f21a68'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    permissions = sa.table(
        "permissions",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String),
        sa.column("libelle", sa.String),
    )
    insertion = postgresql.insert(permissions).values(
        [{"id": uuid.uuid4(), "code": "notification.administrer", "libelle": "Notifications — Administrer (détection d'alertes)"}]
    )
    insertion = insertion.on_conflict_do_update(
        index_elements=["code"], set_={"libelle": insertion.excluded.libelle}
    )
    op.get_bind().execute(insertion)


def downgrade() -> None:
    op.get_bind().execute(sa.text("DELETE FROM permissions WHERE code = 'notification.administrer'"))