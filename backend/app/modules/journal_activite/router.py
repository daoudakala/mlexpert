"""Routes HTTP du module journal_activite.

Deux points d'entrée en lecture seule (aucune écriture : le journal ne se
modifie jamais, cahier section 23) :

- `GET /journal-activite` : vue transversale, réservée à l'administrateur
  plateforme — toutes entreprises confondues.
- `GET /entreprises/{entreprise_id}/journal-activite` : vue d'une seule
  entreprise, ouverte à qui a la permission `journal_activite.consulter`
  sur cette entreprise. `entreprise_id` vient du contexte résolu, jamais
  d'un paramètre de requête : impossible de consulter le journal d'une
  autre entreprise en le passant en query string.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import ContexteEntreprise, exiger_administrateur_plateforme, exiger_permission
from app.core.database import get_db
from app.modules.journal_activite.schemas import JournalActiviteLecture
from app.modules.journal_activite.service import ServiceJournalActivite

router = APIRouter(tags=["Journal d'activité"])


# --- Vue transversale (Administrateur plateforme) ----------------------------


@router.get(
    "/journal-activite",
    response_model=list[JournalActiviteLecture],
    dependencies=[Depends(exiger_administrateur_plateforme)],
)
def rechercher_journal_plateforme(
    entreprise_id: uuid.UUID | None = None,
    utilisateur_id: uuid.UUID | None = None,
    module: str | None = None,
    type_action: str | None = None,
    type_objet: str | None = None,
    objet_id: uuid.UUID | None = None,
    depuis: datetime | None = None,
    jusqu_a: datetime | None = None,
    limite: int = Query(default=100, le=500),
    decalage: int = 0,
    db: Session = Depends(get_db),
) -> list[JournalActiviteLecture]:
    service = ServiceJournalActivite(db)
    entrees = service.rechercher(
        entreprise_id=entreprise_id,
        utilisateur_id=utilisateur_id,
        module=module,
        type_action=type_action,
        type_objet=type_objet,
        objet_id=objet_id,
        depuis=depuis,
        jusqu_a=jusqu_a,
        limite=limite,
        decalage=decalage,
    )
    return [JournalActiviteLecture.model_validate(e) for e in entrees]


# --- Vue d'une entreprise ----------------------------------------------------


@router.get(
    "/entreprises/{entreprise_id}/journal-activite",
    response_model=list[JournalActiviteLecture],
)
def rechercher_journal_entreprise(
    utilisateur_id: uuid.UUID | None = None,
    module: str | None = None,
    type_action: str | None = None,
    type_objet: str | None = None,
    objet_id: uuid.UUID | None = None,
    depuis: datetime | None = None,
    jusqu_a: datetime | None = None,
    limite: int = Query(default=100, le=500),
    decalage: int = 0,
    contexte: ContexteEntreprise = Depends(exiger_permission("journal_activite.consulter")),
    db: Session = Depends(get_db),
) -> list[JournalActiviteLecture]:
    service = ServiceJournalActivite(db)
    entrees = service.rechercher(
        entreprise_id=contexte.entreprise_id,
        utilisateur_id=utilisateur_id,
        module=module,
        type_action=type_action,
        type_objet=type_objet,
        objet_id=objet_id,
        depuis=depuis,
        jusqu_a=jusqu_a,
        limite=limite,
        decalage=decalage,
    )
    return [JournalActiviteLecture.model_validate(e) for e in entrees]


@router.get(
    "/entreprises/{entreprise_id}/journal-activite/objets/{type_objet}/{objet_id}",
    response_model=list[JournalActiviteLecture],
)
def historique_objet(
    type_objet: str,
    objet_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("journal_activite.consulter")),
    db: Session = Depends(get_db),
) -> list[JournalActiviteLecture]:
    """L'historique complet d'un objet précis (ex. un exercice), toutes
    entrées confondues. `entreprise_id` du chemin n'est utilisé que pour la
    vérification de permission ; le filtrage se fait par `type_objet` +
    `objet_id`, qui identifient l'objet de façon unique."""
    service = ServiceJournalActivite(db)
    entrees = service.lister_pour_objet(type_objet, objet_id)
    return [JournalActiviteLecture.model_validate(e) for e in entrees]