"""Accès aux données du module tresorerie.

Trois repositories entreprise-scopés classiques (`entreprise_id`
dénormalisé sur chaque table, voir models.py), tous héritant de
`RepositoryEntreprise` — rien de particulier ici, contrairement au plan
comptable (`comptabilite/repository.py`).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.tresorerie.models import CompteBancaire, LigneReleve, ReleveBancaire
from app.shared.repository import RepositoryEntreprise


class RepositoryComptesBancaires(RepositoryEntreprise[CompteBancaire]):
    modele = CompteBancaire

    def obtenir_par_journal(self, journal_id: uuid.UUID) -> CompteBancaire | None:
        requete = select(CompteBancaire).where(
            CompteBancaire.entreprise_id == self.entreprise_id,
            CompteBancaire.journal_id == journal_id,
        )
        return self.db.scalars(requete).first()

    def lister(
        self, *, actifs_seulement: bool = True, limite: int = 1000, decalage: int = 0
    ) -> list[CompteBancaire]:
        requete = select(CompteBancaire).where(CompteBancaire.entreprise_id == self.entreprise_id)
        if actifs_seulement:
            requete = requete.where(CompteBancaire.actif.is_(True))
        requete = requete.order_by(CompteBancaire.libelle).limit(limite).offset(decalage)
        return list(self.db.scalars(requete).all())


class RepositoryRelevesBancaires(RepositoryEntreprise[ReleveBancaire]):
    modele = ReleveBancaire

    def lister_pour_compte(
        self, compte_bancaire_id: uuid.UUID, *, limite: int = 100, decalage: int = 0
    ) -> list[ReleveBancaire]:
        requete = (
            select(ReleveBancaire)
            .where(
                ReleveBancaire.entreprise_id == self.entreprise_id,
                ReleveBancaire.compte_bancaire_id == compte_bancaire_id,
            )
            .order_by(ReleveBancaire.date_debut.desc())
            .limit(limite)
            .offset(decalage)
        )
        return list(self.db.scalars(requete).all())


class RepositoryLignesReleve(RepositoryEntreprise[LigneReleve]):
    modele = LigneReleve

    def lister_pour_releve(self, releve_id: uuid.UUID) -> list[LigneReleve]:
        requete = select(LigneReleve).where(
            LigneReleve.entreprise_id == self.entreprise_id,
            LigneReleve.releve_id == releve_id,
        )
        return list(self.db.scalars(requete).all())

    def lister_non_rapprochees(
        self, compte_bancaire_id: uuid.UUID, *, limite: int = 200, decalage: int = 0
    ) -> list[LigneReleve]:
        """Les lignes de relevé de ce compte bancaire pas encore
        rapprochées (`code_lettrage IS NULL`) — utilisé par l'écran de
        rapprochement pour proposer les lignes candidates."""
        requete = (
            select(LigneReleve)
            .join(ReleveBancaire, LigneReleve.releve_id == ReleveBancaire.id)
            .where(
                LigneReleve.entreprise_id == self.entreprise_id,
                ReleveBancaire.compte_bancaire_id == compte_bancaire_id,
                LigneReleve.code_lettrage.is_(None),
            )
            .order_by(LigneReleve.date_operation)
            .limit(limite)
            .offset(decalage)
        )
        return list(self.db.scalars(requete).all())

    def lister_par_code_lettrage(self, code_lettrage: str) -> list[LigneReleve]:
        requete = select(LigneReleve).where(
            LigneReleve.entreprise_id == self.entreprise_id,
            LigneReleve.code_lettrage == code_lettrage,
        )
        return list(self.db.scalars(requete).all())

    def obtenir_plusieurs(self, ids: list[uuid.UUID]) -> list[LigneReleve]:
        requete = select(LigneReleve).where(
            LigneReleve.entreprise_id == self.entreprise_id,
            LigneReleve.id.in_(ids),
        )
        return list(self.db.scalars(requete).all())

    def supprimer_pour_releve(self, releve_id: uuid.UUID) -> None:
        """Utilisé pour remplacer intégralement les lignes d'un relevé
        (voir `ServiceTresorerie.modifier_releve`) — même choix que
        `RepositoryLignesEcriture.supprimer_pour_ecriture`."""
        for ligne in self.lister_pour_releve(releve_id):
            self.db.delete(ligne)
        self.db.flush()