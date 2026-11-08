"""Règles métier du module auth.

Connexion, rafraîchissement (avec rotation du jeton) et déconnexion.

Le mot de passe et le hachage du jeton restent dans `core/security.py` ;
ce service orchestre : vérifier les identifiants, créer/révoquer les
sessions, tracer les événements de connexion dans le journal d'activité.

MFA : `Utilisateur.mfa_active` existe déjà (module `utilisateurs`), mais
la vérification TOTP elle-même n'est pas implémentée. Choix retenu par
prudence : `connexion()` REFUSE l'accès à un compte avec MFA activé
plutôt que de l'ignorer silencieusement — une politique de sécurité
déclarée sur le compte ne doit jamais être contournée par un vide
d'implémentation. À lever explicitement quand la vérification TOTP sera
écrite.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import NonAuthentifie, TokenInvalide, ValidationMetier
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_token,
    verify_password,
)
from app.modules.auth.models import SessionUtilisateur
from app.modules.auth.repository import RepositorySessionUtilisateur
from app.modules.journal_activite.models import TypeAction
from app.modules.journal_activite.service import ServiceJournalActivite
from app.modules.utilisateurs.models import Utilisateur
from app.modules.utilisateurs.service import ServiceUtilisateurs


class ServiceAuth:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.sessions = RepositorySessionUtilisateur(db)
        self.journal = ServiceJournalActivite(db)
        self.utilisateurs = ServiceUtilisateurs(db)

    def connexion(
        self,
        *,
        email: str,
        mot_de_passe: str,
        appareil: str | None = None,
        adresse_ip: str | None = None,
    ) -> tuple[str, str, Utilisateur]:
        """Retourne (jeton_acces, jeton_rafraichissement_clair, utilisateur)."""
        email_normalise = email.strip().lower()
        utilisateur = self.utilisateurs.obtenir_par_email(email_normalise)

        identifiants_valides = (
            utilisateur is not None
            and utilisateur.actif
            and verify_password(mot_de_passe, utilisateur.mot_de_passe_hash)
        )
        if not identifiants_valides:
            self.journal.enregistrer(
                module="auth",
                type_action=TypeAction.CONNEXION_ECHOUEE,
                utilisateur_id=utilisateur.id if utilisateur else None,
                description=f"Tentative de connexion échouée pour '{email_normalise}'.",
                adresse_ip=adresse_ip,
            )
            raise NonAuthentifie("Email ou mot de passe incorrect.")

        if utilisateur.mfa_active:
            raise ValidationMetier(
                "L'authentification à deux facteurs n'est pas encore prise en charge."
            )

        jeton_acces = create_access_token(str(utilisateur.id))
        jeton_rafraichissement_clair, jeton_rafraichissement_hache = generate_refresh_token()
        expire_le = datetime.now(timezone.utc) + timedelta(
            days=get_settings().refresh_token_expire_days
        )
        session = SessionUtilisateur(
            utilisateur_id=utilisateur.id,
            jeton_hache=jeton_rafraichissement_hache,
            appareil=appareil,
            adresse_ip=adresse_ip,
            expire_le=expire_le,
        )
        self.sessions.ajouter(session)
        self.utilisateurs.enregistrer_connexion(utilisateur.id)
        self.journal.enregistrer(
            module="auth",
            type_action=TypeAction.CONNEXION,
            utilisateur_id=utilisateur.id,
            description="Connexion réussie.",
            adresse_ip=adresse_ip,
        )
        return jeton_acces, jeton_rafraichissement_clair, utilisateur

    def rafraichir(
        self,
        *,
        jeton_rafraichissement_clair: str,
        appareil: str | None = None,
        adresse_ip: str | None = None,
    ) -> tuple[str, str, Utilisateur]:
        """Rotation : l'ancien jeton de rafraîchissement est révoqué et
        remplacé par un nouveau à chaque appel. Retourne (jeton_acces,
        nouveau_jeton_rafraichissement_clair, utilisateur) — l'utilisateur
        est renvoyé pour que `router.py` puisse redonner `ConnexionReponse`
        sans requête supplémentaire (utile après un rechargement de page :
        le frontend rafraîchit et récupère l'utilisateur en un seul appel)."""
        jeton_hache = hash_token(jeton_rafraichissement_clair)
        session = self.sessions.obtenir_par_jeton_hache(jeton_hache)
        if session is None or not session.est_active:
            raise TokenInvalide("Jeton de rafraîchissement invalide ou expiré.")

        utilisateur = self.utilisateurs.obtenir_utilisateur(session.utilisateur_id)
        if not utilisateur.actif:
            raise NonAuthentifie("Compte désactivé.")

        maintenant = datetime.now(timezone.utc)
        session.revoque_le = maintenant
        session.derniere_utilisation_le = maintenant

        jeton_acces = create_access_token(str(utilisateur.id))
        nouveau_clair, nouveau_hache = generate_refresh_token()
        nouvelle_session = SessionUtilisateur(
            utilisateur_id=utilisateur.id,
            jeton_hache=nouveau_hache,
            appareil=appareil or session.appareil,
            adresse_ip=adresse_ip or session.adresse_ip,
            expire_le=maintenant + timedelta(days=get_settings().refresh_token_expire_days),
        )
        self.sessions.ajouter(nouvelle_session)
        self.db.flush()
        return jeton_acces, nouveau_clair, utilisateur

    def deconnexion(self, *, jeton_rafraichissement_clair: str) -> None:
        """Idempotente : un jeton déjà révoqué ou inconnu ne lève pas
        d'erreur, pour qu'un double appel de déconnexion reste sans effet
        visible côté client."""
        jeton_hache = hash_token(jeton_rafraichissement_clair)
        session = self.sessions.obtenir_par_jeton_hache(jeton_hache)
        if session is None or session.revoque_le is not None:
            return

        session.revoque_le = datetime.now(timezone.utc)
        self.db.flush()
        self.journal.enregistrer(
            module="auth",
            type_action=TypeAction.DECONNEXION,
            utilisateur_id=session.utilisateur_id,
            description="Déconnexion.",
        )

    def revoquer_toutes_les_sessions(
        self, utilisateur_id: uuid.UUID, *, auteur_id: uuid.UUID
    ) -> int:
        """Révoque toutes les sessions actives d'un utilisateur (ex. compte
        compromis, ou désactivation). Retourne le nombre de sessions
        révoquées."""
        sessions_actives = self.sessions.lister_actives_pour_utilisateur(utilisateur_id)
        maintenant = datetime.now(timezone.utc)
        for session in sessions_actives:
            session.revoque_le = maintenant
        self.db.flush()

        if sessions_actives:
            self.journal.enregistrer(
                module="auth",
                type_action=TypeAction.ADMINISTRER,
                utilisateur_id=auteur_id,
                type_objet="Utilisateur",
                objet_id=utilisateur_id,
                description=f"Révocation de {len(sessions_actives)} session(s) active(s).",
            )
        return len(sessions_actives)