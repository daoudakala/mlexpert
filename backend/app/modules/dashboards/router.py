"""Routes HTTP du module dashboards.

Toutes les routes sont entreprise-scopées
(`/dashboards/entreprises/{entreprise_id}/...`), en lecture seule,
protégées par une unique permission `dashboard.consulter` — pas de
`creer`/`modifier`/`supprimer` : ce module ne persiste rien (voir
`repository.py`).
"""

import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import ContexteEntreprise, exiger_permission
from app.core.database import get_db
from app.modules.dashboards.export import exporter_etats_financiers
from app.modules.dashboards.balance import ServiceBalance, exporter_balance
from app.modules.dashboards.grand_livre import ServiceGrandLivre, exporter_grand_livre
from app.modules.dashboards.schemas import (
    GrandLivreGeneralLecture,
    BalanceDetailleeLecture,
    BilanLecture,
    CompteResultatDetailleLecture,
    CompteResultatSommaireLecture,
    LigneBalanceCompareeLecture,
    LigneBalanceLecture,
    LigneEcheanceLecture,
    LigneGrandLivreLecture,
    PrevisionTresorerieLecture,
    TableauBordLecture,
    TableauComptabiliteLecture,
    TableauDirectionLecture,
    TrancheAgeeLecture,
)
from app.modules.dashboards.service import ServiceReporting
from app.modules.dashboards.tableau_bord import ServiceTableauBord
from app.core.exceptions import RessourceIntrouvable, ValidationMetier
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

@router.get(
    "/entreprises/{entreprise_id}/tableau-bord",
    response_model=TableauBordLecture,
)
def lire_tableau_bord(
    entreprise_id: uuid.UUID,
    exercice_id: uuid.UUID | None = None,
    date_debut: date | None = None,
    date_fin: date | None = None,
    contexte: ContexteEntreprise = Depends(exiger_permission("dashboard.consulter")),
    db: Session = Depends(get_db),
) -> TableauBordLecture:
    """Page d'accueil : CA, marge commerciale, valeur ajoutée, EBE (avec
    comparaison N-1), trésorerie, CAF, actif/passif circulant, FR/BFR et
    bilan fonctionnel — voir `dashboards/tableau_bord.py`. Sans
    `exercice_id`, l'exercice courant ; sans dates, l'exercice entier."""
    service = ServiceTableauBord(db, contexte.entreprise_id)
    return TableauBordLecture.model_validate(
        service.tableau_bord(exercice_id=exercice_id, date_debut=date_debut, date_fin=date_fin)
    )


def _lire_classes(classes: str | None) -> set[int] | None:
    """`?classes=1,2,5` -> {1, 2, 5} ; absent ou vide = toutes les classes."""
    if not classes:
        return None
    try:
        return {int(c) for c in classes.split(",") if c.strip()}
    except ValueError:
        raise ValidationMetier("Le paramètre 'classes' doit être une liste de chiffres séparés par des virgules.")


@router.get(
    "/entreprises/{entreprise_id}/exercices/{exercice_id}/balance-detaillee",
    response_model=BalanceDetailleeLecture,
)
def lire_balance_detaillee(
    entreprise_id: uuid.UUID,
    exercice_id: uuid.UUID,
    date_debut: date | None = None,
    date_fin: date | None = None,
    classes: str | None = None,
    contexte: ContexteEntreprise = Depends(exiger_permission("dashboard.consulter")),
    db: Session = Depends(get_db),
) -> BalanceDetailleeLecture:
    """Balance générale à colonnes (à-nouveaux, mouvements, solde) avec
    totaux bilan / gestion / balance — voir `dashboards/balance.py`."""
    service = ServiceBalance(db, contexte.entreprise_id)
    return BalanceDetailleeLecture.model_validate(
        service.balance_detaillee(
            exercice_id, date_debut=date_debut, date_fin=date_fin, classes=_lire_classes(classes)
        )
    )


@router.get("/entreprises/{entreprise_id}/exercices/{exercice_id}/balance-detaillee/export")
def exporter_balance_detaillee(
    entreprise_id: uuid.UUID,
    exercice_id: uuid.UUID,
    date_debut: date | None = None,
    date_fin: date | None = None,
    classes: str | None = None,
    contexte: ContexteEntreprise = Depends(exiger_permission("dashboard.consulter")),
    db: Session = Depends(get_db),
) -> Response:
    """Export Excel de la balance, avec les mêmes filtres que l'écran."""
    entreprise = RepositoryEntreprises(db).obtenir(contexte.entreprise_id)
    if entreprise is None:
        raise RessourceIntrouvable("Entreprise introuvable.")
    exercice = RepositoryExercice(db, contexte.entreprise_id).obtenir(exercice_id)
    if exercice is None:
        raise RessourceIntrouvable("Exercice introuvable pour cette entreprise.")
    balance = ServiceBalance(db, contexte.entreprise_id).balance_detaillee(
        exercice_id, date_debut=date_debut, date_fin=date_fin, classes=_lire_classes(classes)
    )
    contenu = exporter_balance(entreprise=entreprise, exercice=exercice, balance=balance)
    nom_fichier = f"balance_generale_{balance.date_fin:%Y%m%d}.xlsx"
    return Response(
        content=contenu,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nom_fichier}"'},
    )


@router.get(
    "/entreprises/{entreprise_id}/exercices/{exercice_id}/grand-livre-general",
    response_model=GrandLivreGeneralLecture,
)
def lire_grand_livre_general(
    entreprise_id: uuid.UUID,
    exercice_id: uuid.UUID,
    date_debut: date | None = None,
    date_fin: date | None = None,
    compte_debut: str | None = None,
    compte_fin: str | None = None,
    journal_id: uuid.UUID | None = None,
    contexte: ContexteEntreprise = Depends(exiger_permission("dashboard.consulter")),
    db: Session = Depends(get_db),
) -> GrandLivreGeneralLecture:
    """Grand livre de tous les comptes (ou d'une plage de comptes), avec
    solde cumulé — voir `dashboards/grand_livre.py`."""
    service = ServiceGrandLivre(db, contexte.entreprise_id)
    return GrandLivreGeneralLecture.model_validate(
        service.grand_livre_general(
            exercice_id,
            date_debut=date_debut,
            date_fin=date_fin,
            compte_debut=compte_debut,
            compte_fin=compte_fin,
            journal_id=journal_id,
        )
    )


@router.get("/entreprises/{entreprise_id}/exercices/{exercice_id}/grand-livre-general/export")
def exporter_grand_livre_general(
    entreprise_id: uuid.UUID,
    exercice_id: uuid.UUID,
    date_debut: date | None = None,
    date_fin: date | None = None,
    compte_debut: str | None = None,
    compte_fin: str | None = None,
    journal_id: uuid.UUID | None = None,
    contexte: ContexteEntreprise = Depends(exiger_permission("dashboard.consulter")),
    db: Session = Depends(get_db),
) -> Response:
    """Export Excel du grand livre, avec les mêmes filtres que l'écran."""
    entreprise = RepositoryEntreprises(db).obtenir(contexte.entreprise_id)
    if entreprise is None:
        raise RessourceIntrouvable("Entreprise introuvable.")
    exercice = RepositoryExercice(db, contexte.entreprise_id).obtenir(exercice_id)
    if exercice is None:
        raise RessourceIntrouvable("Exercice introuvable pour cette entreprise.")
    grand_livre = ServiceGrandLivre(db, contexte.entreprise_id).grand_livre_general(
        exercice_id,
        date_debut=date_debut,
        date_fin=date_fin,
        compte_debut=compte_debut,
        compte_fin=compte_fin,
        journal_id=journal_id,
    )
    contenu = exporter_grand_livre(entreprise=entreprise, exercice=exercice, grand_livre=grand_livre)
    nom_fichier = f"grand_livre_{grand_livre.date_fin:%Y%m%d}.xlsx"
    return Response(
        content=contenu,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nom_fichier}"'},
    )