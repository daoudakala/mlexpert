"""Accès aux données du module auth."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.modules.auth.models import SessionUtilisateur
from app.shared.repository import Repository


class RepositorySessionUtilisateur(Repository[SessionUtilisateur]):
    modele = SessionUtilisateur

    def obtenir_par_jeton_hache(self, jeton_hache: str) -> SessionUtilisateur | None:
        requete = select(SessionUtilisateur).where(
            SessionUtilisateur.jeton_hache == jeton_hache
        )
        return self.db.scalars(requete).first()

    def lister_actives_pour_utilisateur(
        self, utilisateur_id: uuid.UUID
    ) -> list[SessionUtilisateur]:
        maintenant = datetime.now(timezone.utc)
        requete = select(SessionUtilisateur).where(
            SessionUtilisateur.utilisateur_id == utilisateur_id,
            SessionUtilisateur.revoque_le.is_(None),
            SessionUtilisateur.expire_le > maintenant,
        )
        return list(self.db.scalars(requete).all())