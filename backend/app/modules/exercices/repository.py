"""Accès aux données du module exercices.

Premier module dont les repositories héritent de `RepositoryEntreprise`
(shared/repository.py) plutôt que de `Repository` : `Exercice` et
`Periode` sont des données cloisonnées par entreprise, contrairement aux
référentiels globaux vus jusqu'ici (rôles, permissions, utilisateurs,
entreprises elles-mêmes). Toute méthode héritée (`obtenir`, `lister`,
`ajouter`) est donc déjà filtrée sur l'entreprise du contexte.
"""

import uuid
from datetime import date

from sqlalchemy import select

from app.modules.exercices.models import Exercice, Periode, StatutExercice
from app.shared.repository import RepositoryEntreprise


class RepositoryExercice(RepositoryEntreprise[Exercice]):
    modele = Exercice

    def lister(self, *, limite: int = 100, decalage: int = 0) -> list[Exercice]:
        """Surcharge du générique (shared/repository.py) : trie par date de
        début croissante, pour que le frontend puisse présélectionner
        l'exercice le plus récent via `liste[liste.length - 1]`
        (ReportingPage.vue) sans dépendre d'un ordre non garanti par le
        SGBD.
        """
        requete = (
            select(Exercice)
            .where(Exercice.entreprise_id == self.entreprise_id)
            .order_by(Exercice.date_debut)
            .limit(limite)
            .offset(decalage)
        )
        return list(self.db.scalars(requete).all())

    def lister_ouverts(self) -> list[Exercice]:
        requete = select(Exercice).where(
            Exercice.entreprise_id == self.entreprise_id,
            Exercice.statut == StatutExercice.OUVERT.value,
        )
        return list(self.db.scalars(requete).all())

    def obtenir_pour_date(self, une_date: date) -> Exercice | None:
        """L'exercice de l'entreprise dont l'intervalle contient `une_date`,
        s'il existe. Ajoutée pour la génération d'écriture depuis `stocks`
        (`ServiceStocks.generer_ecriture_mouvement`) : `MouvementStock` n'a
        pas d'`exercice_id` propre (à la différence de `LigneAmortissement`
        ou `BulletinPaie`), donc l'exercice se retrouve par la date du
        mouvement plutôt que par une clé étrangère dédiée."""
        requete = select(Exercice).where(
            Exercice.entreprise_id == self.entreprise_id,
            Exercice.date_debut <= une_date,
            Exercice.date_fin >= une_date,
        )
        return self.db.scalars(requete).first()

    def chevauche(
        self, date_debut: date, date_fin: date, *, exclure_id: uuid.UUID | None = None
    ) -> list[Exercice]:
        """Exercices de l'entreprise dont l'intervalle croise
        [date_debut, date_fin]. Utilisée par le service pour interdire deux
        exercices qui se recouvrent."""
        requete = select(Exercice).where(
            Exercice.entreprise_id == self.entreprise_id,
            Exercice.date_debut <= date_fin,
            Exercice.date_fin >= date_debut,
        )
        if exclure_id is not None:
            requete = requete.where(Exercice.id != exclure_id)
        return list(self.db.scalars(requete).all())


class RepositoryPeriode(RepositoryEntreprise[Periode]):
    modele = Periode

    def lister_pour_exercice(self, exercice_id: uuid.UUID) -> list[Periode]:
        requete = select(Periode).where(
            Periode.entreprise_id == self.entreprise_id,
            Periode.exercice_id == exercice_id,
        )
        return list(self.db.scalars(requete).all())

    def chevauche(
        self,
        exercice_id: uuid.UUID,
        date_debut: date,
        date_fin: date,
        *,
        exclure_id: uuid.UUID | None = None,
    ) -> list[Periode]:
        requete = select(Periode).where(
            Periode.entreprise_id == self.entreprise_id,
            Periode.exercice_id == exercice_id,
            Periode.date_debut <= date_fin,
            Periode.date_fin >= date_debut,
        )
        if exclure_id is not None:
            requete = requete.where(Periode.id != exclure_id)
        return list(self.db.scalars(requete).all())