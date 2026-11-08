"""Routes HTTP du module tiers.

Convention de permission : `tiers.<action>`, avec `archiver` pour la
désactivation et `annuler` pour la réactivation (comme `exercice`/`periode`).
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import ContexteEntreprise, exiger_permission
from app.core.database import get_db
from app.modules.tiers.schemas import (
    TiersComptesCollectifs,
    TiersCreation,
    TiersLecture,
    TiersMiseAJour,
)
from app.modules.tiers.service import ServiceTiers

router = APIRouter(prefix="/entreprises/{entreprise_id}/tiers", tags=["Tiers"])


@router.post("", response_model=TiersLecture, status_code=status.HTTP_201_CREATED)
def creer_tiers(
    donnees: TiersCreation,
    contexte: ContexteEntreprise = Depends(exiger_permission("tiers.creer")),
    db: Session = Depends(get_db),
) -> TiersLecture:
    service = ServiceTiers(db, contexte.entreprise_id)
    tiers = service.creer_tiers(
        auteur_id=contexte.utilisateur_id,
        code=donnees.code,
        raison_sociale=donnees.raison_sociale,
        nif=donnees.nif,
        rccm=donnees.rccm,
        adresse=donnees.adresse,
        email=donnees.email,
        telephone=donnees.telephone,
        delai_paiement_jours=donnees.delai_paiement_jours,
        plafond_credit=donnees.plafond_credit,
        compte_collectif_client_id=donnees.compte_collectif_client_id,
        compte_collectif_fournisseur_id=donnees.compte_collectif_fournisseur_id,
        confirmer_malgre_doublon=donnees.confirmer_malgre_doublon,
    )
    db.commit()
    return TiersLecture.model_validate(tiers)


@router.get("", response_model=list[TiersLecture])
def lister_tiers(
    actifs_seulement: bool = True,
    client_seulement: bool = False,
    fournisseur_seulement: bool = False,
    contexte: ContexteEntreprise = Depends(exiger_permission("tiers.consulter")),
    db: Session = Depends(get_db),
) -> list[TiersLecture]:
    service = ServiceTiers(db, contexte.entreprise_id)
    tiers = service.lister_tiers(
        actifs_seulement=actifs_seulement,
        client_seulement=client_seulement,
        fournisseur_seulement=fournisseur_seulement,
    )
    return [TiersLecture.model_validate(t) for t in tiers]


@router.get("/{tiers_id}", response_model=TiersLecture)
def lire_tiers(
    tiers_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("tiers.consulter")),
    db: Session = Depends(get_db),
) -> TiersLecture:
    service = ServiceTiers(db, contexte.entreprise_id)
    return TiersLecture.model_validate(service.obtenir_tiers(tiers_id))


@router.patch("/{tiers_id}", response_model=TiersLecture)
def modifier_tiers(
    tiers_id: uuid.UUID,
    donnees: TiersMiseAJour,
    contexte: ContexteEntreprise = Depends(exiger_permission("tiers.modifier")),
    db: Session = Depends(get_db),
) -> TiersLecture:
    service = ServiceTiers(db, contexte.entreprise_id)
    tiers = service.modifier_tiers(
        tiers_id,
        auteur_id=contexte.utilisateur_id,
        raison_sociale=donnees.raison_sociale,
        nif=donnees.nif,
        rccm=donnees.rccm,
        adresse=donnees.adresse,
        email=donnees.email,
        telephone=donnees.telephone,
        delai_paiement_jours=donnees.delai_paiement_jours,
        plafond_credit=donnees.plafond_credit,
    )
    db.commit()
    return TiersLecture.model_validate(tiers)


@router.put("/{tiers_id}/comptes-collectifs", response_model=TiersLecture)
def modifier_comptes_collectifs(
    tiers_id: uuid.UUID,
    donnees: TiersComptesCollectifs,
    contexte: ContexteEntreprise = Depends(exiger_permission("tiers.modifier")),
    db: Session = Depends(get_db),
) -> TiersLecture:
    service = ServiceTiers(db, contexte.entreprise_id)
    tiers = service.modifier_comptes_collectifs(
        tiers_id,
        auteur_id=contexte.utilisateur_id,
        compte_collectif_client_id=donnees.compte_collectif_client_id,
        compte_collectif_fournisseur_id=donnees.compte_collectif_fournisseur_id,
    )
    db.commit()
    return TiersLecture.model_validate(tiers)


@router.post("/{tiers_id}/desactiver", status_code=status.HTTP_204_NO_CONTENT)
def desactiver_tiers(
    tiers_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("tiers.archiver")),
    db: Session = Depends(get_db),
) -> None:
    service = ServiceTiers(db, contexte.entreprise_id)
    service.desactiver_tiers(tiers_id, auteur_id=contexte.utilisateur_id)
    db.commit()


@router.post("/{tiers_id}/reactiver", status_code=status.HTTP_204_NO_CONTENT)
def reactiver_tiers(
    tiers_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("tiers.annuler")),
    db: Session = Depends(get_db),
) -> None:
    service = ServiceTiers(db, contexte.entreprise_id)
    service.reactiver_tiers(tiers_id, auteur_id=contexte.utilisateur_id)
    db.commit()