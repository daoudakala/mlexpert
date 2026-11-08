"""Accès aux données du module documents.

Repository entreprise-scopé classique — rien de particulier, comme dans
`tresorerie`/`immobilisations`.
"""

import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.modules.documents.models import Document
from app.shared.repository import RepositoryEntreprise


class RepositoryDocuments(RepositoryEntreprise[Document]):
    modele = Document

    def lister(
        self,
        *,
        categorie: str | None = None,
        exercice_id: uuid.UUID | None = None,
        dossier_permanent_seulement: bool = False,
        visible_client_seulement: bool = False,
        ecriture_id: uuid.UUID | None = None,
        tiers_id_scope: uuid.UUID | None = None,
        limite: int = 200,
        decalage: int = 0,
    ) -> list[Document]:
        """`tiers_id_scope` (Étape 6) : utilisé par `ServicePortailClient`
        pour un compte portail rattaché à un `Tiers` précis — ne retourne
        alors que les documents sans restriction de client
        (`tiers_id IS NULL`, visibles par tous) OU restreints à CE tiers.
        `None` (valeur par défaut, utilisée par le module `documents` côté
        cabinet) ne filtre rien de plus : comportement inchangé."""
        requete = select(Document).where(Document.entreprise_id == self.entreprise_id)
        if categorie is not None:
            requete = requete.where(Document.categorie == categorie)
        if dossier_permanent_seulement:
            requete = requete.where(Document.exercice_id.is_(None))
        elif exercice_id is not None:
            requete = requete.where(Document.exercice_id == exercice_id)
        if visible_client_seulement:
            requete = requete.where(Document.visible_client.is_(True))
        if ecriture_id is not None:
            requete = requete.where(Document.ecriture_id == ecriture_id)
        if tiers_id_scope is not None:
            requete = requete.where(
                or_(Document.tiers_id.is_(None), Document.tiers_id == tiers_id_scope)
            )
        requete = requete.order_by(Document.cree_le.desc()).limit(limite).offset(decalage)
        return list(self.db.scalars(requete).all())

    def lister_pour_ecriture(self, ecriture_id: uuid.UUID) -> list[Document]:
        """Pièces justificatives rattachées à une écriture donnée — utilisé
        par la page de détail d'une écriture côté frontend."""
        requete = (
            select(Document)
            .where(Document.entreprise_id == self.entreprise_id, Document.ecriture_id == ecriture_id)
            .order_by(Document.cree_le.desc())
        )
        return list(self.db.scalars(requete).all())