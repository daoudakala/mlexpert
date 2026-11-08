"""Configuration centralisée de MLexpert.

Toutes les valeurs proviennent des variables d'environnement (ou du fichier
`.env` en développement). Aucun secret ne doit être écrit en dur dans le code.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application -------------------------------------------------------
    app_name: str = "MLexpert"
    app_version: str = "0.1.0"
    # Les trois environnements prévus par le cahier des charges (section 28.2)
    environment: Literal["developpement", "recette", "production"] = "developpement"
    debug: bool = False

    # --- Base de données ---------------------------------------------------
    # Exemple : postgresql+psycopg2://user:motdepasse@localhost:5432/mlexpert
    database_url: str = "postgresql+psycopg2://postgres:kqlq@localhost:5432/mlexpert"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_echo: bool = False

    # --- Sécurité ----------------------------------------------------------
    secret_key: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    password_min_length: int = 12

    # --- CORS --------------------------------------------------------------
    # En variable d'environnement : format JSON, ex. ["http://localhost:5173"]
    cors_origins: list[str] = ["http://localhost:5173"]

    # --- Cookies d'authentification ------------------------------------------
    # Le frontend Vue reçoit les jetons uniquement via cookies `HttpOnly`
    # (jamais dans le corps de la réponse ni en `localStorage`) — voir
    # `app/modules/auth/router.py`. `cookie_secure` doit rester `True` partout
    # sauf en développement local sans HTTPS (sinon le navigateur ignore le
    # cookie) ; `cookie_samesite="lax"` est la première ligne de défense CSRF
    # (bloque l'envoi du cookie sur une requête cross-site initiée par script,
    # sans nécessiter un jeton CSRF séparé tant que frontend et backend
    # restent sur le même site — à revoir si ce n'est plus le cas en prod).
    cookie_acces_nom: str = "mlexpert_acces"
    cookie_rafraichissement_nom: str = "mlexpert_rafraichissement"
    cookie_secure: bool = True
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    # Domaine explicite si frontend/backend sont sur des sous-domaines
    # distincts d'un même domaine (ex. "mlexpert.ci") ; None = cookie limité
    # à l'hôte exact qui a répondu (comportement par défaut, le plus strict).
    cookie_domain: str | None = None

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @model_validator(mode="after")
    def verifier_coherence(self) -> "Settings":
        """Interdit les réglages de développement hors développement."""
        if self.environment != "developpement":
            if self.debug:
                raise ValueError(
                    "DEBUG ne peut pas être activé en recette ou en production."
                )
            if self.db_echo:
                raise ValueError(
                    "DB_ECHO ne peut pas être activé en recette ou en production."
                )
        return self


@lru_cache
def get_settings() -> Settings:
    """Retourne l'instance unique de la configuration (mise en cache).

    À utiliser via `Depends(get_settings)` dans les routes, ce qui permet de
    la remplacer facilement dans les tests.
    """
    return Settings()