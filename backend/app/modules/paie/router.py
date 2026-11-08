"""Routes HTTP du module paie.

Toutes les routes sont entreprise-scopées (`/paie/entreprises/{entreprise_id}/...`),
protégées par les permissions `employe.*`/`rubrique_paie.*`/`bulletin.*`
(`exiger_permission`), sur le modèle de `immobilisations/router.py`.

Pas de route de suppression pour une rubrique de paie (désactivation
logique seulement, comme `RubriquePaie.actif` — voir `service.py`) ni
pour un employé (désactivation via `date_sortie`, réactivable).
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import ContexteEntreprise, exiger_permission
from app.core.database import get_db
from app.modules.comptabilite.schemas import EcritureLecture
from app.modules.paie.schemas import (
    BulletinCreation,
    BulletinLecture,
    BulletinMiseAJourLignes,
    EmployeCreation,
    EmployeDesactivation,
    EmployeLecture,
    EmployeMiseAJour,
    GenerationEcritureBulletinDemande,
    LigneBulletinLecture,
    RubriqueCompteComptable,
    RubriquePaieCreation,
    RubriquePaieLecture,
)
from app.modules.paie.service import BulletinCreation as BulletinCreationDonnees
from app.modules.paie.service import LigneBulletinSaisie as LigneBulletinSaisieDonnees
from app.modules.paie.service import ServicePaie

router = APIRouter(prefix="/paie", tags=["Paie"])


def _lignes_saisies(donnees_lignes: list) -> list[LigneBulletinSaisieDonnees]:
    return [
        LigneBulletinSaisieDonnees(
            rubrique_id=ligne.rubrique_id, montant=ligne.montant, libelle=ligne.libelle
        )
        for ligne in donnees_lignes
    ]


# --- Employés ------------------------------------------------------------------


@router.post(
    "/entreprises/{entreprise_id}/employes",
    response_model=EmployeLecture,
    status_code=status.HTTP_201_CREATED,
)
def creer_employe(
    entreprise_id: uuid.UUID,
    donnees: EmployeCreation,
    contexte: ContexteEntreprise = Depends(exiger_permission("employe.creer")),
    db: Session = Depends(get_db),
) -> EmployeLecture:
    service = ServicePaie(db, contexte.entreprise_id)
    employe = service.creer_employe(
        matricule=donnees.matricule,
        nom=donnees.nom,
        prenom=donnees.prenom,
        poste=donnees.poste,
        date_embauche=donnees.date_embauche,
        salaire_base=donnees.salaire_base,
        auteur_id=contexte.utilisateur_id,
    )
    db.commit()
    return EmployeLecture.model_validate(employe)


@router.get("/entreprises/{entreprise_id}/employes", response_model=list[EmployeLecture])
def lister_employes(
    entreprise_id: uuid.UUID,
    actifs_seulement: bool = True,
    contexte: ContexteEntreprise = Depends(exiger_permission("employe.consulter")),
    db: Session = Depends(get_db),
) -> list[EmployeLecture]:
    service = ServicePaie(db, contexte.entreprise_id)
    return [
        EmployeLecture.model_validate(e)
        for e in service.lister_employes(actifs_seulement=actifs_seulement)
    ]


@router.get("/entreprises/{entreprise_id}/employes/{employe_id}", response_model=EmployeLecture)
def lire_employe(
    entreprise_id: uuid.UUID,
    employe_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("employe.consulter")),
    db: Session = Depends(get_db),
) -> EmployeLecture:
    service = ServicePaie(db, contexte.entreprise_id)
    return EmployeLecture.model_validate(service.obtenir_employe(employe_id))


@router.patch("/entreprises/{entreprise_id}/employes/{employe_id}", response_model=EmployeLecture)
def modifier_employe(
    entreprise_id: uuid.UUID,
    employe_id: uuid.UUID,
    donnees: EmployeMiseAJour,
    contexte: ContexteEntreprise = Depends(exiger_permission("employe.modifier")),
    db: Session = Depends(get_db),
) -> EmployeLecture:
    service = ServicePaie(db, contexte.entreprise_id)
    employe = service.modifier_employe(
        employe_id,
        auteur_id=contexte.utilisateur_id,
        nom=donnees.nom,
        prenom=donnees.prenom,
        poste=donnees.poste,
        salaire_base=donnees.salaire_base,
    )
    db.commit()
    return EmployeLecture.model_validate(employe)


@router.post(
    "/entreprises/{entreprise_id}/employes/{employe_id}/desactiver",
    response_model=EmployeLecture,
)
def desactiver_employe(
    entreprise_id: uuid.UUID,
    employe_id: uuid.UUID,
    donnees: EmployeDesactivation,
    contexte: ContexteEntreprise = Depends(exiger_permission("employe.archiver")),
    db: Session = Depends(get_db),
) -> EmployeLecture:
    service = ServicePaie(db, contexte.entreprise_id)
    employe = service.desactiver_employe(
        employe_id, date_sortie=donnees.date_sortie, auteur_id=contexte.utilisateur_id
    )
    db.commit()
    return EmployeLecture.model_validate(employe)


@router.post(
    "/entreprises/{entreprise_id}/employes/{employe_id}/reactiver",
    response_model=EmployeLecture,
)
def reactiver_employe(
    entreprise_id: uuid.UUID,
    employe_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("employe.archiver")),
    db: Session = Depends(get_db),
) -> EmployeLecture:
    service = ServicePaie(db, contexte.entreprise_id)
    employe = service.reactiver_employe(employe_id, auteur_id=contexte.utilisateur_id)
    db.commit()
    return EmployeLecture.model_validate(employe)


# --- Rubriques de paie -----------------------------------------------------------


@router.post(
    "/entreprises/{entreprise_id}/rubriques",
    response_model=RubriquePaieLecture,
    status_code=status.HTTP_201_CREATED,
)
def creer_rubrique(
    entreprise_id: uuid.UUID,
    donnees: RubriquePaieCreation,
    contexte: ContexteEntreprise = Depends(exiger_permission("rubrique_paie.creer")),
    db: Session = Depends(get_db),
) -> RubriquePaieLecture:
    service = ServicePaie(db, contexte.entreprise_id)
    rubrique = service.creer_rubrique(
        code=donnees.code,
        libelle=donnees.libelle,
        type_rubrique=donnees.type_rubrique,
        compte_comptable_id=donnees.compte_comptable_id,
        auteur_id=contexte.utilisateur_id,
    )
    db.commit()
    return RubriquePaieLecture.model_validate(rubrique)


@router.get("/entreprises/{entreprise_id}/rubriques", response_model=list[RubriquePaieLecture])
def lister_rubriques(
    entreprise_id: uuid.UUID,
    actifs_seulement: bool = True,
    contexte: ContexteEntreprise = Depends(exiger_permission("rubrique_paie.consulter")),
    db: Session = Depends(get_db),
) -> list[RubriquePaieLecture]:
    service = ServicePaie(db, contexte.entreprise_id)
    return [
        RubriquePaieLecture.model_validate(r)
        for r in service.lister_rubriques(actifs_seulement=actifs_seulement)
    ]


@router.get(
    "/entreprises/{entreprise_id}/rubriques/{rubrique_id}", response_model=RubriquePaieLecture
)
def lire_rubrique(
    entreprise_id: uuid.UUID,
    rubrique_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("rubrique_paie.consulter")),
    db: Session = Depends(get_db),
) -> RubriquePaieLecture:
    service = ServicePaie(db, contexte.entreprise_id)
    return RubriquePaieLecture.model_validate(service.obtenir_rubrique(rubrique_id))


@router.post(
    "/entreprises/{entreprise_id}/rubriques/{rubrique_id}/compte-comptable",
    response_model=RubriquePaieLecture,
)
def definir_compte_comptable_rubrique(
    entreprise_id: uuid.UUID,
    rubrique_id: uuid.UUID,
    donnees: RubriqueCompteComptable,
    contexte: ContexteEntreprise = Depends(exiger_permission("rubrique_paie.modifier")),
    db: Session = Depends(get_db),
) -> RubriquePaieLecture:
    service = ServicePaie(db, contexte.entreprise_id)
    rubrique = service.definir_compte_comptable(
        rubrique_id,
        compte_comptable_id=donnees.compte_comptable_id,
        auteur_id=contexte.utilisateur_id,
    )
    db.commit()
    return RubriquePaieLecture.model_validate(rubrique)


@router.post(
    "/entreprises/{entreprise_id}/rubriques/{rubrique_id}/desactiver",
    response_model=RubriquePaieLecture,
)
def desactiver_rubrique(
    entreprise_id: uuid.UUID,
    rubrique_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("rubrique_paie.archiver")),
    db: Session = Depends(get_db),
) -> RubriquePaieLecture:
    service = ServicePaie(db, contexte.entreprise_id)
    rubrique = service.desactiver_rubrique(rubrique_id, auteur_id=contexte.utilisateur_id)
    db.commit()
    return RubriquePaieLecture.model_validate(rubrique)


# --- Bulletins de paie -----------------------------------------------------------


@router.post(
    "/entreprises/{entreprise_id}/bulletins",
    response_model=BulletinLecture,
    status_code=status.HTTP_201_CREATED,
)
def creer_bulletin(
    entreprise_id: uuid.UUID,
    donnees: BulletinCreation,
    contexte: ContexteEntreprise = Depends(exiger_permission("bulletin.creer")),
    db: Session = Depends(get_db),
) -> BulletinLecture:
    service = ServicePaie(db, contexte.entreprise_id)
    bulletin = service.creer_bulletin(
        BulletinCreationDonnees(
            employe_id=donnees.employe_id,
            exercice_id=donnees.exercice_id,
            periode_debut=donnees.periode_debut,
            periode_fin=donnees.periode_fin,
            lignes=_lignes_saisies(donnees.lignes),
        ),
        auteur_id=contexte.utilisateur_id,
    )
    db.commit()
    return BulletinLecture.model_validate(bulletin)


@router.get("/entreprises/{entreprise_id}/bulletins", response_model=list[BulletinLecture])
def lister_bulletins(
    entreprise_id: uuid.UUID,
    employe_id: uuid.UUID | None = None,
    exercice_id: uuid.UUID | None = None,
    statut: str | None = None,
    contexte: ContexteEntreprise = Depends(exiger_permission("bulletin.consulter")),
    db: Session = Depends(get_db),
) -> list[BulletinLecture]:
    service = ServicePaie(db, contexte.entreprise_id)
    return [
        BulletinLecture.model_validate(b)
        for b in service.lister_bulletins(employe_id=employe_id, exercice_id=exercice_id, statut=statut)
    ]


@router.get(
    "/entreprises/{entreprise_id}/bulletins/{bulletin_id}", response_model=BulletinLecture
)
def lire_bulletin(
    entreprise_id: uuid.UUID,
    bulletin_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("bulletin.consulter")),
    db: Session = Depends(get_db),
) -> BulletinLecture:
    service = ServicePaie(db, contexte.entreprise_id)
    return BulletinLecture.model_validate(service.obtenir_bulletin(bulletin_id))


@router.get(
    "/entreprises/{entreprise_id}/bulletins/{bulletin_id}/lignes",
    response_model=list[LigneBulletinLecture],
)
def lister_lignes_bulletin(
    entreprise_id: uuid.UUID,
    bulletin_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("bulletin.consulter")),
    db: Session = Depends(get_db),
) -> list[LigneBulletinLecture]:
    service = ServicePaie(db, contexte.entreprise_id)
    return [LigneBulletinLecture.model_validate(l) for l in service.lister_lignes(bulletin_id)]


@router.patch(
    "/entreprises/{entreprise_id}/bulletins/{bulletin_id}", response_model=BulletinLecture
)
def modifier_bulletin(
    entreprise_id: uuid.UUID,
    bulletin_id: uuid.UUID,
    donnees: BulletinMiseAJourLignes,
    contexte: ContexteEntreprise = Depends(exiger_permission("bulletin.modifier")),
    db: Session = Depends(get_db),
) -> BulletinLecture:
    service = ServicePaie(db, contexte.entreprise_id)
    bulletin = service.modifier_bulletin(
        bulletin_id, lignes=_lignes_saisies(donnees.lignes), auteur_id=contexte.utilisateur_id
    )
    db.commit()
    return BulletinLecture.model_validate(bulletin)


@router.post("/entreprises/{entreprise_id}/bulletins/{bulletin_id}/supprimer")
def supprimer_bulletin(
    entreprise_id: uuid.UUID,
    bulletin_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("bulletin.modifier")),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    service = ServicePaie(db, contexte.entreprise_id)
    service.supprimer_bulletin(bulletin_id, auteur_id=contexte.utilisateur_id)
    db.commit()
    return {"statut": "supprimé"}


@router.post(
    "/entreprises/{entreprise_id}/bulletins/{bulletin_id}/valider", response_model=BulletinLecture
)
def valider_bulletin(
    entreprise_id: uuid.UUID,
    bulletin_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("bulletin.valider")),
    db: Session = Depends(get_db),
) -> BulletinLecture:
    service = ServicePaie(db, contexte.entreprise_id)
    bulletin = service.valider_bulletin(bulletin_id, auteur_id=contexte.utilisateur_id)
    db.commit()
    return BulletinLecture.model_validate(bulletin)


@router.post(
    "/entreprises/{entreprise_id}/bulletins/{bulletin_id}/generer-ecriture",
    response_model=EcritureLecture,
    status_code=status.HTTP_201_CREATED,
)
def generer_ecriture_bulletin(
    entreprise_id: uuid.UUID,
    bulletin_id: uuid.UUID,
    donnees: GenerationEcritureBulletinDemande,
    contexte: ContexteEntreprise = Depends(exiger_permission("bulletin.valider")),
    db: Session = Depends(get_db),
) -> EcritureLecture:
    service = ServicePaie(db, contexte.entreprise_id)
    ecriture = service.generer_ecriture_bulletin(
        bulletin_id,
        journal_id=donnees.journal_id,
        compte_net_a_payer_id=donnees.compte_net_a_payer_id,
        auteur_id=contexte.utilisateur_id,
    )
    db.commit()
    return EcritureLecture.model_validate(ecriture)