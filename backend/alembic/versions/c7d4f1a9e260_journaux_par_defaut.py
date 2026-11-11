"""Journaux par défaut (BQ, CA, AC, VT, OD, RAN) pour les entreprises existantes.

Les entreprises créées après ce changement reçoivent ces journaux à la
création (`ServiceEntreprises.creer_entreprise`) ; cette migration rattrape
celles qui existaient déjà. Idempotente : un journal déjà présent (même code)
n'est ni recréé ni modifié, et le report à nouveau n'est pas dupliqué.

Revision ID: c7d4f1a9e260
Revises: b5e3a8d2c761
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.orm import Session

from app.modules.comptabilite.journaux_par_defaut import creer_journaux_par_defaut

revision = "c7d4f1a9e260"
down_revision = "b5e3a8d2c761"
branch_labels = None
depends_on = None


def upgrade() -> None:
    session = Session(bind=op.get_bind())
    for (entreprise_id,) in session.execute(sa.text("SELECT id FROM entreprises")).all():
        creer_journaux_par_defaut(session, entreprise_id)
    session.flush()


def downgrade() -> None:
    # Volontairement vide : des écritures peuvent déjà référencer ces
    # journaux, on ne les supprime jamais automatiquement.
    pass