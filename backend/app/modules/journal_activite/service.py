"""Règles métier du module journal_activite.

`enregistrer()` est la méthode que tous les autres services appelleront
pour remplacer leurs `# TODO(journal_activite)`. Elle ne fait JAMAIS
`db.commit()` elle-même (voir `core/database.py`) : c'est le service
appelant qui valide sa propre transaction, ce qui garantit que la
modification métier et son entrée au journal sont enregistrées ensemble,
ou pas du tout. Un `enregistrer()` suivi d'aucun commit ne laisse aucune
trace — c'est voulu.

Usage typique, depuis un autre service :

    ServiceJournalActivite(self.db).enregistrer(
        utilisateur_id=...,
        entreprise_id=...,
        module="exercices",
        type_action=TypeAction.VALIDER,
        type_objet="Exercice",
        objet_id=exercice.id,
        description="Clôture de l'exercice",
    )
    # pas de commit ici : l'appelant valide sa propre transaction
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.journal_activite.models import JournalActivite, TypeAction
from app.modules.journal_activite.repository import RepositoryJournalActivite
from app.modules.utilisateurs.models import Utilisateur


@dataclass
class EntreeJournalActivite:
    """Une entrée de `JournalActivite` enrichie du nom de son auteur — la
    table elle-même ne porte que `utilisateur_id` (voir la note de tête de
    fichier de `models.py`), le nom est résolu ici en une seule requête
    groupée plutôt que par une relation ORM, pour ne pas alourdir le
    modèle d'une jointure dont seule la consultation a besoin."""

    id: uuid.UUID
    survenu_le: datetime
    utilisateur_id: uuid.UUID | None
    utilisateur_nom: str | None
    utilisateur_prenom: str | None
    utilisateur_email: str | None
    entreprise_id: uuid.UUID | None
    module: str
    type_action: str
    type_objet: str | None
    objet_id: uuid.UUID | None
    description: str | None
    valeurs_avant: dict | None
    valeurs_apres: dict | None
    adresse_ip: str | None


class ServiceJournalActivite:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.entrees = RepositoryJournalActivite(db)

    def enregistrer(
        self,
        *,
        module: str,
        type_action: TypeAction | str,
        utilisateur_id: uuid.UUID | None = None,
        entreprise_id: uuid.UUID | None = None,
        type_objet: str | None = None,
        objet_id: uuid.UUID | None = None,
        description: str | None = None,
        valeurs_avant: dict | None = None,
        valeurs_apres: dict | None = None,
        adresse_ip: str | None = None,
    ) -> JournalActivite:
        entree = JournalActivite(
            module=module,
            type_action=str(type_action),
            utilisateur_id=utilisateur_id,
            entreprise_id=entreprise_id,
            type_objet=type_objet,
            objet_id=objet_id,
            description=description,
            valeurs_avant=valeurs_avant,
            valeurs_apres=valeurs_apres,
            adresse_ip=adresse_ip,
        )
        return self.entrees.ajouter(entree)

    # --- Consultation (section 23 : export selon les droits) --------------

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
    ) -> list[EntreeJournalActivite]:
        entrees = self.entrees.rechercher(
            entreprise_id=entreprise_id,
            utilisateur_id=utilisateur_id,
            module=module,
            type_action=type_action,
            type_objet=type_objet,
            objet_id=objet_id,
            depuis=depuis,
            jusqu_a=jusqu_a,
            limite=limite,
            decalage=decalage,
        )
        return self._enrichir(entrees)

    def lister_pour_objet(self, type_objet: str, objet_id: uuid.UUID) -> list[EntreeJournalActivite]:
        return self._enrichir(self.entrees.lister_pour_objet(type_objet, objet_id))

    # --- Aides internes -------------------------------------------------------

    def _enrichir(self, entrees: list[JournalActivite]) -> list[EntreeJournalActivite]:
        """Résout `utilisateur_id` -> (nom, prénom, email) en une seule
        requête groupée sur les identifiants distincts de la page
        courante, plutôt qu'un aller-retour par entrée."""
        ids_utilisateurs = {e.utilisateur_id for e in entrees if e.utilisateur_id is not None}
        utilisateurs_par_id: dict[uuid.UUID, Utilisateur] = {}
        if ids_utilisateurs:
            requete = select(Utilisateur).where(Utilisateur.id.in_(ids_utilisateurs))
            utilisateurs_par_id = {u.id: u for u in self.db.scalars(requete).all()}

        resultat = []
        for e in entrees:
            utilisateur = utilisateurs_par_id.get(e.utilisateur_id) if e.utilisateur_id else None
            resultat.append(
                EntreeJournalActivite(
                    id=e.id,
                    survenu_le=e.survenu_le,
                    utilisateur_id=e.utilisateur_id,
                    # Compte supprimé entre-temps (SET NULL sur la ligne de
                    # journal uniquement, pas de contrainte ici) : on garde
                    # l'ID mais le nom reste indisponible plutôt que de
                    # lever une erreur.
                    utilisateur_nom=utilisateur.nom if utilisateur else None,
                    utilisateur_prenom=utilisateur.prenom if utilisateur else None,
                    utilisateur_email=utilisateur.email if utilisateur else None,
                    entreprise_id=e.entreprise_id,
                    module=e.module,
                    type_action=e.type_action,
                    type_objet=e.type_objet,
                    objet_id=e.objet_id,
                    description=e.description,
                    valeurs_avant=e.valeurs_avant,
                    valeurs_apres=e.valeurs_apres,
                    adresse_ip=e.adresse_ip,
                )
            )
        return resultat
