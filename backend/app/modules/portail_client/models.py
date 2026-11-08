"""Modèle du module portail_client.

Une seule table, `DemandeDocument` : un utilisateur client demande une
pièce au cabinet (ex. "mon dernier bilan"), le cabinet la traite en la
liant à un `Document` déjà déposé (module `documents`) ou la refuse avec
un motif. `document_id` est nullable et `ondelete=SET NULL` : une demande
garde son historique même si le document lié est supprimé plus tard.

Pas de nouvelle notion d'utilisateur "client" : c'est un `Utilisateur`
comme un autre, distingué uniquement par son `Affectation` (rôle limité)
sur l'entreprise — voir la note de tête de fichier de `service.py` pour
ce que ça implique côté permissions.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base import Base
from app.shared.mixins import EntrepriseMixin, HorodatageMixin, IdentifiantMixin


class StatutDemandeDocument(StrEnum):
    EN_ATTENTE = "en_attente"
    TRAITEE = "traitee"
    REFUSEE = "refusee"


class DemandeDocument(IdentifiantMixin, HorodatageMixin, EntrepriseMixin, Base):
    __tablename__ = "demandes_documents"
    __table_args__ = (
        CheckConstraint(
            "statut IN ('en_attente', 'traitee', 'refusee')", name="statut_valide"
        ),
    )

    libelle: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    statut: Mapped[str] = mapped_column(
        String(20), nullable=False, default=StatutDemandeDocument.EN_ATTENTE.value
    )
    # Motif de refus, ou commentaire du cabinet à la clôture de la demande.
    reponse: Mapped[str | None] = mapped_column(String(500), nullable=True)

    demandeur_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    traitee_par_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=True
    )
    traitee_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CommentaireDemande(IdentifiantMixin, HorodatageMixin, EntrepriseMixin, Base):
    """Fil de commentaires rattaché à une `DemandeDocument` — la
    « messagerie ou commentaires contextualisés » du cahier des charges
    (section 20). Pas d'édition ni de suppression : un message envoyé est
    définitif, comme une entrée du journal d'activité.

    `demande_id` est en `ondelete=CASCADE` (contrairement à `document_id`
    sur `DemandeDocument`, en `SET NULL`) : un commentaire n'a aucun sens
    sans la demande qu'il commente, alors qu'une demande garde son
    historique même si le document lié est supprimé.
    """

    __tablename__ = "commentaires_demandes"

    demande_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("demandes_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    auteur_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=False
    )
    message: Mapped[str] = mapped_column(String(2000), nullable=False)