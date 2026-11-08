"""tiers_id sur affectation et document + contrainte affectation assouplie

Revision ID: b5e3a8d2c761
Revises: a2f6c9e1b438
Create Date: 2026-10-14 23:05:00.000000

Deux changements de schéma liés à l'auto-gestion des entreprises (Étape 6) :

1. La contrainte unique sur `affectations(utilisateur_id, entreprise_id)`
   empêchait de ré-affecter un utilisateur précédemment retiré (actif=False)
   de la même entreprise : la ligne inactive bloquait toute nouvelle ligne
   pour la même paire, alors que la résolution des droits
   (`RepositoryAffectation.obtenir_active`) ne regarde que `actif=True`.
   Remplacée par un index unique PARTIEL (`WHERE actif`), qui n'impose
   l'unicité qu'entre affectations actives — un historique de plusieurs
   lignes inactives pour la même paire devient possible (et inoffensif,
   c'est de l'historique d'audit).

2. `Affectation.tiers_id` (nullable) et `Document.tiers_id` (nullable) :
   rattachent respectivement un compte du portail client à SON dossier
   (`Tiers`), et un document à un client précis. Les deux `NULL` par
   défaut, rétrocompatibles : une affectation sans `tiers_id` reste un
   accès "cabinet" classique (collaborateur interne, ou ancien compte
   client non encore rattaché) ; un document sans `tiers_id` reste
   visible par TOUS les clients de l'entreprise s'il est `visible_client`
   (comportement inchangé, voir la note de tête de `documents/models.py`).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b5e3a8d2c761'
down_revision: Union[str, Sequence[str], None] = 'a2f6c9e1b438'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("uq_affectations_utilisateur_id", "affectations", type_="unique")
    op.create_index(
        "uq_affectations_utilisateur_entreprise_actif",
        "affectations",
        ["utilisateur_id", "entreprise_id"],
        unique=True,
        postgresql_where=sa.text("actif"),
    )

    op.add_column(
        "affectations",
        sa.Column("tiers_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_affectations_tiers_id_tiers",
        "affectations",
        "tiers",
        ["tiers_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_affectations_tiers_id", "affectations", ["tiers_id"])

    op.add_column(
        "documents",
        sa.Column("tiers_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_documents_tiers_id_tiers",
        "documents",
        "tiers",
        ["tiers_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_documents_tiers_id", "documents", ["tiers_id"])


def downgrade() -> None:
    op.drop_index("ix_documents_tiers_id", table_name="documents")
    op.drop_constraint("fk_documents_tiers_id_tiers", "documents", type_="foreignkey")
    op.drop_column("documents", "tiers_id")

    op.drop_index("ix_affectations_tiers_id", table_name="affectations")
    op.drop_constraint("fk_affectations_tiers_id_tiers", "affectations", type_="foreignkey")
    op.drop_column("affectations", "tiers_id")

    op.drop_index("uq_affectations_utilisateur_entreprise_actif", table_name="affectations")
    op.create_unique_constraint(
        "uq_affectations_utilisateur_id", "affectations", ["utilisateur_id", "entreprise_id"]
    )