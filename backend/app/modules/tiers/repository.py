"""Accès aux données du module tiers.

`Tiers` est une table entreprise-scopée classique : `RepositoryTiers`
hérite normalement de `RepositoryEntreprise` (voir `shared/repository.py`).

`rechercher_par_nif` n'est pas une contrainte d'unicité (le NIF reste
optionnel et non validé dans `models.py`) mais une aide à la saisie : le
service l'utilise pour avertir avant de créer un doublon, sans jamais
bloquer si l'utilisateur confirme malgré tout.
"""

import uuid

from sqlalchemy import select

from app.modules.tiers.models import Tiers
from app.shared.repository import RepositoryEntreprise


class RepositoryTiers(RepositoryEntreprise[Tiers]):
    modele = Tiers

    def obtenir_par_code(self, code: str) -> Tiers | None:
        requete = select(Tiers).where(
            Tiers.code == code, Tiers.entreprise_id == self.entreprise_id
        )
        return self.db.scalars(requete).first()

    def rechercher_par_nif(self, nif: str) -> list[Tiers]:
        """Les tiers de cette entreprise partageant ce NIF — utilisé pour
        repérer un doublon probable avant création, jamais pour l'empêcher
        (le NIF n'est pas une clé)."""
        requete = select(Tiers).where(Tiers.entreprise_id == self.entreprise_id, Tiers.nif == nif)
        return list(self.db.scalars(requete).all())

    def lister(
        self,
        *,
        actifs_seulement: bool = True,
        client_seulement: bool = False,
        fournisseur_seulement: bool = False,
        limite: int = 100,
        decalage: int = 0,
    ) -> list[Tiers]:
        requete = select(Tiers).where(Tiers.entreprise_id == self.entreprise_id)
        if actifs_seulement:
            requete = requete.where(Tiers.actif.is_(True))
        if client_seulement:
            requete = requete.where(Tiers.compte_collectif_client_id.is_not(None))
        if fournisseur_seulement:
            requete = requete.where(Tiers.compte_collectif_fournisseur_id.is_not(None))
        requete = requete.order_by(Tiers.raison_sociale).limit(limite).offset(decalage)
        return list(self.db.scalars(requete).all())