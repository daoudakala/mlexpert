"""Accès aux données du module paie.

Quatre repositories entreprise-scopés classiques — rien de particulier,
comme dans `tresorerie`/`immobilisations`.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.paie.models import BulletinPaie, Employe, LigneBulletin, RubriquePaie
from app.shared.repository import RepositoryEntreprise


class RepositoryEmployes(RepositoryEntreprise[Employe]):
    modele = Employe

    def obtenir_par_matricule(self, matricule: str) -> Employe | None:
        requete = select(Employe).where(
            Employe.entreprise_id == self.entreprise_id, Employe.matricule == matricule
        )
        return self.db.scalars(requete).first()

    def lister(
        self, *, actifs_seulement: bool = True, limite: int = 1000, decalage: int = 0
    ) -> list[Employe]:
        requete = select(Employe).where(Employe.entreprise_id == self.entreprise_id)
        if actifs_seulement:
            requete = requete.where(Employe.statut == "actif")
        requete = requete.order_by(Employe.nom, Employe.prenom).limit(limite).offset(decalage)
        return list(self.db.scalars(requete).all())


class RepositoryRubriquesPaie(RepositoryEntreprise[RubriquePaie]):
    modele = RubriquePaie

    def obtenir_par_code(self, code: str) -> RubriquePaie | None:
        requete = select(RubriquePaie).where(
            RubriquePaie.entreprise_id == self.entreprise_id, RubriquePaie.code == code
        )
        return self.db.scalars(requete).first()

    def lister(
        self, *, actifs_seulement: bool = True, limite: int = 1000, decalage: int = 0
    ) -> list[RubriquePaie]:
        requete = select(RubriquePaie).where(RubriquePaie.entreprise_id == self.entreprise_id)
        if actifs_seulement:
            requete = requete.where(RubriquePaie.actif.is_(True))
        requete = requete.order_by(RubriquePaie.code).limit(limite).offset(decalage)
        return list(self.db.scalars(requete).all())


class RepositoryBulletinsPaie(RepositoryEntreprise[BulletinPaie]):
    modele = BulletinPaie

    def obtenir_pour_periode(
        self, employe_id: uuid.UUID, periode_debut, periode_fin
    ) -> BulletinPaie | None:
        requete = select(BulletinPaie).where(
            BulletinPaie.entreprise_id == self.entreprise_id,
            BulletinPaie.employe_id == employe_id,
            BulletinPaie.periode_debut == periode_debut,
            BulletinPaie.periode_fin == periode_fin,
        )
        return self.db.scalars(requete).first()

    def lister(
        self,
        *,
        employe_id: uuid.UUID | None = None,
        exercice_id: uuid.UUID | None = None,
        statut: str | None = None,
        limite: int = 200,
        decalage: int = 0,
    ) -> list[BulletinPaie]:
        requete = select(BulletinPaie).where(BulletinPaie.entreprise_id == self.entreprise_id)
        if employe_id is not None:
            requete = requete.where(BulletinPaie.employe_id == employe_id)
        if exercice_id is not None:
            requete = requete.where(BulletinPaie.exercice_id == exercice_id)
        if statut is not None:
            requete = requete.where(BulletinPaie.statut == statut)
        requete = requete.order_by(BulletinPaie.periode_debut.desc()).limit(limite).offset(decalage)
        return list(self.db.scalars(requete).all())


class RepositoryLignesBulletin(RepositoryEntreprise[LigneBulletin]):
    modele = LigneBulletin

    def lister_pour_bulletin(self, bulletin_id: uuid.UUID) -> list[LigneBulletin]:
        requete = select(LigneBulletin).where(
            LigneBulletin.entreprise_id == self.entreprise_id,
            LigneBulletin.bulletin_id == bulletin_id,
        )
        return list(self.db.scalars(requete).all())

    def supprimer_pour_bulletin(self, bulletin_id: uuid.UUID) -> None:
        for ligne in self.lister_pour_bulletin(bulletin_id):
            self.db.delete(ligne)
        self.db.flush()