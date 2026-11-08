"""Accès aux données du module portail_client.

Repository entreprise-scopé classique — rien de particulier.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.portail_client.models import CommentaireDemande, DemandeDocument
from app.shared.repository import RepositoryEntreprise


class RepositoryDemandesDocuments(RepositoryEntreprise[DemandeDocument]):
    modele = DemandeDocument

    def lister(
        self,
        *,
        demandeur_id: uuid.UUID | None = None,
        statut: str | None = None,
        limite: int = 200,
        decalage: int = 0,
    ) -> list[DemandeDocument]:
        requete = select(DemandeDocument).where(DemandeDocument.entreprise_id == self.entreprise_id)
        if demandeur_id is not None:
            requete = requete.where(DemandeDocument.demandeur_id == demandeur_id)
        if statut is not None:
            requete = requete.where(DemandeDocument.statut == statut)
        requete = requete.order_by(DemandeDocument.cree_le.desc()).limit(limite).offset(decalage)
        return list(self.db.scalars(requete).all())


class RepositoryCommentairesDemandes(RepositoryEntreprise[CommentaireDemande]):
    modele = CommentaireDemande

    def lister_pour_demande(self, demande_id: uuid.UUID) -> list[CommentaireDemande]:
        requete = (
            select(CommentaireDemande)
            .where(
                CommentaireDemande.entreprise_id == self.entreprise_id,
                CommentaireDemande.demande_id == demande_id,
            )
            .order_by(CommentaireDemande.cree_le.asc())
        )
        return list(self.db.scalars(requete).all())