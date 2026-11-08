"""Environnement Alembic pour MLexpert.

Deux différences avec le fichier généré par `alembic init` :

1. L'URL de connexion vient de `Settings.database_url` (donc du `.env` ou
   des variables d'environnement), pas de la ligne `sqlalchemy.url` codée
   en dur dans `alembic.ini`. Une seule source de vérité pour l'URL,
   partagée avec l'application elle-même.
2. `target_metadata` pointe vers `app.shared.base.Base.metadata`, après
   avoir importé tous les modules `models.py` de l'application : c'est ce
   qui permet à `alembic revision --autogenerate` de voir l'ensemble des
   tables. Un modèle qui n'est pas importé ici est invisible pour
   l'autogénération, même s'il hérite bien de `Base`.

L'ordre des imports ci-dessous ne détermine PAS l'ordre des tables dans la
migration générée : Alembic trie les `CREATE TABLE` selon les clés
étrangères automatiquement. L'ordre choisi ici suit seulement les
dépendances explicites entre modules, pour rester lisible.
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# Permet `import app...` quel que soit le répertoire depuis lequel Alembic
# est invoqué (le dossier `backend/` est le parent de `alembic/`).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings  # noqa: E402
from app.shared.base import Base  # noqa: E402

# Import de tous les modèles, dans l'ordre de dépendance du socle : sans
# entreprise ni exercice ni utilisateur, `droits` ne peut pas être résolu
# (Affectation référence les trois) ; `journal_activite` et `auth`
# viennent en dernier, ils ne sont référencés par personne.
from app.modules.utilisateurs import models as _utilisateurs_models  # noqa: E402,F401
from app.modules.entreprises import models as _entreprises_models  # noqa: E402,F401
from app.modules.exercices import models as _exercices_models  # noqa: E402,F401
from app.modules.droits import models as _droits_models  # noqa: E402,F401
from app.modules.journal_activite import models as _journal_activite_models  # noqa: E402,F401
from app.modules.auth import models as _auth_models  # noqa: E402,F401
from app.modules.comptabilite import models as _comptabilite_models  # noqa: E402,F401
from app.modules.tiers import models as _tiers_models  # noqa: E402,F401
from app.modules.tresorerie import models as _tresorerie_models  # noqa: E402,F401
from app.modules.immobilisations import models as _immobilisations_models  # noqa: E402,F401
from app.modules.documents import models as _documents_models  # noqa: E402,F401
from app.modules.portail_client import models as _portail_client_models  # noqa: E402,F401
from app.modules.paie import models as _paie_models  # noqa: E402,F401
from app.modules.stocks import models as _stocks_models  # noqa: E402,F401

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# L'URL de connexion vient de l'application, pas du fichier .ini.
config.set_main_option("sqlalchemy.url", get_settings().database_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
