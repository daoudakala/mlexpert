"""Accès aux données du module immobilisations.

Deux repositories entreprise-scopés classiques, comme dans `tresorerie` —
rien de particulier ici.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.immobilisations.models import Immobilisation, LigneAmortissement
from app.shared.repository import RepositoryEntreprise


class RepositoryImmobilisations(RepositoryEntreprise[Immobilisation]):
    modele = Immobilisation

    def lister(
        self, *, statut: str | None = None, limite: int = 1000, decalage: int = 0
    ) -> list[Immobilisation]:
        requete = select(Immobilisation).where(Immobilisation.entreprise_id == self.entreprise_id)
        if statut is not None:
            requete = requete.where(Immobilisation.statut == statut)
        requete = requete.order_by(Immobilisation.libelle).limit(limite).offset(decalage)
        return list(self.db.scalars(requete).all())


class RepositoryLignesAmortissement(RepositoryEntreprise[LigneAmortissement]):
    modele = LigneAmortissement

    def lister_pour_immobilisation(self, immobilisation_id: uuid.UUID) -> list[LigneAmortissement]:
        """Triées par exercice (jointure nécessaire : `LigneAmortissement`
        ne porte que `exercice_id`, pas les dates de l'exercice)."""
        from app.modules.exercices.models import Exercice

        requete = (
            select(LigneAmortissement)
            .join(Exercice, LigneAmortissement.exercice_id == Exercice.id)
            .where(
                LigneAmortissement.entreprise_id == self.entreprise_id,
                LigneAmortissement.immobilisation_id == immobilisation_id,
            )
            .order_by(Exercice.date_debut)
        )
        return list(self.db.scalars(requete).all())

    def obtenir_pour_exercice(
        self, immobilisation_id: uuid.UUID, exercice_id: uuid.UUID
    ) -> LigneAmortissement | None:
        requete = select(LigneAmortissement).where(
            LigneAmortissement.entreprise_id == self.entreprise_id,
            LigneAmortissement.immobilisation_id == immobilisation_id,
            LigneAmortissement.exercice_id == exercice_id,
        )
        return self.db.scalars(requete).first()