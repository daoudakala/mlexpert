"""Routes HTTP du module utilisateurs."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import exiger_administrateur_plateforme, get_utilisateur_courant
from app.core.database import get_db
from app.modules.auth.service import ServiceAuth
from app.modules.droits.service import ServiceDroits
from app.modules.utilisateurs.models import Utilisateur
from app.modules.utilisateurs.schemas import (
    ChangementMotDePasse,
    MonProfilLecture,
    ReinitialisationMotDePasse,
    UtilisateurCreation,
    UtilisateurLecture,
    UtilisateurMiseAJourProfil,
)
from app.modules.utilisateurs.service import ServiceUtilisateurs

router = APIRouter(prefix="/utilisateurs", tags=["Utilisateurs"])


# --- Profil de l'utilisateur connecté ---------------------------------------


@router.get("/moi", response_model=MonProfilLecture)
def lire_mon_profil(
    utilisateur: Utilisateur = Depends(get_utilisateur_courant),
    db: Session = Depends(get_db),
) -> MonProfilLecture:
    administrateur_plateforme = ServiceDroits(db).est_administrateur_plateforme(utilisateur.id)
    return MonProfilLecture(
        **UtilisateurLecture.model_validate(utilisateur).model_dump(),
        administrateur_plateforme=administrateur_plateforme,
    )


@router.patch("/moi", response_model=UtilisateurLecture)
def mettre_a_jour_mon_profil(
    donnees: UtilisateurMiseAJourProfil,
    utilisateur: Utilisateur = Depends(get_utilisateur_courant),
    db: Session = Depends(get_db),
) -> UtilisateurLecture:
    service = ServiceUtilisateurs(db)
    mis_a_jour = service.mettre_a_jour_profil(
        utilisateur.id,
        nom=donnees.nom,
        prenom=donnees.prenom,
        telephone=donnees.telephone,
    )
    db.commit()
    return UtilisateurLecture.model_validate(mis_a_jour)


@router.post("/moi/mot-de-passe", status_code=status.HTTP_204_NO_CONTENT)
def changer_mon_mot_de_passe(
    donnees: ChangementMotDePasse,
    utilisateur: Utilisateur = Depends(get_utilisateur_courant),
    db: Session = Depends(get_db),
) -> None:
    service = ServiceUtilisateurs(db)
    service.changer_mot_de_passe(
        utilisateur.id,
        ancien_mot_de_passe=donnees.ancien_mot_de_passe,
        nouveau_mot_de_passe=donnees.nouveau_mot_de_passe,
    )
    db.commit()


# --- Administration des comptes (Administrateur plateforme) -----------------


@router.post(
    "",
    response_model=UtilisateurLecture,
    status_code=status.HTTP_201_CREATED,
)
def creer_utilisateur(
    donnees: UtilisateurCreation,
    administrateur: Utilisateur = Depends(exiger_administrateur_plateforme),
    db: Session = Depends(get_db),
) -> UtilisateurLecture:
    service = ServiceUtilisateurs(db)
    utilisateur = service.creer_utilisateur(
        auteur_id=administrateur.id,
        email=donnees.email,
        mot_de_passe=donnees.mot_de_passe,
        nom=donnees.nom,
        prenom=donnees.prenom,
        telephone=donnees.telephone,
    )
    db.commit()
    return UtilisateurLecture.model_validate(utilisateur)


@router.get(
    "",
    response_model=list[UtilisateurLecture],
    dependencies=[Depends(exiger_administrateur_plateforme)],
)
def lister_utilisateurs(db: Session = Depends(get_db)) -> list[UtilisateurLecture]:
    service = ServiceUtilisateurs(db)
    return [UtilisateurLecture.model_validate(u) for u in service.lister_utilisateurs()]


@router.get(
    "/{utilisateur_id}",
    response_model=UtilisateurLecture,
    dependencies=[Depends(exiger_administrateur_plateforme)],
)
def lire_utilisateur(
    utilisateur_id: uuid.UUID, db: Session = Depends(get_db)
) -> UtilisateurLecture:
    service = ServiceUtilisateurs(db)
    return UtilisateurLecture.model_validate(service.obtenir_utilisateur(utilisateur_id))


@router.post("/{utilisateur_id}/desactiver", status_code=status.HTTP_204_NO_CONTENT)
def desactiver_utilisateur(
    utilisateur_id: uuid.UUID,
    administrateur: Utilisateur = Depends(exiger_administrateur_plateforme),
    db: Session = Depends(get_db),
) -> None:
    """Désactive le compte ET révoque immédiatement toutes ses sessions
    actives, pour qu'un jeton d'accès déjà émis ne survive pas à la
    désactivation."""
    service = ServiceUtilisateurs(db)
    service.desactiver_utilisateur(utilisateur_id, auteur_id=administrateur.id)
    ServiceAuth(db).revoquer_toutes_les_sessions(utilisateur_id, auteur_id=administrateur.id)
    db.commit()


@router.post("/{utilisateur_id}/reactiver", status_code=status.HTTP_204_NO_CONTENT)
def reactiver_utilisateur(
    utilisateur_id: uuid.UUID,
    administrateur: Utilisateur = Depends(exiger_administrateur_plateforme),
    db: Session = Depends(get_db),
) -> None:
    service = ServiceUtilisateurs(db)
    service.reactiver_utilisateur(utilisateur_id, auteur_id=administrateur.id)
    db.commit()


@router.post(
    "/{utilisateur_id}/reinitialiser-mot-de-passe",
    status_code=status.HTTP_204_NO_CONTENT,
)
def reinitialiser_mot_de_passe(
    utilisateur_id: uuid.UUID,
    donnees: ReinitialisationMotDePasse,
    administrateur: Utilisateur = Depends(exiger_administrateur_plateforme),
    db: Session = Depends(get_db),
) -> None:
    service = ServiceUtilisateurs(db)
    service.reinitialiser_mot_de_passe(
        utilisateur_id,
        auteur_id=administrateur.id,
        nouveau_mot_de_passe=donnees.nouveau_mot_de_passe,
    )
    db.commit()
