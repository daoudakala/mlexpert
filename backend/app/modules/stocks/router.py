"""Routes HTTP du module stocks.

Toutes les routes sont entreprise-scopées (`/stocks/entreprises/{entreprise_id}/...`),
protégées par les permissions `article.*`/`mouvement_stock.*`
(`exiger_permission`), sur le modèle de `paie`/`immobilisations`.

Deux routes de création de mouvement distinctes (`/mouvements/entrees` et
`/mouvements/sorties`), reflet des deux schémas de `schemas.py` — le coût
d'une sortie n'est jamais dans le corps de la requête, il est calculé par
le service.
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import ContexteEntreprise, exiger_permission
from app.core.database import get_db
from app.modules.comptabilite.schemas import EcritureLecture
from app.modules.stocks.schemas import (
    ArticleCreation,
    ArticleLecture,
    ArticleMiseAJour,
    GenerationEcritureMouvementDemande,
    InventairePhysiqueCreation,
    InventairePhysiqueLecture,
    LigneConsommationLotLecture,
    MouvementEntreeCreation,
    MouvementSortieCreation,
    MouvementStockLecture,
)
from app.modules.stocks.service import MouvementEntreeCreation as MouvementEntreeCreationDonnees
from app.modules.stocks.service import MouvementSortieCreation as MouvementSortieCreationDonnees
from app.modules.stocks.service import ServiceStocks

router = APIRouter(prefix="/stocks", tags=["Stocks"])


# --- Articles ------------------------------------------------------------------


@router.post(
    "/entreprises/{entreprise_id}/articles",
    response_model=ArticleLecture,
    status_code=status.HTTP_201_CREATED,
)
def creer_article(
    entreprise_id: uuid.UUID,
    donnees: ArticleCreation,
    contexte: ContexteEntreprise = Depends(exiger_permission("article.creer")),
    db: Session = Depends(get_db),
) -> ArticleLecture:
    service = ServiceStocks(db, contexte.entreprise_id)
    article = service.creer_article(
        code=donnees.code,
        libelle=donnees.libelle,
        unite=donnees.unite,
        methode_valorisation=donnees.methode_valorisation,
        compte_stock_id=donnees.compte_stock_id,
        auteur_id=contexte.utilisateur_id,
    )
    db.commit()
    return ArticleLecture.model_validate(article)


@router.get("/entreprises/{entreprise_id}/articles", response_model=list[ArticleLecture])
def lister_articles(
    entreprise_id: uuid.UUID,
    actifs_seulement: bool = True,
    contexte: ContexteEntreprise = Depends(exiger_permission("article.consulter")),
    db: Session = Depends(get_db),
) -> list[ArticleLecture]:
    service = ServiceStocks(db, contexte.entreprise_id)
    return [
        ArticleLecture.model_validate(a)
        for a in service.lister_articles(actifs_seulement=actifs_seulement)
    ]


@router.get("/entreprises/{entreprise_id}/articles/{article_id}", response_model=ArticleLecture)
def lire_article(
    entreprise_id: uuid.UUID,
    article_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("article.consulter")),
    db: Session = Depends(get_db),
) -> ArticleLecture:
    service = ServiceStocks(db, contexte.entreprise_id)
    return ArticleLecture.model_validate(service.obtenir_article(article_id))


@router.patch("/entreprises/{entreprise_id}/articles/{article_id}", response_model=ArticleLecture)
def modifier_article(
    entreprise_id: uuid.UUID,
    article_id: uuid.UUID,
    donnees: ArticleMiseAJour,
    contexte: ContexteEntreprise = Depends(exiger_permission("article.modifier")),
    db: Session = Depends(get_db),
) -> ArticleLecture:
    service = ServiceStocks(db, contexte.entreprise_id)
    article = service.modifier_article(
        article_id, auteur_id=contexte.utilisateur_id, libelle=donnees.libelle, unite=donnees.unite
    )
    db.commit()
    return ArticleLecture.model_validate(article)


@router.post(
    "/entreprises/{entreprise_id}/articles/{article_id}/desactiver", response_model=ArticleLecture
)
def desactiver_article(
    entreprise_id: uuid.UUID,
    article_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("article.archiver")),
    db: Session = Depends(get_db),
) -> ArticleLecture:
    service = ServiceStocks(db, contexte.entreprise_id)
    article = service.desactiver_article(article_id, auteur_id=contexte.utilisateur_id)
    db.commit()
    return ArticleLecture.model_validate(article)


@router.post(
    "/entreprises/{entreprise_id}/articles/{article_id}/reactiver", response_model=ArticleLecture
)
def reactiver_article(
    entreprise_id: uuid.UUID,
    article_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("article.archiver")),
    db: Session = Depends(get_db),
) -> ArticleLecture:
    service = ServiceStocks(db, contexte.entreprise_id)
    article = service.reactiver_article(article_id, auteur_id=contexte.utilisateur_id)
    db.commit()
    return ArticleLecture.model_validate(article)


# --- Mouvements ------------------------------------------------------------------


@router.post(
    "/entreprises/{entreprise_id}/mouvements/entrees",
    response_model=MouvementStockLecture,
    status_code=status.HTTP_201_CREATED,
)
def creer_mouvement_entree(
    entreprise_id: uuid.UUID,
    donnees: MouvementEntreeCreation,
    contexte: ContexteEntreprise = Depends(exiger_permission("mouvement_stock.creer")),
    db: Session = Depends(get_db),
) -> MouvementStockLecture:
    service = ServiceStocks(db, contexte.entreprise_id)
    mouvement = service.creer_mouvement_entree(
        MouvementEntreeCreationDonnees(
            article_id=donnees.article_id,
            date_mouvement=donnees.date_mouvement,
            quantite=donnees.quantite,
            cout_unitaire=donnees.cout_unitaire,
            reference=donnees.reference,
            libelle=donnees.libelle,
            tiers_id=donnees.tiers_id,
        ),
        auteur_id=contexte.utilisateur_id,
    )
    db.commit()
    return MouvementStockLecture.model_validate(mouvement)


@router.post(
    "/entreprises/{entreprise_id}/mouvements/sorties",
    response_model=MouvementStockLecture,
    status_code=status.HTTP_201_CREATED,
)
def creer_mouvement_sortie(
    entreprise_id: uuid.UUID,
    donnees: MouvementSortieCreation,
    contexte: ContexteEntreprise = Depends(exiger_permission("mouvement_stock.creer")),
    db: Session = Depends(get_db),
) -> MouvementStockLecture:
    service = ServiceStocks(db, contexte.entreprise_id)
    mouvement = service.creer_mouvement_sortie(
        MouvementSortieCreationDonnees(
            article_id=donnees.article_id,
            date_mouvement=donnees.date_mouvement,
            quantite=donnees.quantite,
            reference=donnees.reference,
            libelle=donnees.libelle,
            tiers_id=donnees.tiers_id,
        ),
        auteur_id=contexte.utilisateur_id,
    )
    db.commit()
    return MouvementStockLecture.model_validate(mouvement)


@router.get("/entreprises/{entreprise_id}/mouvements", response_model=list[MouvementStockLecture])
def lister_mouvements(
    entreprise_id: uuid.UUID,
    article_id: uuid.UUID | None = None,
    type_mouvement: str | None = None,
    contexte: ContexteEntreprise = Depends(exiger_permission("mouvement_stock.consulter")),
    db: Session = Depends(get_db),
) -> list[MouvementStockLecture]:
    service = ServiceStocks(db, contexte.entreprise_id)
    return [
        MouvementStockLecture.model_validate(m)
        for m in service.lister_mouvements(article_id=article_id, type_mouvement=type_mouvement)
    ]


@router.get(
    "/entreprises/{entreprise_id}/mouvements/{mouvement_id}", response_model=MouvementStockLecture
)
def lire_mouvement(
    entreprise_id: uuid.UUID,
    mouvement_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("mouvement_stock.consulter")),
    db: Session = Depends(get_db),
) -> MouvementStockLecture:
    service = ServiceStocks(db, contexte.entreprise_id)
    return MouvementStockLecture.model_validate(service.obtenir_mouvement(mouvement_id))


@router.get(
    "/entreprises/{entreprise_id}/mouvements/{mouvement_id}/lignes-consommation",
    response_model=list[LigneConsommationLotLecture],
)
def lister_lignes_consommation(
    entreprise_id: uuid.UUID,
    mouvement_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("mouvement_stock.consulter")),
    db: Session = Depends(get_db),
) -> list[LigneConsommationLotLecture]:
    service = ServiceStocks(db, contexte.entreprise_id)
    return [
        LigneConsommationLotLecture.model_validate(l)
        for l in service.lister_lignes_consommation(mouvement_id)
    ]


@router.post(
    "/entreprises/{entreprise_id}/mouvements/{mouvement_id}/generer-ecriture",
    response_model=EcritureLecture,
    status_code=status.HTTP_201_CREATED,
)
def generer_ecriture_mouvement(
    entreprise_id: uuid.UUID,
    mouvement_id: uuid.UUID,
    donnees: GenerationEcritureMouvementDemande,
    contexte: ContexteEntreprise = Depends(exiger_permission("mouvement_stock.creer")),
    db: Session = Depends(get_db),
) -> EcritureLecture:
    service = ServiceStocks(db, contexte.entreprise_id)
    ecriture = service.generer_ecriture_mouvement(
        mouvement_id,
        journal_id=donnees.journal_id,
        compte_contrepartie_id=donnees.compte_contrepartie_id,
        auteur_id=contexte.utilisateur_id,
    )
    db.commit()
    return EcritureLecture.model_validate(ecriture)



# --- Inventaires physiques -------------------------------------------------------


@router.post(
    "/entreprises/{entreprise_id}/inventaires-physiques",
    response_model=InventairePhysiqueLecture,
    status_code=status.HTTP_201_CREATED,
)
def creer_inventaire_physique(
    entreprise_id: uuid.UUID,
    donnees: InventairePhysiqueCreation,
    contexte: ContexteEntreprise = Depends(exiger_permission("inventaire_physique.creer")),
    db: Session = Depends(get_db),
) -> InventairePhysiqueLecture:
    service = ServiceStocks(db, contexte.entreprise_id)
    inventaire = service.creer_inventaire_physique(
        article_id=donnees.article_id,
        exercice_id=donnees.exercice_id,
        date_inventaire=donnees.date_inventaire,
        quantite_physique=donnees.quantite_physique,
        journal_id=donnees.journal_id,
        compte_contrepartie_id=donnees.compte_contrepartie_id,
        auteur_id=contexte.utilisateur_id,
    )
    db.commit()
    return InventairePhysiqueLecture.model_validate(inventaire)


@router.get(
    "/entreprises/{entreprise_id}/inventaires-physiques",
    response_model=list[InventairePhysiqueLecture],
)
def lister_inventaires_physiques(
    entreprise_id: uuid.UUID,
    article_id: uuid.UUID | None = None,
    exercice_id: uuid.UUID | None = None,
    contexte: ContexteEntreprise = Depends(exiger_permission("inventaire_physique.consulter")),
    db: Session = Depends(get_db),
) -> list[InventairePhysiqueLecture]:
    service = ServiceStocks(db, contexte.entreprise_id)
    return [
        InventairePhysiqueLecture.model_validate(i)
        for i in service.lister_inventaires_physiques(article_id=article_id, exercice_id=exercice_id)
    ]


@router.get(
    "/entreprises/{entreprise_id}/inventaires-physiques/{inventaire_id}",
    response_model=InventairePhysiqueLecture,
)
def lire_inventaire_physique(
    entreprise_id: uuid.UUID,
    inventaire_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("inventaire_physique.consulter")),
    db: Session = Depends(get_db),
) -> InventairePhysiqueLecture:
    service = ServiceStocks(db, contexte.entreprise_id)
    return InventairePhysiqueLecture.model_validate(service.obtenir_inventaire_physique(inventaire_id))