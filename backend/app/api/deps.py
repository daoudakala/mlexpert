"""Dépendances FastAPI transverses : authentification, contexte d'entreprise,
contrôle de permission.

Import en avant : `app.modules.utilisateurs.models.Utilisateur` n'existe pas
encore (module `utilisateurs`, prochaine étape). L'import échouera tant que
ce fichier n'est pas écrit, même chose que pour `droits/router.py` avant
aujourd'hui.
"""

import uuid
from dataclasses import dataclass

from fastapi import Depends, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import AccesRefuse, NonAuthentifie, RessourceIntrouvable
from app.core.security import decode_access_token
from app.modules.droits.models import Affectation
from app.modules.droits.service import ServiceDroits
from app.modules.utilisateurs.models import Utilisateur  # noqa: à créer

_schema_bearer = HTTPBearer(auto_error=False)


def _extraire_jeton_acces(
    request: Request, identifiants: HTTPAuthorizationCredentials | None
) -> str | None:
    """Deux sources possibles, dans cet ordre :

    1. L'en-tête `Authorization: Bearer ...` — pour un client API/script
       (ex. nos propres scénarios de test via `TestClient`, une intégration
       tierce future).
    2. Le cookie `HttpOnly` posé par `/auth/connexion` (voir
       `app/modules/auth/router.py`) — c'est la voie qu'emprunte le
       frontend Vue, qui ne voit jamais le jeton en JavaScript.

    L'en-tête a priorité s'il est présent : un appel qui fournit
    explicitement un `Authorization` ne doit pas être court-circuité par un
    cookie de navigateur qui traînerait par ailleurs.
    """
    if identifiants is not None:
        return identifiants.credentials
    return request.cookies.get(get_settings().cookie_acces_nom)


def get_utilisateur_courant(
    request: Request,
    identifiants: HTTPAuthorizationCredentials | None = Security(_schema_bearer),
    db: Session = Depends(get_db),
) -> Utilisateur:
    jeton = _extraire_jeton_acces(request, identifiants)
    if jeton is None:
        raise NonAuthentifie()

    payload = decode_access_token(jeton)
    utilisateur_id = uuid.UUID(payload["sub"])

    utilisateur = db.get(Utilisateur, utilisateur_id)
    if utilisateur is None or not utilisateur.actif:
        raise NonAuthentifie("Compte introuvable ou désactivé.")
    return utilisateur


@dataclass
class ContexteEntreprise:
    """Contexte résolu d'une requête portant sur une entreprise précise.

    C'est cet objet, et non `entreprise_id` pris tel quel dans l'URL, que
    les routers et repositories doivent utiliser : il prouve qu'une
    affectation active a été vérifiée pour cet utilisateur.
    """

    entreprise_id: uuid.UUID
    utilisateur_id: uuid.UUID
    affectation: Affectation
    codes_permissions: set[str]


def get_contexte_entreprise(
    entreprise_id: uuid.UUID,
    utilisateur: Utilisateur = Depends(get_utilisateur_courant),
    db: Session = Depends(get_db),
) -> ContexteEntreprise:
    service = ServiceDroits(db)
    try:
        affectation, codes_permissions = service.obtenir_contexte_acces(
            utilisateur.id, entreprise_id
        )
    except RessourceIntrouvable as exc:
        # 403 plutôt que 404 : ne pas révéler l'existence de l'entreprise
        # à un utilisateur qui n'y est pas affecté.
        raise AccesRefuse("Vous n'avez pas accès à cette entreprise.") from exc

    return ContexteEntreprise(
        entreprise_id=entreprise_id,
        utilisateur_id=utilisateur.id,
        affectation=affectation,
        codes_permissions=codes_permissions,
    )


def exiger_permission(code_permission: str):
    """Fabrique de dépendance : vérifie une permission dans le contexte
    d'entreprise résolu. Usage dans un router :

        dependencies=[Depends(exiger_permission("tiers.creer"))]
    """

    def verifier(
        contexte: ContexteEntreprise = Depends(get_contexte_entreprise),
    ) -> ContexteEntreprise:
        if code_permission not in contexte.codes_permissions:
            raise AccesRefuse(
                f"Permission requise : {code_permission}.",
                details={"permission_requise": code_permission},
            )
        return contexte

    return verifier


def exiger_administrateur_plateforme(
    utilisateur: Utilisateur = Depends(get_utilisateur_courant),
    db: Session = Depends(get_db),
) -> Utilisateur:
    """À utiliser sur les routes d'administration globale (pas de notion
    d'entreprise) : gestion des rôles, des utilisateurs, des sauvegardes...
    """
    service = ServiceDroits(db)
    if not service.est_administrateur_plateforme(utilisateur.id):
        raise AccesRefuse("Réservé à l'administrateur de la plateforme.")
    return utilisateur