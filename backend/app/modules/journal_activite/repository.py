"""Accès aux données du module journal_activite.

Pas de méthode de modification ou de suppression : ce dépôt n'expose que
`ajouter` (hérité de `Repository`) et des lectures. C'est la table elle-même
qui matérialise la traçabilité — rien ne doit pouvoir l'altérer après coup.
"""

import uuid
from datetime import datetime

from sqlalchemy import select

from app.modules.journal_activite.models import JournalActivite
from app.shared.repository import Repository


class RepositoryJournalActivite(Repository[JournalActivite]):
    modele = JournalActivite

    def rechercher(
        self,
        *,
        entreprise_id: uuid.UUID | None = None,
        utilisateur_id: uuid.UUID | None = None,
        module: str | None = None,
        type_action: str | None = None,
        type_objet: str | None = None,
        objet_id: uuid.UUID | None = None,
        depuis: datetime | None = None,
        jusqu_a: datetime | None = None,
        limite: int = 100,
        decalage: int = 0,
    ) -> list[JournalActivite]:
        requete = select(JournalActivite)

        if entreprise_id is not None:
            requete = requete.where(JournalActivite.entreprise_id == entreprise_id)
        if utilisateur_id is not None:
            requete = requete.where(JournalActivite.utilisateur_id == utilisateur_id)
        if module is not None:
            requete = requete.where(JournalActivite.module == module)
        if type_action is not None:
            requete = requete.where(JournalActivite.type_action == type_action)
        if type_objet is not None:
            requete = requete.where(JournalActivite.type_objet == type_objet)
        if objet_id is not None:
            requete = requete.where(JournalActivite.objet_id == objet_id)
        if depuis is not None:
            requete = requete.where(JournalActivite.survenu_le >= depuis)
        if jusqu_a is not None:
            requete = requete.where(JournalActivite.survenu_le <= jusqu_a)

        requete = (
            requete.order_by(JournalActivite.survenu_le.desc()).limit(limite).offset(decalage)
        )
        return list(self.db.scalars(requete).all())

    def lister_pour_objet(self, type_objet: str, objet_id: uuid.UUID) -> list[JournalActivite]:
        """L'historique complet d'un objet précis (ex. un exercice), du plus
        récent au plus ancien — utile pour un écran de détail."""
        requete = (
            select(JournalActivite)
            .where(
                JournalActivite.type_objet == type_objet,
                JournalActivite.objet_id == objet_id,
            )
            .order_by(JournalActivite.survenu_le.desc())
        )
        return list(self.db.scalars(requete).all())