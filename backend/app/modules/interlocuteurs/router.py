"""Routes HTTP du module interlocuteurs.

Toutes les routes sont entreprise-scopées
(`/interlocuteurs/entreprises/{entreprise_id}/...`), protégées par les
permissions `interlocuteur.*` (`exiger_permission`) — même gabarit que
`documents`.
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import ContexteEntreprise, exiger_permission
from app.core.database import get_db
from app.modules.interlocuteurs.schemas import (
    InterlocuteurCreation,
    InterlocuteurLecture,
    InterlocuteurMiseAJour,
)
from app.modules.interlocuteurs.service import InterlocuteurCreationDonnees, ServiceInterlocuteurs

router = APIRouter(prefix="/interlocuteurs", tags=["Interlocuteurs"])


@router.post(
    "/entreprises/{entreprise_id}/interlocuteurs",
    response_model=InterlocuteurLecture,
    status_code=status.HTTP_201_CREATED,
)
def creer_interlocuteur(
    entreprise_id: uuid.UUID,
    donnees: InterlocuteurCreation,
    contexte: ContexteEntreprise = Depends(exiger_permission("interlocuteur.creer")),
    db: Session = Depends(get_db),
) -> InterlocuteurLecture:
    service = ServiceInterlocuteurs(db, contexte.entreprise_id)
    interlocuteur = service.creer_interlocuteur(
        InterlocuteurCreationDonnees(
            nom=donnees.nom,
            role=donnees.role,
            fonction=donnees.fonction,
            email=donnees.email,
            telephone=donnees.telephone,
            pourcentage_detention=donnees.pourcentage_detention,
            notes=donnees.notes,
        ),
        auteur_id=contexte.utilisateur_id,
    )
    db.commit()
    return InterlocuteurLecture.model_validate(interlocuteur)


@router.get(
    "/entreprises/{entreprise_id}/interlocuteurs",
    response_model=list[InterlocuteurLecture],
)
def lister_interlocuteurs(
    entreprise_id: uuid.UUID,
    role: str | None = None,
    actifs_seulement: bool = True,
    contexte: ContexteEntreprise = Depends(exiger_permission("interlocuteur.consulter")),
    db: Session = Depends(get_db),
) -> list[InterlocuteurLecture]:
    service = ServiceInterlocuteurs(db, contexte.entreprise_id)
    interlocuteurs = service.lister_interlocuteurs(role=role, actifs_seulement=actifs_seulement)
    return [InterlocuteurLecture.model_validate(i) for i in interlocuteurs]


@router.get(
    "/entreprises/{entreprise_id}/interlocuteurs/{interlocuteur_id}",
    response_model=InterlocuteurLecture,
)
def lire_interlocuteur(
    entreprise_id: uuid.UUID,
    interlocuteur_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("interlocuteur.consulter")),
    db: Session = Depends(get_db),
) -> InterlocuteurLecture:
    service = ServiceInterlocuteurs(db, contexte.entreprise_id)
    return InterlocuteurLecture.model_validate(service.obtenir_interlocuteur(interlocuteur_id))


@router.patch(
    "/entreprises/{entreprise_id}/interlocuteurs/{interlocuteur_id}",
    response_model=InterlocuteurLecture,
)
def modifier_interlocuteur(
    entreprise_id: uuid.UUID,
    interlocuteur_id: uuid.UUID,
    donnees: InterlocuteurMiseAJour,
    contexte: ContexteEntreprise = Depends(exiger_permission("interlocuteur.modifier")),
    db: Session = Depends(get_db),
) -> InterlocuteurLecture:
    service = ServiceInterlocuteurs(db, contexte.entreprise_id)
    interlocuteur = service.modifier_interlocuteur(
        interlocuteur_id,
        auteur_id=contexte.utilisateur_id,
        nom=donnees.nom,
        role=donnees.role,
        fonction=donnees.fonction,
        email=donnees.email,
        telephone=donnees.telephone,
        pourcentage_detention=donnees.pourcentage_detention,
        notes=donnees.notes,
    )
    db.commit()
    return InterlocuteurLecture.model_validate(interlocuteur)


@router.post(
    "/entreprises/{entreprise_id}/interlocuteurs/{interlocuteur_id}/desactiver",
    response_model=InterlocuteurLecture,
)
def desactiver_interlocuteur(
    entreprise_id: uuid.UUID,
    interlocuteur_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("interlocuteur.modifier")),
    db: Session = Depends(get_db),
) -> InterlocuteurLecture:
    service = ServiceInterlocuteurs(db, contexte.entreprise_id)
    interlocuteur = service.desactiver_interlocuteur(interlocuteur_id, auteur_id=contexte.utilisateur_id)
    db.commit()
    return InterlocuteurLecture.model_validate(interlocuteur)


@router.post(
    "/entreprises/{entreprise_id}/interlocuteurs/{interlocuteur_id}/reactiver",
    response_model=InterlocuteurLecture,
)
def reactiver_interlocuteur(
    entreprise_id: uuid.UUID,
    interlocuteur_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("interlocuteur.modifier")),
    db: Session = Depends(get_db),
) -> InterlocuteurLecture:
    service = ServiceInterlocuteurs(db, contexte.entreprise_id)
    interlocuteur = service.reactiver_interlocuteur(interlocuteur_id, auteur_id=contexte.utilisateur_id)
    db.commit()
    return InterlocuteurLecture.model_validate(interlocuteur)
