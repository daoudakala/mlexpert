"""Routes HTTP du module dashboards.

Toutes les routes sont entreprise-scopées
(`/dashboards/entreprises/{entreprise_id}/...`), en lecture seule,
protégées par une unique permission `dashboard.consulter` — pas de
`creer`/`modifier`/`supprimer` : ce module ne persiste rien (voir
`repository.py`).
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import ContexteEntreprise, exiger_permission
from app.core.database import get_db
from app.modules.dashboards.export import exporter_etats_financiers
from app.modules.dashboards.schemas import (
    BilanLecture,
    CompteResultatDetailleLecture,
    CompteResultatSommaireLecture,
    LigneBalanceCompareeLecture,
    LigneBalanceLecture,
    LigneEcheanceLecture,
    LigneGrandLivreLecture,
    PrevisionTresorerieLecture,
    TableauComptabiliteLecture,
    TableauDirectionLecture,
    TrancheAgeeLecture,
)
from app.modules.dashboards.service import ServiceReporting
from app.core.exceptions import RessourceIntrouvable
from app.modules.entreprises.repository import RepositoryEntreprises
from app.modules.exercices.repository import RepositoryExercice

router = APIRouter(prefix="/dashboards", tags=["Tableaux de bord"])


@router.get(
    "/entreprises/{entreprise_id}/exercices/{exercice_id}/balance-generale",
    response_model=list[LigneBalanceLecture],
)
def lire_balance_generale(
    entreprise_id: uuid.UUID,
    exercice_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("dashboard.consulter")),
    db: Session = Depends(get_db),
) -> list[LigneBalanceLecture]:
    service = ServiceReporting(db, contexte.entreprise_id)
    return [LigneBalanceLecture.model_validate(l) for l in service.balance_generale(exercice_id)]


@router.get(
    "/entreprises/{entreprise_id}/exercices/{exercice_id}/balance-comparee-n1",
    response_model=list[LigneBalanceCompareeLecture],
)
def lire_balance_comparee_n1(
    entreprise_id: uuid.UUID,
    exercice_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("dashboard.consulter")),
    db: Session = Depends(get_db),
) -> list[LigneBalanceCompareeLecture]:
    service = ServiceReporting(db, contexte.entreprise_id)
    return [
        LigneBalanceCompareeLecture.model_validate(l) for l in service.balance_comparee_n1(exercice_id)
    ]


@router.get(
    "/entreprises/{entreprise_id}/exercices/{exercice_id}/comptes/{compte_id}/grand-livre",
    response_model=list[LigneGrandLivreLecture],
)
def lire_grand_livre(
    entreprise_id: uuid.UUID,
    exercice_id: uuid.UUID,
    compte_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("dashboard.consulter")),
    db: Session = Depends(get_db),
) -> list[LigneGrandLivreLecture]:
    service = ServiceReporting(db, contexte.entreprise_id)
    return [
        LigneGrandLivreLecture.model_validate(l)
        for l in service.grand_livre(compte_id, exercice_id)
    ]


@router.get(
    "/entreprises/{entreprise_id}/exercices/{exercice_id}/compte-resultat-sommaire",
    response_model=CompteResultatSommaireLecture,
)
def lire_compte_resultat_sommaire(
    entreprise_id: uuid.UUID,
    exercice_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("dashboard.consulter")),
    db: Session = Depends(get_db),
) -> CompteResultatSommaireLecture:
    service = ServiceReporting(db, contexte.entreprise_id)
    return CompteResultatSommaireLecture.model_validate(service.compte_resultat_sommaire(exercice_id))


@router.get(
    "/entreprises/{entreprise_id}/exercices/{exercice_id}/bilan",
    response_model=BilanLecture,
)
def lire_bilan(
    entreprise_id: uuid.UUID,
    exercice_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("dashboard.consulter")),
    db: Session = Depends(get_db),
) -> BilanLecture:
    service = ServiceReporting(db, contexte.entreprise_id)
    return BilanLecture.model_validate(service.bilan(exercice_id))


@router.get(
    "/entreprises/{entreprise_id}/exercices/{exercice_id}/compte-resultat-detaille",
    response_model=CompteResultatDetailleLecture,
)
def lire_compte_resultat_detaille(
    entreprise_id: uuid.UUID,
    exercice_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("dashboard.consulter")),
    db: Session = Depends(get_db),
) -> CompteResultatDetailleLecture:
    service = ServiceReporting(db, contexte.entreprise_id)
    return CompteResultatDetailleLecture.model_validate(service.compte_resultat_detaille(exercice_id))


@router.get("/entreprises/{entreprise_id}/exercices/{exercice_id}/etats-financiers/export")
def exporter_etats_financiers_route(
    entreprise_id: uuid.UUID,
    exercice_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("dashboard.consulter")),
    db: Session = Depends(get_db),
) -> Response:
    """Export Excel des états financiers (cahier, section 9) : un
    classeur à trois feuilles (Bilan, Compte de résultat, Comparaison
    N-N-1) — voir `dashboards/export.py`. Permission `dashboard.consulter`
    reprise telle quelle : qui peut consulter ces rapports à l'écran peut
    les exporter, pas de permission dédiée pour ce premier export."""
    service = ServiceReporting(db, contexte.entreprise_id)
    entreprise = RepositoryEntreprises(db).obtenir(contexte.entreprise_id)
    if entreprise is None:
        raise RessourceIntrouvable("Entreprise introuvable.")
    exercice = RepositoryExercice(db, contexte.entreprise_id).obtenir(exercice_id)
    if exercice is None:
        raise RessourceIntrouvable("Exercice introuvable pour cette entreprise.")

    contenu = exporter_etats_financiers(
        entreprise=entreprise,
        exercice=exercice,
        bilan=service.bilan(exercice_id),
        resultat=service.compte_resultat_detaille(exercice_id),
        comparaison=service.balance_comparee_n1(exercice_id),
    )
    nom_fichier = f"etats_financiers_{exercice.date_debut:%Y}_{exercice.date_fin:%Y}.xlsx"
    return Response(
        content=contenu,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nom_fichier}"'},
    )


@router.get(
    "/entreprises/{entreprise_id}/echeancier/{type_tiers}",
    response_model=list[LigneEcheanceLecture],
)
def lire_echeancier(
    entreprise_id: uuid.UUID,
    type_tiers: Literal["client", "fournisseur"],
    contexte: ContexteEntreprise = Depends(exiger_permission("dashboard.consulter")),
    db: Session = Depends(get_db),
) -> list[LigneEcheanceLecture]:
    service = ServiceReporting(db, contexte.entreprise_id)
    return [LigneEcheanceLecture.model_validate(l) for l in service.echeancier(type_tiers)]


@router.get(
    "/entreprises/{entreprise_id}/balance-agee/{type_tiers}",
    response_model=list[TrancheAgeeLecture],
)
def lire_balance_agee(
    entreprise_id: uuid.UUID,
    type_tiers: Literal["client", "fournisseur"],
    contexte: ContexteEntreprise = Depends(exiger_permission("dashboard.consulter")),
    db: Session = Depends(get_db),
) -> list[TrancheAgeeLecture]:
    service = ServiceReporting(db, contexte.entreprise_id)
    return [TrancheAgeeLecture.model_validate(t) for t in service.balance_agee(type_tiers)]


@router.get(
    "/entreprises/{entreprise_id}/prevision-tresorerie",
    response_model=PrevisionTresorerieLecture,
)
def lire_prevision_tresorerie(
    entreprise_id: uuid.UUID,
    horizon_jours: int = 90,
    contexte: ContexteEntreprise = Depends(exiger_permission("dashboard.consulter")),
    db: Session = Depends(get_db),
) -> PrevisionTresorerieLecture:
    service = ServiceReporting(db, contexte.entreprise_id)
    return PrevisionTresorerieLecture.model_validate(
        service.prevision_tresorerie(horizon_jours=horizon_jours)
    )


@router.get(
    "/entreprises/{entreprise_id}/tableau-direction",
    response_model=TableauDirectionLecture,
)
def lire_tableau_direction(
    entreprise_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("dashboard.consulter")),
    db: Session = Depends(get_db),
) -> TableauDirectionLecture:
    service = ServiceReporting(db, contexte.entreprise_id)
    return TableauDirectionLecture.model_validate(service.tableau_direction())


@router.get(
    "/entreprises/{entreprise_id}/tableau-comptabilite",
    response_model=TableauComptabiliteLecture,
)
def lire_tableau_comptabilite(
    entreprise_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("dashboard.consulter")),
    db: Session = Depends(get_db),
) -> TableauComptabiliteLecture:
    service = ServiceReporting(db, contexte.entreprise_id)
    return TableauComptabiliteLecture.model_validate(service.tableau_comptabilite())