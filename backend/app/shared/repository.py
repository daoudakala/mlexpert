"""Dépôts de données de base.

Deux classes génériques :

- `Repository` : opérations CRUD simples, sans notion d'entreprise
  (utilisée par les tables globales : utilisateurs, rôles, permissions...).
- `RepositoryEntreprise` : la même chose, mais toutes les requêtes sont
  systématiquement filtrées par `entreprise_id`. C'est le mécanisme qui
  garantit l'isolation des données par entreprise : un développeur qui
  hérite de cette classe ne peut pas lire ou écrire hors de l'entreprise
  du contexte courant, même par oubli.

Chaque module définit son propre repository qui hérite de l'une des deux,
en fixant son modèle :

    class RepositoryTiers(RepositoryEntreprise[Tiers]):
        modele = Tiers
"""

import uuid
from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.shared.base import Base

ModeleType = TypeVar("ModeleType", bound=Base)


class Repository(Generic[ModeleType]):
    modele: type[ModeleType]

    def __init__(self, db: Session) -> None:
        self.db = db

    def obtenir(self, id_: uuid.UUID) -> ModeleType | None:
        return self.db.get(self.modele, id_)

    def lister(self, *, limite: int = 100, decalage: int = 0) -> list[ModeleType]:
        requete = select(self.modele).limit(limite).offset(decalage)
        return list(self.db.scalars(requete).all())

    def ajouter(self, objet: ModeleType) -> ModeleType:
        self.db.add(objet)
        self.db.flush()  # rend l'id disponible sans clôturer la transaction
        return objet

    def supprimer(self, objet: ModeleType) -> None:
        self.db.delete(objet)
        self.db.flush()


class RepositoryEntreprise(Repository[ModeleType]):
    """Comme `Repository`, mais toujours filtré par entreprise.

    `entreprise_id` provient du contexte de la requête HTTP courante
    (résolu par `api/deps.py`), jamais d'une valeur choisie par l'appelant.
    """

    def __init__(self, db: Session, entreprise_id: uuid.UUID) -> None:
        super().__init__(db)
        self.entreprise_id = entreprise_id

    def obtenir(self, id_: uuid.UUID) -> ModeleType | None:
        requete = select(self.modele).where(
            self.modele.id == id_,
            self.modele.entreprise_id == self.entreprise_id,
        )
        return self.db.scalars(requete).first()

    def lister(self, *, limite: int = 100, decalage: int = 0) -> list[ModeleType]:
        requete = (
            select(self.modele)
            .where(self.modele.entreprise_id == self.entreprise_id)
            .limit(limite)
            .offset(decalage)
        )
        return list(self.db.scalars(requete).all())

    def ajouter(self, objet: ModeleType) -> ModeleType:
        # Sécurité : impose l'entreprise du contexte, même si l'appelant a
        # renseigné (ou oublié) `entreprise_id` autrement.
        objet.entreprise_id = self.entreprise_id
        return super().ajouter(objet)