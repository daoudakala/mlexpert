"""rôle administrateur d'entreprise

Revision ID: a2f6c9e1b438
Revises: d4e8b1a7c3f9
Create Date: 2026-10-14 22:30:00.000000

Seed du rôle non-plateforme "Administrateur d'entreprise" (Étape 6 —
auto-gestion des entreprises) : une entreprise nouvellement créée affecte
désormais automatiquement son créateur à ce rôle (voir
`ServiceEntreprises.creer_entreprise`), ce qui lui permet ensuite
d'inviter lui-même ses propres collaborateurs et comptes clients, sans
dépendre de l'administrateur de plateforme pour chaque affectation.

Bundle de permissions délibérément centré sur la GESTION de l'entreprise
(accès, tiers, documents, portail client) plutôt que sur les actions
comptables elles-mêmes (écritures, journaux...) : ce rôle n'est pas un
rôle de travail au quotidien, c'est le rôle qui permet de mettre en place
les rôles de travail (en affectant des utilisateurs aux rôles métier déjà
définis par l'administrateur de plateforme — la création de nouveaux
rôles reste réservée à ce dernier, voir droits/router.py).
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a2f6c9e1b438'
down_revision: Union[str, Sequence[str], None] = 'd4e8b1a7c3f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CODE_ROLE = "administrateur_entreprise"

CODES_PERMISSIONS_ROLE = [
    "droits.administrer", "droits.consulter",
    "tiers.creer", "tiers.consulter", "tiers.modifier", "tiers.archiver",
    "document.consulter", "document.creer", "document.modifier",
    "portail_client.consulter", "portail_client.traiter",
    "dashboard.consulter",
    "notification.consulter", "notification.administrer",
    "journal_activite.consulter",
]


def upgrade() -> None:
    connexion = op.get_bind()

    roles = sa.table(
        "roles",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String),
        sa.column("libelle", sa.String),
        sa.column("est_role_plateforme", sa.Boolean),
    )
    insertion_role = postgresql.insert(roles).values(
        [
            {
                "id": uuid.uuid4(),
                "code": CODE_ROLE,
                "libelle": "Administrateur d'entreprise",
                "est_role_plateforme": False,
            }
        ]
    )
    insertion_role = insertion_role.on_conflict_do_update(
        index_elements=["code"], set_={"libelle": insertion_role.excluded.libelle}
    )
    connexion.execute(insertion_role)

    # L'id réellement en base peut différer de celui généré ci-dessus si la
    # ligne existait déjà (`ON CONFLICT DO UPDATE` ne renvoie pas l'id
    # existant via cette forme d'insert) — on le relit explicitement.
    role_id_reel = connexion.execute(
        sa.text("SELECT id FROM roles WHERE code = :code"), {"code": CODE_ROLE}
    ).scalar_one()

    permissions_existantes = connexion.execute(
        sa.text("SELECT id, code FROM permissions WHERE code IN :codes").bindparams(
            sa.bindparam("codes", expanding=True)
        ),
        {"codes": tuple(CODES_PERMISSIONS_ROLE)},
    ).all()
    codes_trouves = {ligne.code for ligne in permissions_existantes}
    codes_manquants = set(CODES_PERMISSIONS_ROLE) - codes_trouves
    if codes_manquants:
        raise RuntimeError(
            f"Permissions introuvables pour le rôle '{CODE_ROLE}' : {sorted(codes_manquants)}. "
            "Cette migration suppose que le catalogue de permissions (9a3c7e5b4d21 et suivantes) "
            "a déjà été appliqué."
        )

    roles_permissions = sa.table(
        "roles_permissions",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("role_id", postgresql.UUID(as_uuid=True)),
        sa.column("permission_id", postgresql.UUID(as_uuid=True)),
    )
    # Idempotent : on repart d'un jeu de permissions propre pour ce rôle à
    # chaque passage de la migration (utile si elle est rejouée après un
    # ajustement manuel), plutôt que d'accumuler des doublons.
    connexion.execute(
        sa.text("DELETE FROM roles_permissions WHERE role_id = :role_id"), {"role_id": role_id_reel}
    )
    connexion.execute(
        postgresql.insert(roles_permissions).values(
            [
                {"id": uuid.uuid4(), "role_id": role_id_reel, "permission_id": ligne.id}
                for ligne in permissions_existantes
            ]
        )
    )


def downgrade() -> None:
    connexion = op.get_bind()
    connexion.execute(
        sa.text(
            "DELETE FROM roles_permissions WHERE role_id = (SELECT id FROM roles WHERE code = :code)"
        ),
        {"code": CODE_ROLE},
    )
    # Si des affectations référencent encore ce rôle, la FK `RESTRICT` sur
    # `affectations.role_id` empêchera cette suppression — comportement
    # voulu, comme pour le downgrade du catalogue de permissions.
    connexion.execute(sa.text("DELETE FROM roles WHERE code = :code"), {"code": CODE_ROLE})