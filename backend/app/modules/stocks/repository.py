"""Accès aux données du module stocks.

Quatre repositories entreprise-scopés. `RepositoryLotsEntreeStock.lister_lots_disponibles`
est le seul un peu particulier : il trie par `date_entree` croissante
(puis `cree_le` pour départager deux lots de la même date) — c'est cet
ordre qui matérialise le FIFO côté service (voir `ServiceStocks._consommer_fifo`).
"""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.stocks.models import (
    Article,
    InventairePhysique,
    LigneConsommationLot,
    LotEntreeStock,
    MouvementStock,
)
from app.shared.repository import RepositoryEntreprise


class RepositoryArticles(RepositoryEntreprise[Article]):
    modele = Article

    def obtenir_par_code(self, code: str) -> Article | None:
        requete = select(Article).where(
            Article.entreprise_id == self.entreprise_id, Article.code == code
        )
        return self.db.scalars(requete).first()

    def lister(self, *, actifs_seulement: bool = True, limite: int = 1000, decalage: int = 0) -> list[Article]:
        requete = select(Article).where(Article.entreprise_id == self.entreprise_id)
        if actifs_seulement:
            requete = requete.where(Article.actif.is_(True))
        requete = requete.order_by(Article.code).limit(limite).offset(decalage)
        return list(self.db.scalars(requete).all())


class RepositoryMouvementsStock(RepositoryEntreprise[MouvementStock]):
    modele = MouvementStock

    def lister(
        self,
        *,
        article_id: uuid.UUID | None = None,
        type_mouvement: str | None = None,
        limite: int = 200,
        decalage: int = 0,
    ) -> list[MouvementStock]:
        requete = select(MouvementStock).where(MouvementStock.entreprise_id == self.entreprise_id)
        if article_id is not None:
            requete = requete.where(MouvementStock.article_id == article_id)
        if type_mouvement is not None:
            requete = requete.where(MouvementStock.type_mouvement == type_mouvement)
        requete = (
            requete.order_by(MouvementStock.date_mouvement.desc(), MouvementStock.cree_le.desc())
            .limit(limite)
            .offset(decalage)
        )
        return list(self.db.scalars(requete).all())


class RepositoryLotsEntreeStock(RepositoryEntreprise[LotEntreeStock]):
    modele = LotEntreeStock

    def lister_lots_disponibles(self, article_id: uuid.UUID) -> list[LotEntreeStock]:
        """Lots avec un reliquat non nul, du plus ancien au plus récent —
        c'est cet ordre qui fait le FIFO (voir la note de tête de fichier)."""
        requete = (
            select(LotEntreeStock)
            .where(
                LotEntreeStock.entreprise_id == self.entreprise_id,
                LotEntreeStock.article_id == article_id,
                LotEntreeStock.quantite_restante > 0,
            )
            .order_by(LotEntreeStock.date_entree.asc(), LotEntreeStock.id.asc())
        )
        return list(self.db.scalars(requete).all())

    def lister_pour_article(self, article_id: uuid.UUID) -> list[LotEntreeStock]:
        requete = (
            select(LotEntreeStock)
            .where(
                LotEntreeStock.entreprise_id == self.entreprise_id,
                LotEntreeStock.article_id == article_id,
            )
            .order_by(LotEntreeStock.date_entree.asc(), LotEntreeStock.id.asc())
        )
        return list(self.db.scalars(requete).all())


class RepositoryLignesConsommationLot(RepositoryEntreprise[LigneConsommationLot]):
    modele = LigneConsommationLot

    def lister_pour_mouvement(self, mouvement_sortie_id: uuid.UUID) -> list[LigneConsommationLot]:
        requete = select(LigneConsommationLot).where(
            LigneConsommationLot.entreprise_id == self.entreprise_id,
            LigneConsommationLot.mouvement_sortie_id == mouvement_sortie_id,
        )
        return list(self.db.scalars(requete).all())


class RepositoryInventairesPhysiques(RepositoryEntreprise[InventairePhysique]):
    modele = InventairePhysique

    def lister(
        self,
        *,
        article_id: uuid.UUID | None = None,
        exercice_id: uuid.UUID | None = None,
        limite: int = 500,
        decalage: int = 0,
    ) -> list[InventairePhysique]:
        requete = select(InventairePhysique).where(InventairePhysique.entreprise_id == self.entreprise_id)
        if article_id is not None:
            requete = requete.where(InventairePhysique.article_id == article_id)
        if exercice_id is not None:
            requete = requete.where(InventairePhysique.exercice_id == exercice_id)
        requete = requete.order_by(InventairePhysique.date_inventaire.desc()).limit(limite).offset(decalage)
        return list(self.db.scalars(requete).all())