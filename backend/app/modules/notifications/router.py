"""Routes HTTP du module notifications.

Toutes scopées à l'entreprise courante
(`/notifications/entreprises/{entreprise_id}/...`, voir la note de tête
de `models.py` sur `exiger_permission`), permission unique
`notification.consulter` — lecture et gestion de SES PROPRES
notifications, pas d'administration ici : aucune route de création
publique, seule une autre partie du backend crée des notifications via
`ServiceNotifications.creer(...)` (voir Étapes 4 et 5, pas encore
construites).
"""

import uuid

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import ContexteEntreprise, exiger_permission
from app.core.database import get_db
from app.modules.notifications.schemas import (
    CompteurNotificationsLecture,
    NotificationLecture,
    PreferenceNotificationEcriture,
    PreferenceNotificationLecture,
)
from app.modules.notifications.service import ServiceNotifications

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get(
    "/entreprises/{entreprise_id}/mes-notifications",
    response_model=list[NotificationLecture],
)
def lister_mes_notifications(
    entreprise_id: uuid.UUID,
    non_lues_seulement: bool = False,
    contexte: ContexteEntreprise = Depends(exiger_permission("notification.consulter")),
    db: Session = Depends(get_db),
) -> list[NotificationLecture]:
    service = ServiceNotifications(db, contexte.entreprise_id)
    return [
        NotificationLecture.model_validate(n)
        for n in service.lister(contexte.utilisateur_id, non_lues_seulement=non_lues_seulement)
    ]


@router.get(
    "/entreprises/{entreprise_id}/mes-notifications/compteur",
    response_model=CompteurNotificationsLecture,
)
def compter_mes_notifications_non_lues(
    entreprise_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("notification.consulter")),
    db: Session = Depends(get_db),
) -> CompteurNotificationsLecture:
    service = ServiceNotifications(db, contexte.entreprise_id)
    return CompteurNotificationsLecture(non_lues=service.compter_non_lues(contexte.utilisateur_id))


@router.post(
    "/entreprises/{entreprise_id}/notifications/{notification_id}/marquer-lue",
    response_model=NotificationLecture,
)
def marquer_notification_lue(
    entreprise_id: uuid.UUID,
    notification_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("notification.consulter")),
    db: Session = Depends(get_db),
) -> NotificationLecture:
    service = ServiceNotifications(db, contexte.entreprise_id)
    notification = service.marquer_lue(notification_id, contexte.utilisateur_id)
    db.commit()
    return NotificationLecture.model_validate(notification)


@router.post(
    "/entreprises/{entreprise_id}/mes-notifications/marquer-toutes-lues",
    status_code=status.HTTP_204_NO_CONTENT,
)
def marquer_toutes_mes_notifications_lues(
    entreprise_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("notification.consulter")),
    db: Session = Depends(get_db),
) -> Response:
    service = ServiceNotifications(db, contexte.entreprise_id)
    service.marquer_toutes_lues(contexte.utilisateur_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/entreprises/{entreprise_id}/mes-preferences",
    response_model=list[PreferenceNotificationLecture],
)
def lister_mes_preferences(
    entreprise_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("notification.consulter")),
    db: Session = Depends(get_db),
) -> list[PreferenceNotificationLecture]:
    service = ServiceNotifications(db, contexte.entreprise_id)
    return [
        PreferenceNotificationLecture.model_validate(p)
        for p in service.obtenir_preferences(contexte.utilisateur_id)
    ]


@router.put(
    "/entreprises/{entreprise_id}/mes-preferences/{type_notification}",
    response_model=PreferenceNotificationLecture,
)
def definir_ma_preference(
    entreprise_id: uuid.UUID,
    type_notification: str,
    donnees: PreferenceNotificationEcriture,
    contexte: ContexteEntreprise = Depends(exiger_permission("notification.consulter")),
    db: Session = Depends(get_db),
) -> PreferenceNotificationLecture:
    service = ServiceNotifications(db, contexte.entreprise_id)
    preference = service.definir_preference(
        contexte.utilisateur_id,
        type_notification,
        active=donnees.active,
        niveau_minimum=donnees.niveau_minimum,
    )
    db.commit()
    return PreferenceNotificationLecture.model_validate(preference)