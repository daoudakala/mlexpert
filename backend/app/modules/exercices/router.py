"""Routes HTTP du module exercices.

Convention de permission : `exercice.<action>` / `periode.<action>`, avec
`valider` pour la clôture et `annuler` pour la réouverture — les deux
actions du cahier (section 6) les plus proches de ce que ces opérations
représentent.
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import ContexteEntreprise, exiger_permission
from app.core.database import get_db
from app.modules.exercices.schemas import (
    ExerciceCreation,
    ExerciceLecture,
    PeriodeCreation,
    PeriodeLecture,
)
from app.modules.exercices.service import ServiceExercices

router = APIRouter(prefix="/entreprises/{entreprise_id}/exercices", tags=["Exercices"])


# --- Exercices ----------------------------------------------------------


@router.post("", response_model=ExerciceLecture, status_code=status.HTTP_201_CREATED)
def creer_exercice(
    donnees: ExerciceCreation,
    contexte: ContexteEntreprise = Depends(exiger_permission("exercice.creer")),
    db: Session = Depends(get_db),
) -> ExerciceLecture:
    service = ServiceExercices(db, contexte.entreprise_id)
    exercice = service.creer_exercice(
        auteur_id=contexte.utilisateur_id,
        date_debut=donnees.date_debut,
        date_fin=donnees.date_fin,
        exercice_precedent_id=donnees.exercice_precedent_id,
    )
    db.commit()
    return ExerciceLecture.model_validate(exercice)


@router.get("", response_model=list[ExerciceLecture])
def lister_exercices(
    contexte: ContexteEntreprise = Depends(exiger_permission("exercice.consulter")),
    db: Session = Depends(get_db),
) -> list[ExerciceLecture]:
    service = ServiceExercices(db, contexte.entreprise_id)
    return [ExerciceLecture.model_validate(e) for e in service.lister_exercices()]


@router.get("/{exercice_id}", response_model=ExerciceLecture)
def lire_exercice(
    exercice_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("exercice.consulter")),
    db: Session = Depends(get_db),
) -> ExerciceLecture:
    service = ServiceExercices(db, contexte.entreprise_id)
    return ExerciceLecture.model_validate(service.obtenir_exercice(exercice_id))


@router.post("/{exercice_id}/cloturer", status_code=status.HTTP_204_NO_CONTENT)
def cloturer_exercice(
    exercice_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("exercice.valider")),
    db: Session = Depends(get_db),
) -> None:
    service = ServiceExercices(db, contexte.entreprise_id)
    service.cloturer_exercice(exercice_id, auteur_id=contexte.utilisateur_id)
    db.commit()


@router.post("/{exercice_id}/reouvrir", status_code=status.HTTP_204_NO_CONTENT)
def reouvrir_exercice(
    exercice_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("exercice.annuler")),
    db: Session = Depends(get_db),
) -> None:
    service = ServiceExercices(db, contexte.entreprise_id)
    service.reouvrir_exercice(exercice_id, auteur_id=contexte.utilisateur_id)
    db.commit()


# --- Périodes -------------------------------------------------------------


@router.post(
    "/{exercice_id}/periodes",
    response_model=PeriodeLecture,
    status_code=status.HTTP_201_CREATED,
)
def creer_periode(
    exercice_id: uuid.UUID,
    donnees: PeriodeCreation,
    contexte: ContexteEntreprise = Depends(exiger_permission("periode.creer")),
    db: Session = Depends(get_db),
) -> PeriodeLecture:
    service = ServiceExercices(db, contexte.entreprise_id)
    periode = service.creer_periode(
        auteur_id=contexte.utilisateur_id,
        exercice_id=exercice_id,
        date_debut=donnees.date_debut,
        date_fin=donnees.date_fin,
        libelle=donnees.libelle,
    )
    db.commit()
    return PeriodeLecture.model_validate(periode)


@router.get("/{exercice_id}/periodes", response_model=list[PeriodeLecture])
def lister_periodes(
    exercice_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("periode.consulter")),
    db: Session = Depends(get_db),
) -> list[PeriodeLecture]:
    service = ServiceExercices(db, contexte.entreprise_id)
    return [PeriodeLecture.model_validate(p) for p in service.lister_periodes(exercice_id)]


@router.post(
    "/{exercice_id}/periodes/{periode_id}/cloturer",
    status_code=status.HTTP_204_NO_CONTENT,
)
def cloturer_periode(
    exercice_id: uuid.UUID,
    periode_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("periode.valider")),
    db: Session = Depends(get_db),
) -> None:
    service = ServiceExercices(db, contexte.entreprise_id)
    service.cloturer_periode(periode_id, auteur_id=contexte.utilisateur_id)
    db.commit()


@router.post(
    "/{exercice_id}/periodes/{periode_id}/reouvrir",
    status_code=status.HTTP_204_NO_CONTENT,
)
def reouvrir_periode(
    exercice_id: uuid.UUID,
    periode_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("periode.annuler")),
    db: Session = Depends(get_db),
) -> None:
    service = ServiceExercices(db, contexte.entreprise_id)
    service.reouvrir_periode(periode_id, auteur_id=contexte.utilisateur_id)
    db.commit()