"""Schémas Pydantic du module notifications."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modules.notifications.models import NiveauCriticite


class NotificationLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type_notification: str
    niveau_criticite: str
    canal: str
    titre: str
    message: str
    type_objet: str | None
    objet_id: uuid.UUID | None
    lu: bool
    lu_le: datetime | None
    cree_le: datetime


class CompteurNotificationsLecture(BaseModel):
    non_lues: int


class PreferenceNotificationLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    type_notification: str
    active: bool
    niveau_minimum: str


class PreferenceNotificationEcriture(BaseModel):
    active: bool = True
    niveau_minimum: str = NiveauCriticite.INFO.value