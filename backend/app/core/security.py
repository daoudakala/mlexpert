"""Primitives de sécurité : mots de passe et jetons.

- Mots de passe : Argon2id (argon2-cffi), jamais stockés en clair.
- Jeton d'accès : JWT court, qui identifie uniquement l'utilisateur.
  Les droits ne sont PAS dans le jeton : ils dépendent de l'entreprise
  consultée et sont résolus en base à chaque requête (table Affectation).
- Jeton de rafraîchissement : chaîne aléatoire opaque. Seule son empreinte
  est stockée en base (table SessionUtilisateur), ce qui permet la révocation.
"""

import secrets
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings
from app.core.exceptions import TokenInvalide

_hasher = PasswordHasher()


# --- Mots de passe ----------------------------------------------------------


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    """Vrai si les paramètres de hachage ont évolué depuis la création du hash."""
    return _hasher.check_needs_rehash(password_hash)


# --- Jeton d'accès (JWT) ----------------------------------------------------


def create_access_token(user_id: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": user_id,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Décode et vérifie un jeton d'accès. Lève `TokenInvalide` sinon."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenInvalide() from exc

    if payload.get("type") != "access":
        raise TokenInvalide()
    return payload


# --- Jeton de rafraîchissement (opaque) -------------------------------------


def generate_refresh_token() -> tuple[str, str]:
    """Retourne (jeton_en_clair, empreinte).

    Le jeton en clair est envoyé au client une seule fois ;
    seule l'empreinte est enregistrée en base.
    """
    token = secrets.token_urlsafe(48)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()