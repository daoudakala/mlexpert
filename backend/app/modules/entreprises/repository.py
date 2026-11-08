"""Accès aux données du module entreprises.

Nommage : la classe s'appelle `RepositoryEntreprises` (au pluriel), pas
`RepositoryEntreprise`, pour ne pas entrer en collision avec
`shared.repository.RepositoryEntreprise` — la classe générique que TOUS
LES AUTRES modules utilisent pour filtrer leurs propres données par
entreprise. Les deux noms qui se ressemblent désignent des choses très
différentes ; le pluriel ici est le signal qui les distingue à l'import.

`Entreprise` n'étant pas elle-même une donnée cloisonnée (elle EST le
périmètre), ce repository hérite du `Repository` simple, pas de la
variante filtrée.
"""

from sqlalchemy import or_, select

from app.modules.entreprises.models import Entreprise
from app.shared.repository import Repository


class RepositoryEntreprises(Repository[Entreprise]):
    modele = Entreprise

    def rechercher(
        self, terme: str, *, limite: int = 50, decalage: int = 0
    ) -> list[Entreprise]:
        """Recherche large sur la raison sociale et le sigle (écran liste,
        cahier section 31)."""
        motif = f"%{terme}%"
        requete = (
            select(Entreprise)
            .where(
                or_(
                    Entreprise.raison_sociale.ilike(motif),
                    Entreprise.sigle.ilike(motif),
                )
            )
            .limit(limite)
            .offset(decalage)
        )
        return list(self.db.scalars(requete).all())