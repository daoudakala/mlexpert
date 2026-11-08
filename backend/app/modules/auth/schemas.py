"""Schémas Pydantic du module auth.

Depuis le passage aux cookies `HttpOnly` (voir `router.py`), les jetons ne
transitent plus JAMAIS dans un corps JSON — ni en réponse de `/connexion`,
ni en requête de `/rafraichir` ou `/deconnexion` (le jeton de
rafraîchissement est lu depuis le cookie, pas depuis le corps). Les anciens
schémas `JetonsReponse`/`RafraichirDemande`/`DeconnexionDemande` ont donc
disparu : il n'y a plus rien à transporter côté client pour ces routes.
"""

from pydantic import BaseModel, EmailStr

from app.modules.utilisateurs.schemas import UtilisateurLecture


class ConnexionDemande(BaseModel):
    email: EmailStr
    mot_de_passe: str


class ConnexionReponse(BaseModel):
    utilisateur: UtilisateurLecture