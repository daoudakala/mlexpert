"""Modèle du module utilisateurs.

Une seule table d'authentification pour tous les profils (Administrateur,
Direction, Comptable, Client...) : c'est l'`Affectation` (module `droits`)
qui détermine le rôle d'un utilisateur *par entreprise*, pas une colonne
ici. Un client et un collaborateur du cabinet sont techniquement le même
type d'enregistrement.

`SessionUtilisateur` (jetons de rafraîchissement révocables) n'est pas
dans ce fichier : elle appartient au module `auth`, qui porte la mécanique
de connexion, pas le profil de l'utilisateur.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base import Base
from app.shared.mixins import HorodatageMixin, IdentifiantMixin


class Utilisateur(IdentifiantMixin, HorodatageMixin, Base):
    __tablename__ = "utilisateurs"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    mot_de_passe_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    prenom: Mapped[str] = mapped_column(String(100), nullable=False)
    telephone: Mapped[str | None] = mapped_column(String(30), nullable=True)

    actif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Authentification multifacteur (cahier des charges, section 27).
    mfa_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Secret TOTP chiffré au repos (chiffrement applicatif, pas géré ici) ;
    # nul tant que le MFA n'a pas été activé par l'utilisateur.
    mfa_secret_chiffre: Mapped[str | None] = mapped_column(String(255), nullable=True)

    derniere_connexion_le: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    @property
    def nom_complet(self) -> str:
        return f"{self.prenom} {self.nom}"