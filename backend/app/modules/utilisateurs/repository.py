"""Accès aux données du module utilisateurs."""

from sqlalchemy import select

from app.modules.utilisateurs.models import Utilisateur
from app.shared.repository import Repository


class RepositoryUtilisateur(Repository[Utilisateur]):
    modele = Utilisateur

    def obtenir_par_email(self, email: str) -> Utilisateur | None:
        requete = select(Utilisateur).where(Utilisateur.email == email.lower())
        return self.db.scalars(requete).first()