"""Schémas Pydantic du module journal_activite."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JournalActiviteLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    survenu_le: datetime
    utilisateur_id: uuid.UUID | None
    # Résolus par ServiceJournalActivite._enrichir (voir service.py) plutôt
    # que portés par la table elle-même : nuls pour un événement système ou
    # une connexion non résolue (voir models.py), ou si le compte a depuis
    # été supprimé.
    utilisateur_nom: str | None = None
    utilisateur_prenom: str | None = None
    utilisateur_email: str | None = None
    entreprise_id: uuid.UUID | None
    module: str
    type_action: str
    type_objet: str | None
    objet_id: uuid.UUID | None
    description: str | None
    valeurs_avant: dict | None
    valeurs_apres: dict | None
    adresse_ip: str | None
