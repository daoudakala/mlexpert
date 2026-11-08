"""Routes HTTP du module auth.

Les jetons voyagent exclusivement via cookies `HttpOnly` (jamais dans un
corps JSON) : `_poser_cookies_jetons` les écrit après connexion ou
rafraîchissement, `_effacer_cookies_jetons` les efface à la déconnexion.
Le jeton de rafraîchissement est en outre limité au chemin `/auth` par
défaut (`cookie_rafraichissement_path`, à régler sur `/api/auth` quand le
frontend appelle l'API via un proxy `/api`) (`path` sur le cookie) : le navigateur ne l'envoie qu'aux routes qui en ont besoin
(`/auth/rafraichir`, `/auth/deconnexion`), jamais aux routes métier.
"""

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_utilisateur_courant
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import NonAuthentifie
from app.modules.auth.schemas import ConnexionDemande, ConnexionReponse
from app.modules.auth.service import ServiceAuth
from app.modules.utilisateurs.models import Utilisateur
from app.modules.utilisateurs.schemas import UtilisateurLecture

router = APIRouter(prefix="/auth", tags=["Authentification"])


def _adresse_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _appareil(request: Request) -> str | None:
    return request.headers.get("user-agent")


def _poser_cookies_jetons(response: Response, *, jeton_acces: str, jeton_rafraichissement: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.cookie_acces_nom,
        value=jeton_acces,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
        path="/",
    )
    response.set_cookie(
        key=settings.cookie_rafraichissement_nom,
        value=jeton_rafraichissement,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
        # Restreint au module auth : ce cookie n'a aucune raison d'être
        # envoyé sur une route de comptabilite/paie/stocks/...
        path=settings.cookie_rafraichissement_path,
    )


def _effacer_cookies_jetons(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.cookie_acces_nom, domain=settings.cookie_domain, path="/"
    )
    response.delete_cookie(
        key=settings.cookie_rafraichissement_nom, domain=settings.cookie_domain,
        path=settings.cookie_rafraichissement_path,
    )


@router.post("/connexion", response_model=ConnexionReponse)
def connexion(
    donnees: ConnexionDemande, request: Request, response: Response, db: Session = Depends(get_db)
) -> ConnexionReponse:
    service = ServiceAuth(db)
    jeton_acces, jeton_rafraichissement, utilisateur = service.connexion(
        email=donnees.email,
        mot_de_passe=donnees.mot_de_passe,
        appareil=_appareil(request),
        adresse_ip=_adresse_ip(request),
    )
    db.commit()
    _poser_cookies_jetons(
        response, jeton_acces=jeton_acces, jeton_rafraichissement=jeton_rafraichissement
    )
    return ConnexionReponse(utilisateur=UtilisateurLecture.model_validate(utilisateur))


@router.post("/rafraichir", response_model=ConnexionReponse)
def rafraichir(
    request: Request, response: Response, db: Session = Depends(get_db)
) -> ConnexionReponse:
    settings = get_settings()
    jeton_rafraichissement_clair = request.cookies.get(settings.cookie_rafraichissement_nom)
    if jeton_rafraichissement_clair is None:
        raise NonAuthentifie("Aucune session à rafraîchir.")

    service = ServiceAuth(db)
    jeton_acces, nouveau_jeton_rafraichissement, utilisateur = service.rafraichir(
        jeton_rafraichissement_clair=jeton_rafraichissement_clair,
        appareil=_appareil(request),
        adresse_ip=_adresse_ip(request),
    )
    db.commit()
    _poser_cookies_jetons(
        response, jeton_acces=jeton_acces, jeton_rafraichissement=nouveau_jeton_rafraichissement
    )
    return ConnexionReponse(utilisateur=UtilisateurLecture.model_validate(utilisateur))


@router.post("/deconnexion", status_code=status.HTTP_204_NO_CONTENT)
def deconnexion(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    settings = get_settings()
    jeton_rafraichissement_clair = request.cookies.get(settings.cookie_rafraichissement_nom)
    if jeton_rafraichissement_clair is not None:
        service = ServiceAuth(db)
        service.deconnexion(jeton_rafraichissement_clair=jeton_rafraichissement_clair)
        db.commit()
    _effacer_cookies_jetons(response)


@router.post("/moi/deconnexion-toutes-sessions", status_code=status.HTTP_204_NO_CONTENT)
def deconnexion_toutes_sessions(
    response: Response,
    utilisateur: Utilisateur = Depends(get_utilisateur_courant),
    db: Session = Depends(get_db),
) -> None:
    """Révoque toutes les sessions actives de l'utilisateur connecté
    (« déconnecter tous les appareils »), y compris la session courante :
    on efface donc aussi ses propres cookies."""
    service = ServiceAuth(db)
    service.revoquer_toutes_les_sessions(utilisateur.id, auteur_id=utilisateur.id)
    db.commit()
    _effacer_cookies_jetons(response)