"""Routes HTTP du module provisions.

Toutes les routes sont entreprise-scopées
(`/provisions/entreprises/{entreprise_id}/...`), protégées par les
permissions `provision.*` (`exiger_permission`), sur le modèle de
`immobilisations/router.py`.

Pas de route de saisie pour un `MouvementProvision` : il se DÉCLENCHE
(`POST .../provisions/{id}/dotations` ou `.../reprises`), il ne se crée
pas à partir d'un corps de requête libre.
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import ContexteEntreprise, exiger_permission
from app.core.database import get_db
from app.modules.comptabilite.schemas import EcritureLecture
from app.modules.provisions.schemas import (
    DotationDemande,
    MouvementProvisionLecture,
    ProvisionCreation,
    ProvisionLecture,
    ProvisionMiseAJour,
    RepriseDemande,
)
from app.modules.provisions.service import ProvisionCreation as ProvisionCreationDonnees
from app.modules.provisions.service import ServiceProvisions

router = APIRouter(prefix="/provisions", tags=["Provisions"])


@router.post(
    "/entreprises/{entreprise_id}/provisions",
    response_model=ProvisionLecture,
    status_code=status.HTTP_201_CREATED,
)
def creer_provision(
    entreprise_id: uuid.UUID,
    donnees: ProvisionCreation,
    contexte: ContexteEntreprise = Depends(exiger_permission("provision.creer")),
    db: Session = Depends(get_db),
) -> ProvisionLecture:
    service = ServiceProvisions(db, contexte.entreprise_id)
    provision = service.creer_provision(
        ProvisionCreationDonnees(
            libelle=donnees.libelle,
            type_provision=donnees.type_provision,
            tiers_id=donnees.tiers_id,
            compte_dotation_id=donnees.compte_dotation_id,
            compte_provision_id=donnees.compte_provision_id,
            compte_reprise_id=donnees.compte_reprise_id,
        ),
        auteur_id=contexte.utilisateur_id,
    )
    db.commit()
    return ProvisionLecture.model_validate(provision)


@router.get(
    "/entreprises/{entreprise_id}/provisions",
    response_model=list[ProvisionLecture],
)
def lister_provisions(
    entreprise_id: uuid.UUID,
    type_provision: str | None = None,
    statut: str | None = None,
    contexte: ContexteEntreprise = Depends(exiger_permission("provision.consulter")),
    db: Session = Depends(get_db),
) -> list[ProvisionLecture]:
    service = ServiceProvisions(db, contexte.entreprise_id)
    return [
        ProvisionLecture.model_validate(p)
        for p in service.lister_provisions(type_provision=type_provision, statut=statut)
    ]


@router.get(
    "/entreprises/{entreprise_id}/provisions/{provision_id}",
    response_model=ProvisionLecture,
)
def lire_provision(
    entreprise_id: uuid.UUID,
    provision_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("provision.consulter")),
    db: Session = Depends(get_db),
) -> ProvisionLecture:
    service = ServiceProvisions(db, contexte.entreprise_id)
    return ProvisionLecture.model_validate(service.obtenir_provision(provision_id))


@router.patch(
    "/entreprises/{entreprise_id}/provisions/{provision_id}",
    response_model=ProvisionLecture,
)
def modifier_provision(
    entreprise_id: uuid.UUID,
    provision_id: uuid.UUID,
    donnees: ProvisionMiseAJour,
    contexte: ContexteEntreprise = Depends(exiger_permission("provision.modifier")),
    db: Session = Depends(get_db),
) -> ProvisionLecture:
    service = ServiceProvisions(db, contexte.entreprise_id)
    provision = service.modifier_provision(
        provision_id,
        auteur_id=contexte.utilisateur_id,
        libelle=donnees.libelle,
        tiers_id=donnees.tiers_id,
    )
    db.commit()
    return ProvisionLecture.model_validate(provision)


@router.get(
    "/entreprises/{entreprise_id}/provisions/{provision_id}/mouvements",
    response_model=list[MouvementProvisionLecture],
)
def lister_mouvements_provision(
    entreprise_id: uuid.UUID,
    provision_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("provision.consulter")),
    db: Session = Depends(get_db),
) -> list[MouvementProvisionLecture]:
    service = ServiceProvisions(db, contexte.entreprise_id)
    return [
        MouvementProvisionLecture.model_validate(m) for m in service.lister_mouvements(provision_id)
    ]


@router.post(
    "/entreprises/{entreprise_id}/provisions/{provision_id}/dotations",
    response_model=EcritureLecture,
    status_code=status.HTTP_201_CREATED,
)
def constituer_provision(
    entreprise_id: uuid.UUID,
    provision_id: uuid.UUID,
    donnees: DotationDemande,
    contexte: ContexteEntreprise = Depends(exiger_permission("provision.valider")),
    db: Session = Depends(get_db),
) -> EcritureLecture:
    service = ServiceProvisions(db, contexte.entreprise_id)
    ecriture = service.constituer_provision(
        provision_id,
        exercice_id=donnees.exercice_id,
        journal_id=donnees.journal_id,
        date_mouvement=donnees.date_mouvement,
        montant=donnees.montant,
        auteur_id=contexte.utilisateur_id,
    )
    db.commit()
    return EcritureLecture.model_validate(ecriture)


@router.post(
    "/entreprises/{entreprise_id}/provisions/{provision_id}/reprises",
    response_model=EcritureLecture,
    status_code=status.HTTP_201_CREATED,
)
def reprendre_provision(
    entreprise_id: uuid.UUID,
    provision_id: uuid.UUID,
    donnees: RepriseDemande,
    contexte: ContexteEntreprise = Depends(exiger_permission("provision.valider")),
    db: Session = Depends(get_db),
) -> EcritureLecture:
    service = ServiceProvisions(db, contexte.entreprise_id)
    ecriture = service.reprendre_provision(
        provision_id,
        exercice_id=donnees.exercice_id,
        journal_id=donnees.journal_id,
        date_mouvement=donnees.date_mouvement,
        montant=donnees.montant,
        auteur_id=contexte.utilisateur_id,
    )
    db.commit()
    return EcritureLecture.model_validate(ecriture)