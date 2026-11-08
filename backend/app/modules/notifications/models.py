"""Modèle du module notifications (cahier des charges, sections 20 et 24).

Infrastructure seule : ce module ne génère aucune notification de
lui-même. Les futurs producteurs (messagerie portail client — Étape 4,
alertes de pilotage : échéances, impayés, clôtures... — Étape 5)
appelleront `ServiceNotifications.creer(...)` (voir service.py).

`entreprise_id` est ici obligatoire (via `EntrepriseMixin`), par
cohérence avec `app/api/deps.py` : `exiger_permission(...)` ne sait
vérifier qu'un contexte entreprise précis (`get_contexte_entreprise`
exige un `entreprise_id` dans l'URL) — il n'existe aucune route
"plateforme" sans entreprise pour une boîte de réception transverse.
Une alerte de sécurité réellement plateforme (hors entreprise) n'est
donc pas modélisable pour l'instant — à revoir si l'Étape 5 en a
concrètement besoin.

`type_notification` reprend le choix de `journal_activite.TypeAction` :
une liste indicative (`TypeNotification`) SANS contrainte CHECK, pour ne
pas imposer une migration à chaque nouvelle catégorie d'alerte.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base import Base
from app.shared.mixins import EntrepriseMixin, HorodatageMixin, IdentifiantMixin


class TypeNotification(StrEnum):
    """Valeurs indicatives (cahier, section 24 "Alertes et échéances" +
    section 20 "Messagerie... Notifications") ; d'autres valeurs pourront
    être ajoutées par de futurs modules sans migration (voir la note de
    tête de fichier)."""

    ECHEANCE_CLIENT = "echeance_client"
    ECHEANCE_FOURNISSEUR = "echeance_fournisseur"
    DOCUMENT_MANQUANT = "document_manquant"
    DEMANDE_PIECE_NON_TRAITEE = "demande_piece_non_traitee"
    VALIDATION_EN_ATTENTE = "validation_en_attente"
    CLOTURE_COMPTABLE = "cloture_comptable"
    ALERTE_SECURITE = "alerte_securite"
    MESSAGE_PORTAIL = "message_portail"


class NiveauCriticite(StrEnum):
    INFO = "info"
    AVERTISSEMENT = "avertissement"
    CRITIQUE = "critique"


class CanalNotification(StrEnum):
    """Un seul canal réellement implémenté pour l'instant : `IN_APP`. Les
    autres valeurs n'existent pas encore — aucune infra email/SMS dans le
    projet (cahier, section 25.4 "intégrations futures : messagerie").
    Le champ existe dès maintenant pour ne pas avoir à migrer la table
    plus tard, quand un canal réel sera ajouté."""

    IN_APP = "in_app"


class Notification(IdentifiantMixin, HorodatageMixin, EntrepriseMixin, Base):
    __tablename__ = "notifications"

    destinataire_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("utilisateurs.id", ondelete="CASCADE"), nullable=False, index=True
    )

    type_notification: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    niveau_criticite: Mapped[str] = mapped_column(
        String(20), nullable=False, default=NiveauCriticite.INFO.value
    )
    canal: Mapped[str] = mapped_column(String(20), nullable=False, default=CanalNotification.IN_APP.value)

    titre: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Lien générique vers l'objet concerné (une écriture, une demande de
    # document...), même convention que journal_activite.
    type_objet: Mapped[str | None] = mapped_column(String(100), nullable=True)
    objet_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)

    lu: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    lu_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PreferenceNotification(IdentifiantMixin, HorodatageMixin, Base):
    """Une ligne par (utilisateur, type_notification) — personnelle, PAS
    rattachée à une entreprise : une préférence de notification est un
    réglage de l'utilisateur lui-même, valable sur toutes les entreprises
    auxquelles il est affecté (pas d'`EntrepriseMixin` ici).

    Absence de ligne pour un (utilisateur, type) donné = comportement par
    défaut (actif, niveau minimum "info") — voir `service.py`."""

    __tablename__ = "preferences_notifications"
    __table_args__ = (
        UniqueConstraint("utilisateur_id", "type_notification", name="uq_preference_utilisateur_type"),
    )

    utilisateur_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("utilisateurs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type_notification: Mapped[str] = mapped_column(String(50), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    niveau_minimum: Mapped[str] = mapped_column(
        String(20), nullable=False, default=NiveauCriticite.INFO.value
    )