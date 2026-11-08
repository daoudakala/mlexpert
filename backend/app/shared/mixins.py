"""Mixins réutilisables par les modèles des modules.

Un mixin ajoute des colonnes communes à un modèle sans passer par
l'héritage de table (qui compliquerait les migrations). Chaque modèle
compose les mixins dont il a besoin, en plus de `Base`.
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class IdentifiantMixin:
    """Clé primaire UUID.

    Un UUID plutôt qu'un entier auto-incrémenté : les identifiants ne
    révèlent pas le volume de données d'une entreprise à une autre, et ils
    restent stables si les données doivent un jour être répliquées ou
    fusionnées entre environnements.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


class HorodatageMixin:
    """Dates de création et de modification, posées par la base elle-même.

    `server_default` / `onupdate=func.now()` garantit la valeur même pour
    une insertion faite hors de l'application (script de reprise, console).
    """

    cree_le: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
    modifie_le: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class EntrepriseMixin:
    """Rattachement obligatoire à une entreprise.

    Toute table métier (écritures, documents, tiers, immobilisations...)
    compose ce mixin. C'est la colonne que `RepositoryEntreprise`
    (repository.py) filtre systématiquement, ce qui réalise l'isolation
    des données par entreprise exigée par le cahier des charges.
    """

    entreprise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entreprises.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )