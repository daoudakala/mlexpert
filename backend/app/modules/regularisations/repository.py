"""Accès aux données du module regularisations.

Un seul repository entreprise-scopé : il n'y a qu'une table (voir la note
de tête de fichier de `models.py`).
"""

from sqlalchemy import select

from app.modules.regularisations.models import Regularisation
from app.shared.repository import RepositoryEntreprise


class RepositoryRegularisations(RepositoryEntreprise[Regularisation]):
    modele = Regularisation

    def lister(
        self,
        *,
        type_regularisation: str | None = None,
        exercice_id=None,
        limite: int = 1000,
        decalage: int = 0,
    ) -> list[Regularisation]:
        requete = select(Regularisation).where(Regularisation.entreprise_id == self.entreprise_id)
        if type_regularisation is not None:
            requete = requete.where(Regularisation.type_regularisation == type_regularisation)
        if exercice_id is not None:
            requete = requete.where(Regularisation.exercice_id == exercice_id)
        requete = requete.order_by(Regularisation.date_regularisation.desc()).limit(limite).offset(decalage)
        return list(self.db.scalars(requete).all())