"""Modèle du module journal_activite (cahier des charges, section 23).

Une seule table, en ajout seul — aucune ligne n'est jamais modifiée ni
supprimée. Pour cette raison, ce modèle n'utilise PAS `HorodatageMixin` :
sa colonne `modifie_le` (avec `onupdate`) n'aurait pas de sens sur une
ligne qui ne change jamais. À la place, une unique colonne `survenu_le`.

`utilisateur_id` et `entreprise_id` sont nullables, contrairement à la
convention habituelle (`EntrepriseMixin` les impose obligatoires) : une
création de rôle ou d'utilisateur n'a pas d'entreprise ; une tentative de
connexion échouée peut n'avoir aucun utilisateur identifié. C'est pourquoi
ce module ne réutilise pas `EntrepriseMixin` et définit ses colonnes à la
main.

`type_action` a une liste indicative de valeurs (`TypeAction`) mais AUCUNE
contrainte `CHECK` en base, à la différence de `statut` sur `Entreprise`
ou `Exercice` : les statuts sont un petit ensemble fermé qui ne bouge
presque jamais, alors que les types d'action s'enrichiront à chaque
nouveau module (comptabilité, immobilisations...). Une contrainte stricte
forcerait une migration à chaque ajout.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base import Base
from app.shared.mixins import IdentifiantMixin


class TypeAction(StrEnum):
    """Valeurs indicatives, alignées sur les 9 actions du cahier (section 6)
    plus les événements de connexion (section 23). D'autres valeurs pourront
    être utilisées par de futurs modules sans changer ce fichier."""

    CONSULTER = "consulter"
    CREER = "creer"
    MODIFIER = "modifier"
    VALIDER = "valider"
    ANNULER = "annuler"
    EXPORTER = "exporter"
    SUPPRIMER = "supprimer"
    ARCHIVER = "archiver"
    ADMINISTRER = "administrer"
    CONNEXION = "connexion"
    CONNEXION_ECHOUEE = "connexion_echouee"
    DECONNEXION = "deconnexion"


class JournalActivite(IdentifiantMixin, Base):
    __tablename__ = "journal_activite"

    survenu_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # Qui : nul pour un événement système ou une connexion non résolue
    # (email inconnu). `SET NULL` plutôt que `CASCADE` : la ligne de
    # journal doit survivre même si le compte est un jour supprimé.
    utilisateur_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("utilisateurs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Quelle entreprise : nul pour une action de portée plateforme
    # (création d'un rôle, d'un utilisateur...).
    entreprise_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entreprises.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Quoi
    module: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    type_action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    type_objet: Mapped[str | None] = mapped_column(String(100), nullable=True)
    objet_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # État avant/après (cahier, section 5 : "les automatisations doivent
    # conserver une trace de leur origine"). JSONB : interrogeable côté
    # PostgreSQL sans schéma rigide, adapté à des objets métier très divers.
    valeurs_avant: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    valeurs_apres: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    adresse_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)