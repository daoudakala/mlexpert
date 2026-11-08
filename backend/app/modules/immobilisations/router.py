"""Routes HTTP du module immobilisations.

Toutes les routes sont entreprise-scopées
(`/immobilisations/entreprises/{entreprise_id}/...`), protégées par les
permissions `immobilisation.*` (`exiger_permission`), sur le modèle de
`tresorerie/router.py`.

Pas de route de saisie pour une ligne de plan d'amortissement : elle se
GÉNÈRE (`POST .../lignes-amortissement/{exercice_id}`), elle ne se crée
pas à partir d'un corps de requête libre (voir `schemas.py`).
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import ContexteEntreprise, exiger_permission
from app.core.database import get_db
from app.modules.comptabilite.schemas import EcritureLecture
from app.modules.immobilisations.schemas import (
    CessionDemande,
    GenerationEcritureDemande,
    ImmobilisationCreation,
    ImmobilisationLecture,
    ImmobilisationMiseAJour,
    LigneAmortissementLecture,
    ReformeDemande,
)
from app.modules.immobilisations.service import CessionDemande as CessionDemandeDonnees
from app.modules.immobilisations.service import ImmobilisationCreation as ImmobilisationCreationDonnees
from app.modules.immobilisations.service import ReformeDemande as ReformeDemandeDonnees
from app.modules.immobilisations.service import ServiceImmobilisations

router = APIRouter(prefix="/immobilisations", tags=["Immobilisations"])


@router.post(
    "/entreprises/{entreprise_id}/immobilisations",
    response_model=ImmobilisationLecture,
    status_code=status.HTTP_201_CREATED,
)
def creer_immobilisation(
    entreprise_id: uuid.UUID,
    donnees: ImmobilisationCreation,
    contexte: ContexteEntreprise = Depends(exiger_permission("immobilisation.creer")),
    db: Session = Depends(get_db),
) -> ImmobilisationLecture:
    service = ServiceImmobilisations(db, contexte.entreprise_id)
    immobilisation = service.creer_immobilisation(
        ImmobilisationCreationDonnees(
            libelle=donnees.libelle,
            categorie=donnees.categorie,
            numero_inventaire=donnees.numero_inventaire,
            date_acquisition=donnees.date_acquisition,
            date_mise_en_service=donnees.date_mise_en_service,
            valeur_origine=donnees.valeur_origine,
            valeur_residuelle=donnees.valeur_residuelle,
            duree_amortissement_annees=donnees.duree_amortissement_annees,
            methode_amortissement=donnees.methode_amortissement,
            taux_degressif=donnees.taux_degressif,
            compte_immobilisation_id=donnees.compte_immobilisation_id,
            compte_amortissement_id=donnees.compte_amortissement_id,
            compte_dotation_id=donnees.compte_dotation_id,
            fournisseur_id=donnees.fournisseur_id,
        ),
        auteur_id=contexte.utilisateur_id,
    )
    db.commit()
    return ImmobilisationLecture.model_validate(immobilisation)


@router.get(
    "/entreprises/{entreprise_id}/immobilisations",
    response_model=list[ImmobilisationLecture],
)
def lister_immobilisations(
    entreprise_id: uuid.UUID,
    statut: str | None = None,
    contexte: ContexteEntreprise = Depends(exiger_permission("immobilisation.consulter")),
    db: Session = Depends(get_db),
) -> list[ImmobilisationLecture]:
    service = ServiceImmobilisations(db, contexte.entreprise_id)
    return [ImmobilisationLecture.model_validate(i) for i in service.lister_immobilisations(statut=statut)]


@router.get(
    "/entreprises/{entreprise_id}/immobilisations/{immobilisation_id}",
    response_model=ImmobilisationLecture,
)
def lire_immobilisation(
    entreprise_id: uuid.UUID,
    immobilisation_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("immobilisation.consulter")),
    db: Session = Depends(get_db),
) -> ImmobilisationLecture:
    service = ServiceImmobilisations(db, contexte.entreprise_id)
    return ImmobilisationLecture.model_validate(service.obtenir_immobilisation(immobilisation_id))


@router.patch(
    "/entreprises/{entreprise_id}/immobilisations/{immobilisation_id}",
    response_model=ImmobilisationLecture,
)
def modifier_immobilisation(
    entreprise_id: uuid.UUID,
    immobilisation_id: uuid.UUID,
    donnees: ImmobilisationMiseAJour,
    contexte: ContexteEntreprise = Depends(exiger_permission("immobilisation.modifier")),
    db: Session = Depends(get_db),
) -> ImmobilisationLecture:
    service = ServiceImmobilisations(db, contexte.entreprise_id)
    immobilisation = service.modifier_immobilisation(
        immobilisation_id,
        auteur_id=contexte.utilisateur_id,
        libelle=donnees.libelle,
        categorie=donnees.categorie,
        numero_inventaire=donnees.numero_inventaire,
        fournisseur_id=donnees.fournisseur_id,
    )
    db.commit()
    return ImmobilisationLecture.model_validate(immobilisation)


@router.post(
    "/entreprises/{entreprise_id}/immobilisations/{immobilisation_id}/lignes-amortissement/{exercice_id}",
    response_model=LigneAmortissementLecture,
    status_code=status.HTTP_201_CREATED,
)
def generer_ligne_amortissement(
    entreprise_id: uuid.UUID,
    immobilisation_id: uuid.UUID,
    exercice_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("immobilisation.valider")),
    db: Session = Depends(get_db),
) -> LigneAmortissementLecture:
    service = ServiceImmobilisations(db, contexte.entreprise_id)
    ligne = service.generer_ligne_amortissement(immobilisation_id, exercice_id, auteur_id=contexte.utilisateur_id)
    db.commit()
    return LigneAmortissementLecture.model_validate(ligne)


@router.get(
    "/entreprises/{entreprise_id}/immobilisations/{immobilisation_id}/lignes-amortissement",
    response_model=list[LigneAmortissementLecture],
)
def lister_lignes_amortissement(
    entreprise_id: uuid.UUID,
    immobilisation_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("immobilisation.consulter")),
    db: Session = Depends(get_db),
) -> list[LigneAmortissementLecture]:
    service = ServiceImmobilisations(db, contexte.entreprise_id)
    return [
        LigneAmortissementLecture.model_validate(l)
        for l in service.lister_lignes_amortissement(immobilisation_id)
    ]


@router.post(
    "/entreprises/{entreprise_id}/lignes-amortissement/{ligne_id}/generer-ecriture",
    response_model=EcritureLecture,
    status_code=status.HTTP_201_CREATED,
)
def generer_ecriture_amortissement(
    entreprise_id: uuid.UUID,
    ligne_id: uuid.UUID,
    donnees: GenerationEcritureDemande,
    contexte: ContexteEntreprise = Depends(exiger_permission("immobilisation.valider")),
    db: Session = Depends(get_db),
) -> EcritureLecture:
    service = ServiceImmobilisations(db, contexte.entreprise_id)
    ecriture = service.generer_ecriture_amortissement(
        ligne_id, journal_id=donnees.journal_id, auteur_id=contexte.utilisateur_id
    )
    db.commit()
    return EcritureLecture.model_validate(ecriture)


@router.post(
    "/entreprises/{entreprise_id}/immobilisations/{immobilisation_id}/ceder",
    response_model=ImmobilisationLecture,
)
def ceder_immobilisation(
    entreprise_id: uuid.UUID,
    immobilisation_id: uuid.UUID,
    donnees: CessionDemande,
    contexte: ContexteEntreprise = Depends(exiger_permission("immobilisation.ceder")),
    db: Session = Depends(get_db),
) -> ImmobilisationLecture:
    service = ServiceImmobilisations(db, contexte.entreprise_id)
    immobilisation = service.ceder_immobilisation(
        immobilisation_id,
        CessionDemandeDonnees(
            date_sortie=donnees.date_sortie,
            prix_cession=donnees.prix_cession,
            journal_id=donnees.journal_id,
            compte_tresorerie_id=donnees.compte_tresorerie_id,
            compte_produit_cession_id=donnees.compte_produit_cession_id,
            compte_valeur_comptable_sortie_id=donnees.compte_valeur_comptable_sortie_id,
        ),
        auteur_id=contexte.utilisateur_id,
    )
    db.commit()
    return ImmobilisationLecture.model_validate(immobilisation)


@router.post(
    "/entreprises/{entreprise_id}/immobilisations/{immobilisation_id}/reformer",
    response_model=ImmobilisationLecture,
)
def reformer_immobilisation(
    entreprise_id: uuid.UUID,
    immobilisation_id: uuid.UUID,
    donnees: ReformeDemande,
    contexte: ContexteEntreprise = Depends(exiger_permission("immobilisation.ceder")),
    db: Session = Depends(get_db),
) -> ImmobilisationLecture:
    service = ServiceImmobilisations(db, contexte.entreprise_id)
    immobilisation = service.reformer_immobilisation(
        immobilisation_id,
        ReformeDemandeDonnees(
            date_sortie=donnees.date_sortie,
            journal_id=donnees.journal_id,
            compte_valeur_comptable_sortie_id=donnees.compte_valeur_comptable_sortie_id,
        ),
        auteur_id=contexte.utilisateur_id,
    )
    db.commit()
    return ImmobilisationLecture.model_validate(immobilisation)