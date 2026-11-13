"""Autorise la classe 9 dans le plan comptable.

Revision ID: e9b2c4d6a813
Revises: d8a1b3c5f702
"""

from alembic import op

revision = "e9b2c4d6a813"
down_revision = "d8a1b3c5f702"
branch_labels = None
depends_on = None


def _nom_contrainte_classe(connexion) -> str | None:
    """Retrouve le nom réel de la contrainte CHECK sur `classe` (il dépend
    de la convention de nommage de la base)."""
    resultat = connexion.exec_driver_sql(
        """
        SELECT c.conname
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        WHERE t.relname = 'comptes'
          AND c.contype = 'c'
          AND pg_get_constraintdef(c.oid) ILIKE '%classe%'
          AND pg_get_constraintdef(c.oid) NOT ILIKE '%collectif%'
        """
    ).fetchone()
    return resultat[0] if resultat else None


def _remplacer(borne_haute: int) -> None:
    connexion = op.get_bind()
    nom = _nom_contrainte_classe(connexion) or "ck_comptes_classe_valide"
    op.execute(f'ALTER TABLE comptes DROP CONSTRAINT IF EXISTS "{nom}"')
    op.execute(f'ALTER TABLE comptes ADD CONSTRAINT "{nom}" CHECK (classe BETWEEN 1 AND {borne_haute})')


def upgrade() -> None:
    _remplacer(9)


def downgrade() -> None:
    # Échoue volontairement s'il existe encore des comptes de classe 9.
    _remplacer(8)