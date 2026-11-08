"""Routes HTTP du module tresorerie.

Toutes les routes sont entreprise-scopées
(`/tresorerie/entreprises/{entreprise_id}/...`), protégées par les
permissions `compte_bancaire.*` / `releve.*` / `rapprochement.*`
(`exiger_permission`), sur le modèle de `comptabilite/router.py`.

Convention de permission : `<ressource>.<action>`. `rapprochement` n'a
que `creer` et `annuler` : consulter les candidates au rapprochement
(lignes de relevé non rapprochées, lignes d'écriture non lettrées) est
couvert par `releve.consulter`, ce n'est pas une ressource à part.
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import ContexteEntreprise, exiger_permission
from app.core.database import get_db
from app.modules.comptabilite.schemas import LigneEcritureLecture
from app.modules.tresorerie.schemas import (
    AnnulationRapprochementDemande,
    CompteBancaireCreation,
    CompteBancaireLecture,
    LigneReleveLecture,
    RapprochementDemande,
    RapprochementReponse,
    ReleveAvecLignes,
    ReleveCreation,
    ReleveLecture,
    ReleveMiseAJour,
)
from app.modules.tresorerie.service import LigneReleveSaisie, ServiceTresorerie

router = APIRouter(prefix="/tresorerie", tags=["Trésorerie"])


def _lignes_saisies(donnees_lignes: list) -> list[LigneReleveSaisie]:
    return [
        LigneReleveSaisie(
            date_operation=ligne.date_operation,
            libelle=ligne.libelle,
            debit=ligne.debit,
            credit=ligne.credit,
            reference=ligne.reference,
        )
        for ligne in donnees_lignes
    ]


def _releve_avec_lignes(releve, lignes) -> ReleveAvecLignes:
    return ReleveAvecLignes.model_validate(
        {**ReleveLecture.model_validate(releve).model_dump(), "lignes": lignes}
    )


# --- Comptes bancaires -------------------------------------------------------


@router.post(
    "/entreprises/{entreprise_id}/comptes-bancaires",
    response_model=CompteBancaireLecture,
    status_code=status.HTTP_201_CREATED,
)
def creer_compte_bancaire(
    entreprise_id: uuid.UUID,
    donnees: CompteBancaireCreation,
    contexte: ContexteEntreprise = Depends(exiger_permission("compte_bancaire.creer")),
    db: Session = Depends(get_db),
) -> CompteBancaireLecture:
    service = ServiceTresorerie(db, contexte.entreprise_id)
    compte_bancaire = service.creer_compte_bancaire(
        auteur_id=contexte.utilisateur_id,
        journal_id=donnees.journal_id,
        compte_comptable_id=donnees.compte_comptable_id,
        libelle=donnees.libelle,
        banque=donnees.banque,
        numero_compte=donnees.numero_compte,
        iban=donnees.iban,
        solde_initial=donnees.solde_initial,
    )
    db.commit()
    return CompteBancaireLecture.model_validate(compte_bancaire)


@router.get(
    "/entreprises/{entreprise_id}/comptes-bancaires",
    response_model=list[CompteBancaireLecture],
)
def lister_comptes_bancaires(
    entreprise_id: uuid.UUID,
    actifs_seulement: bool = True,
    contexte: ContexteEntreprise = Depends(exiger_permission("compte_bancaire.consulter")),
    db: Session = Depends(get_db),
) -> list[CompteBancaireLecture]:
    service = ServiceTresorerie(db, contexte.entreprise_id)
    return [
        CompteBancaireLecture.model_validate(c)
        for c in service.lister_comptes_bancaires(actifs_seulement=actifs_seulement)
    ]


@router.get(
    "/entreprises/{entreprise_id}/comptes-bancaires/{compte_bancaire_id}",
    response_model=CompteBancaireLecture,
)
def lire_compte_bancaire(
    entreprise_id: uuid.UUID,
    compte_bancaire_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("compte_bancaire.consulter")),
    db: Session = Depends(get_db),
) -> CompteBancaireLecture:
    service = ServiceTresorerie(db, contexte.entreprise_id)
    return CompteBancaireLecture.model_validate(service.obtenir_compte_bancaire(compte_bancaire_id))


@router.post(
    "/entreprises/{entreprise_id}/comptes-bancaires/{compte_bancaire_id}/desactiver",
    status_code=status.HTTP_204_NO_CONTENT,
)
def desactiver_compte_bancaire(
    entreprise_id: uuid.UUID,
    compte_bancaire_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("compte_bancaire.archiver")),
    db: Session = Depends(get_db),
) -> None:
    service = ServiceTresorerie(db, contexte.entreprise_id)
    service.desactiver_compte_bancaire(compte_bancaire_id, auteur_id=contexte.utilisateur_id)
    db.commit()


@router.get(
    "/entreprises/{entreprise_id}/comptes-bancaires/{compte_bancaire_id}/lignes-non-rapprochees",
    response_model=list[LigneReleveLecture],
)
def lister_lignes_non_rapprochees(
    entreprise_id: uuid.UUID,
    compte_bancaire_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("releve.consulter")),
    db: Session = Depends(get_db),
) -> list[LigneReleveLecture]:
    service = ServiceTresorerie(db, contexte.entreprise_id)
    return [
        LigneReleveLecture.model_validate(l)
        for l in service.lister_lignes_non_rapprochees(compte_bancaire_id)
    ]


@router.get(
    "/entreprises/{entreprise_id}/comptes-bancaires/{compte_bancaire_id}/ecritures-candidates",
    response_model=list[LigneEcritureLecture],
)
def lister_ecritures_candidates(
    entreprise_id: uuid.UUID,
    compte_bancaire_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("releve.consulter")),
    db: Session = Depends(get_db),
) -> list[LigneEcritureLecture]:
    service = ServiceTresorerie(db, contexte.entreprise_id)
    return [
        LigneEcritureLecture.model_validate(l)
        for l in service.lister_ecritures_candidates(compte_bancaire_id)
    ]


# --- Relevés bancaires -------------------------------------------------------


@router.post(
    "/entreprises/{entreprise_id}/comptes-bancaires/{compte_bancaire_id}/releves",
    response_model=ReleveAvecLignes,
    status_code=status.HTTP_201_CREATED,
)
def creer_releve(
    entreprise_id: uuid.UUID,
    compte_bancaire_id: uuid.UUID,
    donnees: ReleveCreation,
    contexte: ContexteEntreprise = Depends(exiger_permission("releve.creer")),
    db: Session = Depends(get_db),
) -> ReleveAvecLignes:
    service = ServiceTresorerie(db, contexte.entreprise_id)
    releve = service.creer_releve(
        auteur_id=contexte.utilisateur_id,
        compte_bancaire_id=compte_bancaire_id,
        date_debut=donnees.date_debut,
        date_fin=donnees.date_fin,
        solde_debut=donnees.solde_debut,
        solde_fin=donnees.solde_fin,
        reference=donnees.reference,
        lignes=_lignes_saisies(donnees.lignes),
    )
    db.commit()
    return _releve_avec_lignes(releve, service.lister_lignes(releve.id))


@router.get(
    "/entreprises/{entreprise_id}/comptes-bancaires/{compte_bancaire_id}/releves",
    response_model=list[ReleveLecture],
)
def lister_releves(
    entreprise_id: uuid.UUID,
    compte_bancaire_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("releve.consulter")),
    db: Session = Depends(get_db),
) -> list[ReleveLecture]:
    service = ServiceTresorerie(db, contexte.entreprise_id)
    return [ReleveLecture.model_validate(r) for r in service.lister_releves(compte_bancaire_id)]


@router.get(
    "/entreprises/{entreprise_id}/releves/{releve_id}",
    response_model=ReleveAvecLignes,
)
def lire_releve(
    entreprise_id: uuid.UUID,
    releve_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("releve.consulter")),
    db: Session = Depends(get_db),
) -> ReleveAvecLignes:
    service = ServiceTresorerie(db, contexte.entreprise_id)
    releve = service.obtenir_releve(releve_id)
    return _releve_avec_lignes(releve, service.lister_lignes(releve_id))


@router.patch(
    "/entreprises/{entreprise_id}/releves/{releve_id}",
    response_model=ReleveAvecLignes,
)
def modifier_releve(
    entreprise_id: uuid.UUID,
    releve_id: uuid.UUID,
    donnees: ReleveMiseAJour,
    contexte: ContexteEntreprise = Depends(exiger_permission("releve.modifier")),
    db: Session = Depends(get_db),
) -> ReleveAvecLignes:
    service = ServiceTresorerie(db, contexte.entreprise_id)
    releve = service.modifier_releve(
        releve_id,
        auteur_id=contexte.utilisateur_id,
        solde_debut=donnees.solde_debut,
        solde_fin=donnees.solde_fin,
        reference=donnees.reference,
        lignes=_lignes_saisies(donnees.lignes) if donnees.lignes is not None else None,
    )
    db.commit()
    return _releve_avec_lignes(releve, service.lister_lignes(releve.id))


@router.post(
    "/entreprises/{entreprise_id}/releves/{releve_id}/supprimer",
    status_code=status.HTTP_204_NO_CONTENT,
)
def supprimer_releve(
    entreprise_id: uuid.UUID,
    releve_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("releve.supprimer")),
    db: Session = Depends(get_db),
) -> None:
    service = ServiceTresorerie(db, contexte.entreprise_id)
    service.supprimer_releve(releve_id, auteur_id=contexte.utilisateur_id)
    db.commit()


# --- Rapprochement -----------------------------------------------------------


@router.post(
    "/entreprises/{entreprise_id}/comptes-bancaires/{compte_bancaire_id}/rapprocher",
    response_model=RapprochementReponse,
    status_code=status.HTTP_201_CREATED,
)
def rapprocher(
    entreprise_id: uuid.UUID,
    compte_bancaire_id: uuid.UUID,
    donnees: RapprochementDemande,
    contexte: ContexteEntreprise = Depends(exiger_permission("rapprochement.creer")),
    db: Session = Depends(get_db),
) -> RapprochementReponse:
    service = ServiceTresorerie(db, contexte.entreprise_id)
    code = service.rapprocher(
        auteur_id=contexte.utilisateur_id,
        compte_bancaire_id=compte_bancaire_id,
        ligne_releve_ids=donnees.ligne_releve_ids,
        ligne_ecriture_ids=donnees.ligne_ecriture_ids,
    )
    db.commit()
    return RapprochementReponse(code_lettrage=code)


@router.post(
    "/entreprises/{entreprise_id}/rapprochements/annuler",
    status_code=status.HTTP_204_NO_CONTENT,
)
def annuler_rapprochement(
    entreprise_id: uuid.UUID,
    donnees: AnnulationRapprochementDemande,
    contexte: ContexteEntreprise = Depends(exiger_permission("rapprochement.annuler")),
    db: Session = Depends(get_db),
) -> None:
    service = ServiceTresorerie(db, contexte.entreprise_id)
    service.annuler_rapprochement(donnees.code_lettrage, auteur_id=contexte.utilisateur_id)
    db.commit()