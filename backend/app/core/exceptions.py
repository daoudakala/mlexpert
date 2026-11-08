"""Erreurs métier normalisées.

Les services lèvent ces exceptions ; le gestionnaire enregistré dans
`main.py` les convertit en réponses JSON au format unique :

    {"erreur": {"code": "...", "message": "...", "details": {...}}}

Les modules pourront définir leurs propres erreurs en héritant de celles-ci
(par exemple `PeriodeCloturee(ValidationMetier)` dans le module exercices).
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class ErreurMetier(Exception):
    status_code: int = 400
    code: str = "erreur_metier"
    message_defaut: str = "Une erreur est survenue."
    headers: dict[str, str] | None = None

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.message_defaut
        self.details = details
        super().__init__(self.message)


class NonAuthentifie(ErreurMetier):
    status_code = 401
    code = "non_authentifie"
    message_defaut = "Authentification requise."
    headers = {"WWW-Authenticate": "Bearer"}


class TokenInvalide(NonAuthentifie):
    code = "token_invalide"
    message_defaut = "Jeton invalide ou expiré."


class AccesRefuse(ErreurMetier):
    status_code = 403
    code = "acces_refuse"
    message_defaut = "Vous n'avez pas les droits nécessaires."


class RessourceIntrouvable(ErreurMetier):
    status_code = 404
    code = "ressource_introuvable"
    message_defaut = "Ressource introuvable."


class Conflit(ErreurMetier):
    status_code = 409
    code = "conflit"
    message_defaut = "L'opération est en conflit avec l'état actuel des données."


class ValidationMetier(ErreurMetier):
    status_code = 422
    code = "validation_metier"
    message_defaut = "Les données ne respectent pas les règles de gestion."


def enregistrer_gestionnaires_erreurs(app: FastAPI) -> None:
    """À appeler une seule fois lors de la création de l'application."""

    @app.exception_handler(ErreurMetier)
    async def gerer_erreur_metier(request: Request, exc: ErreurMetier) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content={
                "erreur": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )