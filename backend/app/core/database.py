"""Connexion à la base de données (SQLAlchemy 2, mode synchrone).

Règle de transaction : ce module ne valide jamais (pas de commit automatique).
C'est le service qui appelle `db.commit()` à la fin d'un cas d'usage, ce qui
garantit que la modification métier et son entrée dans le journal d'activité
sont enregistrées ensemble, ou pas du tout.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_settings = get_settings()

engine = create_engine(
    _settings.database_url,
    pool_size=_settings.db_pool_size,
    max_overflow=_settings.db_max_overflow,
    echo=_settings.db_echo,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Fournit une session par requête HTTP.

    En cas d'erreur non gérée, la transaction en cours est annulée.
    La session est toujours fermée à la fin de la requête.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()