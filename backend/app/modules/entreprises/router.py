"""Routes HTTP du module entreprises.

Deux niveaux d'accès cohabitent (Annexe B, points 12-13) :
- l'administration de la fiche (créer, modifier, archiver) est réservée à
  l'administrateur plateforme (cahier, section 26) ;
- la consultation d'une fiche est ouverte à l'administrateur plateforme
  OU à un utilisateur affecté à cette entreprise (portefeuille du cabinet,
  vue unique du client).
"""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import exiger_administrateur_plateforme, get_utilisateur_courant
from app.core.database import get_db
from app.core.exceptions import AccesRefuse
from app.modules.droits.service import ServiceDroits
from app.modules.entreprises.models import Entreprise
from app.modules.entreprises.schemas import (
    EntrepriseCreation,
    EntrepriseLecture,
    EntrepriseMiseAJour,
)
from app.modules.entreprises.service import ServiceEntreprises
from app.modules.utilisateurs.models import Utilisateur

router = APIRouter(prefix="/entreprises", tags=["Entreprises"])


def _acceder_fiche_entreprise(
    entreprise_id: uuid.UUID,
    utilisateur: Utilisateur = Depends(get_utilisateur_courant),
    db: Session = Depends(get_db),
) -> Entreprise:
    """Autorise l'administrateur plateforme, ou tout utilisateur affecté à
    cette entreprise (peu importe son rôle ni ses restrictions)."""
    service_droits = ServiceDroits(db)
    service_entreprises = ServiceEntreprises(db)

    est_admin = service_droits.est_administrateur_plateforme(utilisateur.id)
    a_une_affectation = service_droits.est_affecte(utilisateur.id, entreprise_id)
    if not est_admin and not a_une_affectation:
        raise AccesRefuse("Vous n'avez pas accès à cette entreprise.")

    return service_entreprises.obtenir_entreprise(entreprise_id)


# --- Consultation ------------------------------------------------------------


@router.get("/moi", response_model=list[EntrepriseLecture])
def lister_mon_portefeuille(
    utilisateur: Utilisateur = Depends(get_utilisateur_courant),
    db: Session = Depends(get_db),
) -> list[EntrepriseLecture]:
    """Les entreprises auxquelles l'utilisateur connecté est affecté."""
    service_droits = ServiceDroits(db)
    service_entreprises = ServiceEntreprises(db)

    affectations = service_droits.lister_affectations_utilisateur(utilisateur.id)
    entreprises = [
        service_entreprises.obtenir_entreprise(a.entreprise_id) for a in affectations
    ]
    return [EntrepriseLecture.model_validate(e) for e in entreprises]


@router.get("/{entreprise_id}", response_model=EntrepriseLecture)
def lire_fiche_entreprise(
    entreprise: Entreprise = Depends(_acceder_fiche_entreprise),
) -> EntrepriseLecture:
    return EntrepriseLecture.model_validate(entreprise)


# --- Administration (Administrateur plateforme) ------------------------------


@router.post("", response_model=EntrepriseLecture, status_code=status.HTTP_201_CREATED)
def creer_entreprise(
    donnees: EntrepriseCreation,
    administrateur: Utilisateur = Depends(exiger_administrateur_plateforme),
    db: Session = Depends(get_db),
) -> EntrepriseLecture:
    service = ServiceEntreprises(db)
    entreprise = service.creer_entreprise(auteur_id=administrateur.id, **donnees.model_dump())
    db.commit()
    return EntrepriseLecture.model_validate(entreprise)


@router.get(
    "",
    response_model=list[EntrepriseLecture],
    dependencies=[Depends(exiger_administrateur_plateforme)],
)
def lister_entreprises(
    q: str | None = Query(default=None, description="Recherche sur la raison sociale ou le sigle"),
    db: Session = Depends(get_db),
) -> list[EntrepriseLecture]:
    service = ServiceEntreprises(db)
    entreprises = service.rechercher_entreprises(q) if q else service.lister_entreprises()
    return [EntrepriseLecture.model_validate(e) for e in entreprises]


@router.patch("/{entreprise_id}", response_model=EntrepriseLecture)
def modifier_fiche_entreprise(
    entreprise_id: uuid.UUID,
    donnees: EntrepriseMiseAJour,
    administrateur: Utilisateur = Depends(exiger_administrateur_plateforme),
    db: Session = Depends(get_db),
) -> EntrepriseLecture:
    service = ServiceEntreprises(db)
    entreprise = service.mettre_a_jour_fiche(
        entreprise_id, auteur_id=administrateur.id, **donnees.model_dump(exclude_unset=True)
    )
    db.commit()
    return EntrepriseLecture.model_validate(entreprise)


@router.post("/{entreprise_id}/archiver", status_code=status.HTTP_204_NO_CONTENT)
def archiver_entreprise(
    entreprise_id: uuid.UUID,
    administrateur: Utilisateur = Depends(exiger_administrateur_plateforme),
    db: Session = Depends(get_db),
) -> None:
    service = ServiceEntreprises(db)
    service.archiver(entreprise_id, auteur_id=administrateur.id)
    db.commit()


@router.post("/{entreprise_id}/suspendre", status_code=status.HTTP_204_NO_CONTENT)
def suspendre_entreprise(
    entreprise_id: uuid.UUID,
    administrateur: Utilisateur = Depends(exiger_administrateur_plateforme),
    db: Session = Depends(get_db),
) -> None:
    service = ServiceEntreprises(db)
    service.suspendre(entreprise_id, auteur_id=administrateur.id)
    db.commit()


@router.post("/{entreprise_id}/reactiver", status_code=status.HTTP_204_NO_CONTENT)
def reactiver_entreprise(
    entreprise_id: uuid.UUID,
    administrateur: Utilisateur = Depends(exiger_administrateur_plateforme),
    db: Session = Depends(get_db),
) -> None:
    service = ServiceEntreprises(db)
    service.reactiver(entreprise_id, auteur_id=administrateur.id)
    db.commit()