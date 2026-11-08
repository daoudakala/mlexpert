"""Accès aux données du module interlocuteurs.

Repository entreprise-scopé classique — rien de particulier, comme dans
`documents`/`tresorerie`.
"""

from sqlalchemy import select

from app.modules.interlocuteurs.models import Interlocuteur
from app.shared.repository import RepositoryEntreprise


class RepositoryInterlocuteurs(RepositoryEntreprise[Interlocuteur]):
    modele = Interlocuteur

    def lister(
        self,
        *,
        role: str | None = None,
        actifs_seulement: bool = True,
        limite: int = 200,
        decalage: int = 0,
    ) -> list[Interlocuteur]:
        requete = select(Interlocuteur).where(Interlocuteur.entreprise_id == self.entreprise_id)
        if actifs_seulement:
            requete = requete.where(Interlocuteur.actif.is_(True))
        if role is not None:
            requete = requete.where(Interlocuteur.role == role)
        requete = requete.order_by(Interlocuteur.nom).limit(limite).offset(decalage)
        return list(self.db.scalars(requete).all())
