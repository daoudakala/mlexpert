"""catalogue des permissions

Revision ID: 9a3c7e5b4d21
Revises: 7468c1c608fb
Create Date: 2026-10-07 12:10:00.000000

Insère en base le catalogue complet des permissions (code + libellé),
jusqu'ici jamais peuplé : chaque module créait ses propres lignes
`Permission` à la volée (scripts de seed, ou via `ServiceDroits.creer_role`
qui exige que le code existe déjà). Conséquence concrète : la page
Rôles & permissions du frontend (GET /droits/permissions) affichait une
liste vide sur toute base qui n'avait pas été seedée module par module.

Les codes repris ici sont tous ceux effectivement vérifiés par
`exiger_permission(...)` dans les routers (recherche exhaustive sur
`app/`) — la seule source de vérité fiable pour ce qui est réellement
appliqué.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a3c7e5b4d21'
down_revision: Union[str, Sequence[str], None] = '7468c1c608fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


LIBELLES_PAR_ACTION = {
    "consulter": "Consulter",
    "creer": "Créer",
    "modifier": "Modifier",
    "valider": "Valider",
    "annuler": "Annuler",
    "exporter": "Exporter",
    "supprimer": "Supprimer",
    "archiver": "Archiver",
    "administrer": "Administrer",
    "demander": "Demander",
    "traiter": "Traiter",
    "ceder": "Céder",
}

LIBELLES_PAR_MODULE = {
    "article": "Articles",
    "bulletin": "Bulletins de paie",
    "compte": "Plan comptable",
    "compte_bancaire": "Comptes bancaires",
    "dashboard": "Tableaux de bord",
    "document": "Documents",
    "droits": "Droits",
    "ecriture": "Écritures",
    "employe": "Employés",
    "exercice": "Exercices",
    "immobilisation": "Immobilisations",
    "journal": "Journaux",
    "journal_activite": "Journal d'activité",
    "mouvement_stock": "Mouvements de stock",
    "periode": "Périodes",
    "portail_client": "Portail client",
    "rapprochement": "Rapprochements bancaires",
    "releve": "Relevés bancaires",
    "rubrique_paie": "Rubriques de paie",
    "tiers": "Tiers",
}

# Codes effectivement vérifiés par `exiger_permission("<code>")` dans les
# routers (voir docstring ci-dessus).
CODES_PERMISSIONS = [
    "article.archiver", "article.consulter", "article.creer", "article.modifier",
    "bulletin.consulter", "bulletin.creer", "bulletin.modifier", "bulletin.valider",
    "compte.archiver", "compte.consulter", "compte.creer",
    "compte_bancaire.archiver", "compte_bancaire.consulter", "compte_bancaire.creer",
    "dashboard.consulter",
    "document.consulter", "document.creer", "document.modifier", "document.supprimer",
    "droits.administrer", "droits.consulter",
    "ecriture.annuler", "ecriture.consulter", "ecriture.creer", "ecriture.modifier",
    "ecriture.supprimer", "ecriture.valider",
    "employe.archiver", "employe.consulter", "employe.creer", "employe.modifier",
    "exercice.annuler", "exercice.consulter", "exercice.creer", "exercice.valider",
    "immobilisation.ceder", "immobilisation.consulter", "immobilisation.creer",
    "immobilisation.modifier", "immobilisation.valider",
    "journal.archiver", "journal.consulter", "journal.creer",
    "journal_activite.consulter",
    "mouvement_stock.consulter", "mouvement_stock.creer",
    "periode.annuler", "periode.consulter", "periode.creer", "periode.valider",
    "portail_client.consulter", "portail_client.demander", "portail_client.traiter",
    "rapprochement.annuler", "rapprochement.creer",
    "releve.consulter", "releve.creer", "releve.modifier", "releve.supprimer",
    "rubrique_paie.archiver", "rubrique_paie.consulter", "rubrique_paie.creer",
    "rubrique_paie.modifier",
    "tiers.annuler", "tiers.archiver", "tiers.consulter", "tiers.creer", "tiers.modifier",
]


def _libelle(code: str) -> str:
    module, action = code.split(".", 1)
    return f"{LIBELLES_PAR_MODULE.get(module, module)} — {LIBELLES_PAR_ACTION.get(action, action)}"


def upgrade() -> None:
    """Insère les permissions manquantes et corrige le libellé de celles
    qui existaient déjà avec un libellé provisoire (certains scripts de
    seed créaient la ligne à la volée avec `libelle=code` faute de mieux :
    `ON CONFLICT DO UPDATE` plutôt que `DO NOTHING` pour rattraper ces
    lignes-là aussi, pas seulement insérer celles qui manquent)."""
    permissions = sa.table(
        "permissions",
        sa.column("id", sa.dialects.postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String),
        sa.column("libelle", sa.String),
    )
    connexion = op.get_bind()
    import uuid

    lignes = [
        {"id": uuid.uuid4(), "code": code, "libelle": _libelle(code)}
        for code in CODES_PERMISSIONS
    ]
    insertion = sa.dialects.postgresql.insert(permissions).values(lignes)
    insertion = insertion.on_conflict_do_update(
        index_elements=["code"], set_={"libelle": insertion.excluded.libelle}
    )
    connexion.execute(insertion)


def downgrade() -> None:
    """Ne retire que les permissions de ce catalogue, et seulement si elles
    ne sont plus référencées par un rôle (sinon la contrainte de clé
    étrangère sur roles_permissions bloquera la suppression, ce qui est le
    comportement voulu)."""
    connexion = op.get_bind()
    codes = tuple(CODES_PERMISSIONS)
    connexion.execute(
        sa.text("DELETE FROM permissions WHERE code IN :codes").bindparams(
            sa.bindparam("codes", expanding=True)
        ),
        {"codes": codes},
    )