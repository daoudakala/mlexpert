"""Classe de base des modèles SQLAlchemy.

La convention de nommage ci-dessous force Alembic à générer des noms de
contraintes stables et prévisibles (index, clés étrangères, unicité,
vérifications). Sans elle, les noms sont générés automatiquement par la base
de données et changent d'une exécution à l'autre, ce qui rend les migrations
imprévisibles à modifier ou à annuler.

Tous les modèles de tous les modules héritent de `Base`, jamais d'une base
propre au module.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

CONVENTION_NOMMAGE = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=CONVENTION_NOMMAGE)