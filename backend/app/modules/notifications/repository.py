"""Accès aux données du module notifications.

Deux dépôts : `RepositoryNotifications` hérite de `RepositoryEntreprise`
(une notification appartient toujours à une entreprise précise, voir
models.py) ; `RepositoryPreferencesNotifications` hérite du `Repository`
simple (une préférence est personnelle à l'utilisateur, pas rattachée à
une entreprise).
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select

from app.modules.notifications.models import Notification, PreferenceNotification
from app.shared.repository import Repository, RepositoryEntreprise


class RepositoryNotifications(RepositoryEntreprise[Notification]):
    modele = Notification

    def lister_pour_utilisateur(
        self,
        utilisateur_id: uuid.UUID,
        *,
        non_lues_seulement: bool = False,
        limite: int = 100,
        decalage: int = 0,
    ) -> list[Notification]:
        requete = select(Notification).where(
            Notification.entreprise_id == self.entreprise_id,
            Notification.destinataire_id == utilisateur_id,
        )
        if non_lues_seulement:
            requete = requete.where(Notification.lu.is_(False))
        requete = requete.order_by(Notification.cree_le.desc()).limit(limite).offset(decalage)
        return list(self.db.scalars(requete).all())

    def compter_non_lues(self, utilisateur_id: uuid.UUID) -> int:
        requete = (
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.entreprise_id == self.entreprise_id,
                Notification.destinataire_id == utilisateur_id,
                Notification.lu.is_(False),
            )
        )
        return self.db.scalar(requete) or 0

    def marquer_toutes_lues(self, utilisateur_id: uuid.UUID) -> None:
        """Boucle ORM plutôt qu'un UPDATE en masse : le volume par
        utilisateur reste faible (notifications non lues), et ça laisse
        SQLAlchemy gérer `lu_le` de façon identique à `marquer_lue`
        (service.py) sans dupliquer la valeur de l'horodatage."""
        maintenant = datetime.now(UTC)
        requete = select(Notification).where(
            Notification.entreprise_id == self.entreprise_id,
            Notification.destinataire_id == utilisateur_id,
            Notification.lu.is_(False),
        )
        for notification in self.db.scalars(requete).all():
            notification.lu = True
            notification.lu_le = maintenant


class RepositoryPreferencesNotifications(Repository[PreferenceNotification]):
    modele = PreferenceNotification

    def obtenir_pour_type(
        self, utilisateur_id: uuid.UUID, type_notification: str
    ) -> PreferenceNotification | None:
        requete = select(PreferenceNotification).where(
            PreferenceNotification.utilisateur_id == utilisateur_id,
            PreferenceNotification.type_notification == type_notification,
        )
        return self.db.scalars(requete).first()

    def lister_pour_utilisateur(self, utilisateur_id: uuid.UUID) -> list[PreferenceNotification]:
        requete = select(PreferenceNotification).where(
            PreferenceNotification.utilisateur_id == utilisateur_id
        )
        return list(self.db.scalars(requete).all())