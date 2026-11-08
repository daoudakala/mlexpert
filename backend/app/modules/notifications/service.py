"""Règles métier du module notifications.

Infrastructure seule (voir models.py) : ce service ne décide jamais QUAND
créer une notification — c'est aux futurs producteurs (Étapes 4 et 5) de
choisir le bon moment et le bon destinataire, en appelant `creer(...)`. Il
décide seulement SI elle doit effectivement être créée (préférence
utilisateur) et comment la lire/l'acquitter ensuite.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.exceptions import RessourceIntrouvable
from app.modules.notifications.models import (
    NiveauCriticite,
    Notification,
    PreferenceNotification,
    TypeNotification,
)
from app.modules.notifications.repository import (
    RepositoryNotifications,
    RepositoryPreferencesNotifications,
)

_ORDRE_CRITICITE = {
    NiveauCriticite.INFO.value: 0,
    NiveauCriticite.AVERTISSEMENT.value: 1,
    NiveauCriticite.CRITIQUE.value: 2,
}

# Jamais filtrée par préférence utilisateur : une alerte de sécurité doit
# toujours atteindre son destinataire (cahier, section 24) — un
# utilisateur ne peut pas se couper lui-même de ce type d'alerte.
_TYPES_NON_DESACTIVABLES = {TypeNotification.ALERTE_SECURITE.value}


class ServiceNotifications:
    def __init__(self, db: Session, entreprise_id: uuid.UUID) -> None:
        self.db = db
        self.entreprise_id = entreprise_id
        self.notifications = RepositoryNotifications(db, entreprise_id)
        self.preferences = RepositoryPreferencesNotifications(db)

    def creer(
        self,
        *,
        destinataire_id: uuid.UUID,
        type_notification: str,
        niveau_criticite: str,
        titre: str,
        message: str,
        type_objet: str | None = None,
        objet_id: uuid.UUID | None = None,
    ) -> Notification | None:
        """Crée la notification, sauf si l'utilisateur a désactivé ce
        type (ou relevé son niveau minimum au-dessus de
        `niveau_criticite`) — auquel cas retourne `None` plutôt que de
        créer une ligne que personne ne verra. Absence de préférence
        enregistrée = comportement par défaut (actif, tous niveaux)."""
        if type_notification not in _TYPES_NON_DESACTIVABLES:
            preference = self.preferences.obtenir_pour_type(destinataire_id, type_notification)
            if preference is not None:
                if not preference.active:
                    return None
                if _ORDRE_CRITICITE.get(niveau_criticite, 0) < _ORDRE_CRITICITE.get(
                    preference.niveau_minimum, 0
                ):
                    return None

        notification = Notification(
            destinataire_id=destinataire_id,
            type_notification=type_notification,
            niveau_criticite=niveau_criticite,
            titre=titre,
            message=message,
            type_objet=type_objet,
            objet_id=objet_id,
        )
        return self.notifications.ajouter(notification)

    def lister(self, utilisateur_id: uuid.UUID, *, non_lues_seulement: bool = False) -> list[Notification]:
        return self.notifications.lister_pour_utilisateur(
            utilisateur_id, non_lues_seulement=non_lues_seulement
        )

    def compter_non_lues(self, utilisateur_id: uuid.UUID) -> int:
        return self.notifications.compter_non_lues(utilisateur_id)

    def marquer_lue(self, notification_id: uuid.UUID, utilisateur_id: uuid.UUID) -> Notification:
        notification = self.notifications.obtenir(notification_id)
        if notification is None or notification.destinataire_id != utilisateur_id:
            raise RessourceIntrouvable("Notification introuvable.")
        if not notification.lu:
            notification.lu = True
            notification.lu_le = datetime.now(UTC)
        return notification

    def marquer_toutes_lues(self, utilisateur_id: uuid.UUID) -> None:
        self.notifications.marquer_toutes_lues(utilisateur_id)

    def obtenir_preferences(self, utilisateur_id: uuid.UUID) -> list[PreferenceNotification]:
        return self.preferences.lister_pour_utilisateur(utilisateur_id)

    def definir_preference(
        self,
        utilisateur_id: uuid.UUID,
        type_notification: str,
        *,
        active: bool,
        niveau_minimum: str,
    ) -> PreferenceNotification:
        preference = self.preferences.obtenir_pour_type(utilisateur_id, type_notification)
        if preference is None:
            preference = PreferenceNotification(
                utilisateur_id=utilisateur_id,
                type_notification=type_notification,
                active=active,
                niveau_minimum=niveau_minimum,
            )
            return self.preferences.ajouter(preference)
        preference.active = active
        preference.niveau_minimum = niveau_minimum
        return preference