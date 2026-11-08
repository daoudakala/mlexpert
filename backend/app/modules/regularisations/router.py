"""Routes HTTP du module regularisations.

Toutes les routes sont entreprise-scopées
(`/regularisations/entreprises/{entreprise_id}/...`), protégées par les
permissions `regularisation.*` (`exiger_permission`), sur le modèle de
`provisions/router.py`.
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import ContexteEntreprise, exiger_permission
from app.core.database import get_db
from app.modules.regularisations.schemas import RegularisationCreation, RegularisationLecture
from app.modules.regularisations.service import RegularisationCreation as RegularisationCreationDonnees
from app.modules.regularisations.service import ServiceRegularisations

router = APIRouter(prefix="/regularisations", tags=["Régularisations"])


@router.post(
    "/entreprises/{entreprise_id}/regularisations",
    response_model=RegularisationLecture,
    status_code=status.HTTP_201_CREATED,
)
def creer_regularisation(
    entreprise_id: uuid.UUID,
    donnees: RegularisationCreation,
    contexte: ContexteEntreprise = Depends(exiger_permission("regularisation.creer")),
    db: Session = Depends(get_db),
) -> RegularisationLecture:
    service = ServiceRegularisations(db, contexte.entreprise_id)
    regularisation = service.creer_regularisation(
        RegularisationCreationDonnees(
            libelle=donnees.libelle,
            type_regularisation=donnees.type_regularisation,
            exercice_id=donnees.exercice_id,
            compte_origine_id=donnees.compte_origine_id,
            compte_regularisation_id=donnees.compte_regularisation_id,
            journal_id=donnees.journal_id,
            date_regularisation=donnees.date_regularisation,
            montant=donnees.montant,
        ),
        auteur_id=contexte.utilisateur_id,
    )
    db.commit()
    return RegularisationLecture.model_validate(regularisation)


@router.get(
    "/entreprises/{entreprise_id}/regularisations",
    response_model=list[RegularisationLecture],
)
def lister_regularisations(
    entreprise_id: uuid.UUID,
    type_regularisation: str | None = None,
    exercice_id: uuid.UUID | None = None,
    contexte: ContexteEntreprise = Depends(exiger_permission("regularisation.consulter")),
    db: Session = Depends(get_db),
) -> list[RegularisationLecture]:
    service = ServiceRegularisations(db, contexte.entreprise_id)
    return [
        RegularisationLecture.model_validate(r)
        for r in service.lister_regularisations(type_regularisation=type_regularisation, exercice_id=exercice_id)
    ]


@router.get(
    "/entreprises/{entreprise_id}/regularisations/{regularisation_id}",
    response_model=RegularisationLecture,
)
def lire_regularisation(
    entreprise_id: uuid.UUID,
    regularisation_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("regularisation.consulter")),
    db: Session = Depends(get_db),
) -> RegularisationLecture:
    service = ServiceRegularisations(db, contexte.entreprise_id)
    return RegularisationLecture.model_validate(service.obtenir_regularisation(regularisation_id))