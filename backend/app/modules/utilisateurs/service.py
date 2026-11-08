"""Règles métier du module utilisateurs.

`creer_utilisateur`, `reinitialiser_mot_de_passe`, `desactiver_utilisateur`
et `reactiver_utilisateur` sont des actions d'administrateur : elles
prennent un `auteur_id` distinct de l'utilisateur ciblé. `changer_mot_de_passe`
est une action sur soi-même : l'auteur et la cible sont la même personne,
donc pas de paramètre séparé — le journal utilise `utilisateur_id` pour
les deux rôles à la fois.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import Conflit, RessourceIntrouvable, ValidationMetier
from app.core.security import hash_password, verify_password
from app.modules.droits.repository import RepositoryAffectation
from app.modules.journal_activite.models import TypeAction
from app.modules.journal_activite.service import ServiceJournalActivite
from app.modules.notifications.models import NiveauCriticite, TypeNotification
from app.modules.notifications.service import ServiceNotifications
from app.modules.utilisateurs.models import Utilisateur
from app.modules.utilisateurs.repository import RepositoryUtilisateur


class ServiceUtilisateurs:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.utilisateurs = RepositoryUtilisateur(db)
        self.journal = ServiceJournalActivite(db)
        self.affectations = RepositoryAffectation(db)

    def creer_utilisateur(
        self,
        *,
        auteur_id: uuid.UUID,
        email: str,
        mot_de_passe: str,
        nom: str,
        prenom: str,
        telephone: str | None = None,
    ) -> Utilisateur:
        email_normalise = email.strip().lower()
        if self.utilisateurs.obtenir_par_email(email_normalise) is not None:
            raise Conflit(f"Un utilisateur existe déjà avec l'adresse '{email_normalise}'.")

        self._valider_force_mot_de_passe(mot_de_passe)

        utilisateur = Utilisateur(
            email=email_normalise,
            mot_de_passe_hash=hash_password(mot_de_passe),
            nom=nom,
            prenom=prenom,
            telephone=telephone,
        )
        self.utilisateurs.ajouter(utilisateur)
        self.journal.enregistrer(
            module="utilisateurs",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            type_objet="Utilisateur",
            objet_id=utilisateur.id,
            description=f"Création du compte '{email_normalise}'.",
            # Jamais le mot de passe, même haché, dans le journal.
            valeurs_apres={"email": email_normalise, "nom": nom, "prenom": prenom},
        )
        return utilisateur

    def changer_mot_de_passe(
        self, utilisateur_id: uuid.UUID, *, ancien_mot_de_passe: str, nouveau_mot_de_passe: str
    ) -> None:
        utilisateur = self._obtenir_ou_lever(utilisateur_id)
        if not verify_password(ancien_mot_de_passe, utilisateur.mot_de_passe_hash):
            raise ValidationMetier("Mot de passe actuel incorrect.")

        self._valider_force_mot_de_passe(nouveau_mot_de_passe)
        utilisateur.mot_de_passe_hash = hash_password(nouveau_mot_de_passe)
        self.db.flush()
        self.journal.enregistrer(
            module="utilisateurs",
            type_action=TypeAction.MODIFIER,
            utilisateur_id=utilisateur_id,
            type_objet="Utilisateur",
            objet_id=utilisateur.id,
            description="Changement de mot de passe (par l'utilisateur lui-même).",
        )
        self._notifier_alerte_securite(
            utilisateur_id,
            titre="Mot de passe modifié",
            message="Votre mot de passe vient d'être changé.",
        )

    def reinitialiser_mot_de_passe(
        self, utilisateur_id: uuid.UUID, *, auteur_id: uuid.UUID, nouveau_mot_de_passe: str
    ) -> None:
        """Réservée à l'administrateur (pas de vérification de l'ancien mot
        de passe) : le contrôle d'accès se fait au niveau du router."""
        utilisateur = self._obtenir_ou_lever(utilisateur_id)
        self._valider_force_mot_de_passe(nouveau_mot_de_passe)
        utilisateur.mot_de_passe_hash = hash_password(nouveau_mot_de_passe)
        self.db.flush()
        self.journal.enregistrer(
            module="utilisateurs",
            type_action=TypeAction.ADMINISTRER,
            utilisateur_id=auteur_id,
            type_objet="Utilisateur",
            objet_id=utilisateur.id,
            description=f"Réinitialisation du mot de passe de {utilisateur.email}.",
        )
        self._notifier_alerte_securite(
            utilisateur_id,
            titre="Mot de passe réinitialisé",
            message="Votre mot de passe vient d'être réinitialisé par un administrateur.",
        )

    def obtenir_utilisateur(self, utilisateur_id: uuid.UUID) -> Utilisateur:
        return self._obtenir_ou_lever(utilisateur_id)

    def obtenir_par_email(self, email: str) -> Utilisateur | None:
        """Utilisée par `modules/auth/service.py` à la connexion — passe par
        le service plutôt que par le repository directement, comme pour
        tout accès inter-module."""
        return self.utilisateurs.obtenir_par_email(email.strip().lower())

    def enregistrer_connexion(self, utilisateur_id: uuid.UUID) -> None:
        utilisateur = self._obtenir_ou_lever(utilisateur_id)
        utilisateur.derniere_connexion_le = datetime.now(timezone.utc)
        self.db.flush()

    def lister_utilisateurs(self) -> list[Utilisateur]:
        return self.utilisateurs.lister()

    def mettre_a_jour_profil(
        self,
        utilisateur_id: uuid.UUID,
        *,
        nom: str | None = None,
        prenom: str | None = None,
        telephone: str | None = None,
    ) -> Utilisateur:
        utilisateur = self._obtenir_ou_lever(utilisateur_id)
        if nom is not None:
            utilisateur.nom = nom
        if prenom is not None:
            utilisateur.prenom = prenom
        if telephone is not None:
            utilisateur.telephone = telephone
        self.db.flush()
        return utilisateur

    def desactiver_utilisateur(self, utilisateur_id: uuid.UUID, *, auteur_id: uuid.UUID) -> None:
        utilisateur = self._obtenir_ou_lever(utilisateur_id)
        utilisateur.actif = False
        self.db.flush()
        self.journal.enregistrer(
            module="utilisateurs",
            type_action=TypeAction.ARCHIVER,
            utilisateur_id=auteur_id,
            type_objet="Utilisateur",
            objet_id=utilisateur.id,
            description=f"Désactivation du compte {utilisateur.email}.",
            valeurs_avant={"actif": True},
            valeurs_apres={"actif": False},
        )

    def reactiver_utilisateur(self, utilisateur_id: uuid.UUID, *, auteur_id: uuid.UUID) -> None:
        utilisateur = self._obtenir_ou_lever(utilisateur_id)
        utilisateur.actif = True
        self.db.flush()
        self.journal.enregistrer(
            module="utilisateurs",
            type_action=TypeAction.ANNULER,
            utilisateur_id=auteur_id,
            type_objet="Utilisateur",
            objet_id=utilisateur.id,
            description=f"Réactivation du compte {utilisateur.email}.",
            valeurs_avant={"actif": False},
            valeurs_apres={"actif": True},
        )

    # --- Aides internes ---------------------------------------------------

    def _obtenir_ou_lever(self, utilisateur_id: uuid.UUID) -> Utilisateur:
        utilisateur = self.utilisateurs.obtenir(utilisateur_id)
        if utilisateur is None:
            raise RessourceIntrouvable("Utilisateur introuvable.")
        return utilisateur

    def _valider_force_mot_de_passe(self, mot_de_passe: str) -> None:
        longueur_min = get_settings().password_min_length
        if len(mot_de_passe) < longueur_min:
            raise ValidationMetier(
                f"Le mot de passe doit contenir au moins {longueur_min} caractères."
            )

    def _notifier_alerte_securite(self, utilisateur_id: uuid.UUID, *, titre: str, message: str) -> None:
        """`Notification.entreprise_id` est obligatoire (voir
        `notifications/models.py`) alors que `ServiceUtilisateurs` n'est pas
        scopé à une entreprise : on notifie donc l'utilisateur dans CHACUNE
        des entreprises où il a une affectation active, plutôt que
        d'inventer une notification "plateforme" hors entreprise que le
        modèle actuel ne sait pas représenter."""
        for affectation in self.affectations.lister_pour_utilisateur(utilisateur_id):
            ServiceNotifications(self.db, affectation.entreprise_id).creer(
                destinataire_id=utilisateur_id,
                type_notification=TypeNotification.ALERTE_SECURITE.value,
                niveau_criticite=NiveauCriticite.AVERTISSEMENT.value,
                titre=titre,
                message=message,
            )