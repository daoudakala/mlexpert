"""Accès aux données du module provisions.

Deux repositories entreprise-scopés, comme dans `immobilisations` — rien
de particulier ici.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.provisions.models import MouvementProvision, Provision
from app.shared.repository import RepositoryEntreprise


class RepositoryProvisions(RepositoryEntreprise[Provision]):
    modele = Provision

    def lister(
        self,
        *,
        type_provision: str | None = None,
        statut: str | None = None,
        limite: int = 1000,
        decalage: int = 0,
    ) -> list[Provision]:
        requete = select(Provision).where(Provision.entreprise_id == self.entreprise_id)
        if type_provision is not None:
            requete = requete.where(Provision.type_provision == type_provision)
        if statut is not None:
            requete = requete.where(Provision.statut == statut)
        requete = requete.order_by(Provision.libelle).limit(limite).offset(decalage)
        return list(self.db.scalars(requete).all())


class RepositoryMouvementsProvision(RepositoryEntreprise[MouvementProvision]):
    modele = MouvementProvision

    def lister_pour_provision(self, provision_id: uuid.UUID) -> list[MouvementProvision]:
        """Triées par exercice (jointure nécessaire : `MouvementProvision`
        ne porte que `exercice_id`, pas les dates de l'exercice) — même
        raisonnement que `RepositoryLignesAmortissement.lister_pour_immobilisation`."""
        from app.modules.exercices.models import Exercice

        requete = (
            select(MouvementProvision)
            .join(Exercice, MouvementProvision.exercice_id == Exercice.id)
            .where(
                MouvementProvision.entreprise_id == self.entreprise_id,
                MouvementProvision.provision_id == provision_id,
            )
            .order_by(Exercice.date_debut, MouvementProvision.date_mouvement)
        )
        return list(self.db.scalars(requete).all())