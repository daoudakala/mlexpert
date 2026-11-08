"""Règles métier du module droits.

C'est ce service que `api/deps.py` appellera pour résoudre le contexte
d'une requête (affectation active, permissions du rôle) et pour vérifier
qu'une permission précise est accordée.

Chaque méthode qui écrit prend un paramètre `auteur_id` : c'est
l'utilisateur au nom duquel l'action est tracée dans le journal
d'activité, jamais déduit implicitement. Le router le fournit à partir de
l'utilisateur authentifié (soit via `exiger_administrateur_plateforme`,
soit via `contexte.utilisateur_id` pour les routes filtrées par
`exiger_permission`).
"""

import secrets
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.exceptions import Conflit, RessourceIntrouvable, ValidationMetier
from app.modules.droits.models import Affectation, AttributionRoleGlobal, Permission, Role
from app.modules.droits.repository import (
    RepositoryAffectation,
    RepositoryAttributionRoleGlobal,
    RepositoryPermission,
    RepositoryRole,
    RepositoryRolePermission,
)
from app.modules.entreprises.models import Entreprise
from app.modules.entreprises.repository import RepositoryEntreprises
from app.modules.journal_activite.models import TypeAction
from app.modules.journal_activite.service import ServiceJournalActivite
from app.modules.notifications.models import NiveauCriticite, TypeNotification
from app.modules.notifications.service import ServiceNotifications
from app.modules.tiers.repository import RepositoryTiers
from app.modules.utilisateurs.models import Utilisateur
from app.modules.utilisateurs.service import ServiceUtilisateurs


@dataclass
class ContexteAccesUtilisateur:
    """Le « portefeuille » d'une affectation, vu du frontend : de quoi
    peupler le sélecteur d'entreprise et construire le menu sans requête
    supplémentaire par entreprise — voir
    `ServiceDroits.lister_contextes_acces_utilisateur`."""

    affectation: Affectation
    entreprise: Entreprise
    role: Role
    codes_permissions: set[str]

# Code du rôle de plateforme "Administrateur" (cahier des charges, section 6).
# Constante plutôt que chaîne répétée, pour n'avoir qu'un seul endroit à
# changer si ce code évolue.
CODE_ROLE_ADMINISTRATEUR_PLATEFORME = "administrateur_plateforme"

# Code du rôle métier (non-plateforme) "Administrateur d'entreprise", seedé
# par la migration `a2f6c9e1b438` (Étape 6 — auto-gestion des entreprises).
# Affecté automatiquement au créateur d'une entreprise par
# `ServiceEntreprises.creer_entreprise`.
CODE_ROLE_ADMINISTRATEUR_ENTREPRISE = "administrateur_entreprise"

# Longueur du mot de passe temporaire généré par `inviter_utilisateur` —
# volontairement bien au-dessus de `password_min_length` (12 par défaut,
# voir core/config.py) : c'est un mot de passe qui ne sera tapé qu'une
# fois (ou jamais, si transmis par copier-coller), pas mémorisé.
LONGUEUR_MOT_DE_PASSE_TEMPORAIRE = 16


class ServiceDroits:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.entreprises = RepositoryEntreprises(db)
        self.roles = RepositoryRole(db)
        self.permissions = RepositoryPermission(db)
        self.roles_permissions = RepositoryRolePermission(db)
        self.affectations = RepositoryAffectation(db)
        self.attributions_globales = RepositoryAttributionRoleGlobal(db)
        self.journal = ServiceJournalActivite(db)
        self.utilisateurs = ServiceUtilisateurs(db)

    # --- Rôles et permissions -----------------------------------------

    def lister_roles(self) -> list[Role]:
        return self.roles.lister()

    def lister_permissions(self) -> list[Permission]:
        return self.permissions.lister()

    def creer_role(
        self,
        *,
        auteur_id: uuid.UUID,
        code: str,
        libelle: str,
        est_role_plateforme: bool = False,
        codes_permissions: list[str] | None = None,
    ) -> Role:
        if self.roles.obtenir_par_code(code) is not None:
            raise Conflit(f"Le rôle '{code}' existe déjà.")

        role = Role(code=code, libelle=libelle, est_role_plateforme=est_role_plateforme)
        self.roles.ajouter(role)

        if codes_permissions:
            self._associer_permissions(role, codes_permissions)

        self.journal.enregistrer(
            module="droits",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            type_objet="Role",
            objet_id=role.id,
            description=f"Création du rôle '{code}'.",
            valeurs_apres={"code": code, "libelle": libelle, "est_role_plateforme": est_role_plateforme},
        )
        return role

    def obtenir_role(self, role_id: uuid.UUID) -> Role:
        return self._obtenir_role_ou_lever(role_id)

    def lister_permissions_role(self, role_id: uuid.UUID) -> list[Permission]:
        self._obtenir_role_ou_lever(role_id)
        return self.roles_permissions.lister_permissions_pour_role(role_id)

    def modifier_role(
        self,
        role_id: uuid.UUID,
        *,
        auteur_id: uuid.UUID,
        code: str | None = None,
        libelle: str | None = None,
        codes_permissions: list[str] | None = None,
    ) -> Role:
        """Mise à jour partielle d'un rôle existant — jusqu'ici absente
        (voir la note en tête de `RolesListe.vue` côté frontend) : un rôle
        créé ne pouvait plus voir son jeu de permissions évoluer. Fournir
        `codes_permissions` REMPLACE l'intégralité des permissions du rôle
        (même convention que `ServiceComptabilite.modifier_modele` pour ses
        lignes) — une liste vide retire donc toutes les permissions.

        Les permissions se résolvent par RÔLE, jamais par utilisateur
        individuel (voir la docstring de models.py : pas de table
        d'association directe utilisateur-permission) : modifier un rôle
        change donc immédiatement les droits de tous les utilisateurs qui
        y sont affectés, dans toutes les entreprises concernées — au
        prochain rafraîchissement de leur contexte d'accès (connexion, ou
        `GET /droits/moi/contextes`), pas en temps réel sur une session
        déjà ouverte.

        `est_role_plateforme` n'est volontairement pas modifiable ici :
        en faire basculer un existant changerait rétroactivement la portée
        (entreprise <-> plateforme) de toutes les affectations/attributions
        qui le référencent déjà, ce qui demande une vérification dédiée,
        hors de la portée de ce correctif."""
        role = self._obtenir_role_ou_lever(role_id)

        if code is not None and code != role.code:
            if self.roles.obtenir_par_code(code) is not None:
                raise Conflit(f"Le rôle '{code}' existe déjà.")
            role.code = code
        if libelle is not None:
            role.libelle = libelle
        if codes_permissions is not None:
            self.roles_permissions.supprimer_pour_role(role_id)
            if codes_permissions:
                self._associer_permissions(role, codes_permissions)
        self.db.flush()

        self.journal.enregistrer(
            module="droits",
            type_action=TypeAction.MODIFIER,
            utilisateur_id=auteur_id,
            type_objet="Role",
            objet_id=role.id,
            description=f"Modification du rôle '{role.code}'.",
        )
        return role

    def _obtenir_role_ou_lever(self, role_id: uuid.UUID) -> Role:
        role = self.roles.obtenir(role_id)
        if role is None:
            raise RessourceIntrouvable("Rôle introuvable.")
        return role

    def _associer_permissions(self, role: Role, codes_permissions: list[str]) -> None:
        permissions = self.permissions.obtenir_plusieurs_par_code(codes_permissions)
        codes_trouves = {p.code for p in permissions}
        codes_manquants = set(codes_permissions) - codes_trouves
        if codes_manquants:
            raise ValidationMetier(
                "Permissions inconnues.",
                details={"codes_manquants": sorted(codes_manquants)},
            )
        for permission in permissions:
            self.roles_permissions.ajouter(
                self.roles_permissions.modele(role_id=role.id, permission_id=permission.id)
            )

    # --- Affectations (rôle métier sur une entreprise) ------------------

    def affecter_utilisateur(
        self,
        *,
        auteur_id: uuid.UUID,
        utilisateur_id: uuid.UUID,
        entreprise_id: uuid.UUID,
        role_id: uuid.UUID,
        module_restreint: str | None = None,
        exercice_id_restreint: uuid.UUID | None = None,
    ) -> Affectation:
        role = self.roles.obtenir(role_id)
        if role is None:
            raise RessourceIntrouvable("Rôle introuvable.")
        if role.est_role_plateforme:
            raise ValidationMetier(
                "Un rôle de plateforme ne peut pas être affecté sur une entreprise."
            )

        existante = self.affectations.obtenir_active(utilisateur_id, entreprise_id)
        if existante is not None:
            raise Conflit(
                "Cet utilisateur a déjà un rôle actif sur cette entreprise.",
                details={"affectation_id": str(existante.id)},
            )

        affectation = Affectation(
            utilisateur_id=utilisateur_id,
            entreprise_id=entreprise_id,
            role_id=role_id,
            module_restreint=module_restreint,
            exercice_id_restreint=exercice_id_restreint,
        )
        self.affectations.ajouter(affectation)
        self.journal.enregistrer(
            module="droits",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            entreprise_id=entreprise_id,
            type_objet="Affectation",
            objet_id=affectation.id,
            description=f"Affectation de l'utilisateur {utilisateur_id} sur l'entreprise.",
            valeurs_apres={
                "utilisateur_id": str(utilisateur_id),
                "role_id": str(role_id),
                "module_restreint": module_restreint,
                "exercice_id_restreint": str(exercice_id_restreint)
                if exercice_id_restreint
                else None,
            },
        )
        # Alerte de sécurité (cahier, section 24) : un nouvel accès accordé
        # à une entreprise est un événement, pas une détection périodique
        # — voir la docstring de tête de `notifications/alertes.py`.
        ServiceNotifications(self.db, entreprise_id).creer(
            destinataire_id=utilisateur_id,
            type_notification=TypeNotification.ALERTE_SECURITE.value,
            niveau_criticite=NiveauCriticite.INFO.value,
            titre="Nouvel accès accordé",
            message=f"Un rôle vous a été attribué sur cette entreprise ({role.libelle}).",
        )
        return affectation

    def inviter_utilisateur(
        self,
        *,
        auteur_id: uuid.UUID,
        entreprise_id: uuid.UUID,
        email: str,
        nom: str,
        prenom: str,
        role_id: uuid.UUID,
        telephone: str | None = None,
        tiers_id: uuid.UUID | None = None,
    ) -> tuple[Affectation, Utilisateur, str | None]:
        """Invitation self-service d'un collaborateur ou d'un client
        (Étape 6 — auto-gestion des entreprises), réservée à
        `droits.administrer` (même permission que `affecter_utilisateur` :
        inviter, c'est créer-le-compte-si-besoin PUIS l'affecter, pas une
        action d'une autre nature).

        Pas d'infrastructure d'email dans ce projet (voir la note de
        conception) : si le compte n'existe pas encore, un mot de passe
        temporaire est généré ici et renvoyé UNE SEULE FOIS dans le
        résultat — à charge pour la personne qui invite de le transmettre
        hors-bande (téléphone, en personne). Il n'est jamais journalisé ni
        reloggé ensuite. Si l'email correspond à un compte déjà existant
        (un collaborateur qui bascule d'une entreprise à l'autre), ce
        compte est réutilisé tel quel et aucun mot de passe n'est généré
        (3ᵉ élément du tuple à `None`) — seule une nouvelle affectation est
        créée.

        `tiers_id`, s'il est fourni, doit désigner un `Tiers` de CETTE
        entreprise : rattache le compte à son dossier client, pour que
        `ServicePortailClient` puisse restreindre ce qu'il voit à ses
        propres documents (voir `Affectation.tiers_id`).
        """
        role = self.roles.obtenir(role_id)
        if role is None:
            raise RessourceIntrouvable("Rôle introuvable.")
        if role.est_role_plateforme:
            raise ValidationMetier(
                "Un rôle de plateforme ne peut pas être affecté sur une entreprise."
            )

        if tiers_id is not None:
            tiers = RepositoryTiers(self.db, entreprise_id).obtenir(tiers_id)
            if tiers is None:
                raise RessourceIntrouvable("Tiers introuvable pour cette entreprise.")

        mot_de_passe_temporaire: str | None = None
        utilisateur = self.utilisateurs.obtenir_par_email(email)
        if utilisateur is None:
            mot_de_passe_temporaire = secrets.token_urlsafe(LONGUEUR_MOT_DE_PASSE_TEMPORAIRE)
            utilisateur = self.utilisateurs.creer_utilisateur(
                auteur_id=auteur_id,
                email=email,
                mot_de_passe=mot_de_passe_temporaire,
                nom=nom,
                prenom=prenom,
                telephone=telephone,
            )

        affectation = self.affecter_utilisateur(
            auteur_id=auteur_id,
            utilisateur_id=utilisateur.id,
            entreprise_id=entreprise_id,
            role_id=role_id,
        )
        if tiers_id is not None:
            affectation.tiers_id = tiers_id
            self.db.flush()

        return affectation, utilisateur, mot_de_passe_temporaire

    def retirer_affectation(
        self, affectation_id: uuid.UUID, *, entreprise_id: uuid.UUID, auteur_id: uuid.UUID
    ) -> None:
        affectation = self.affectations.obtenir(affectation_id)
        if affectation is None or affectation.entreprise_id != entreprise_id:
            # Même message que "introuvable" dans les deux cas : ne pas
            # révéler qu'une affectation existe mais appartient à une autre
            # entreprise que celle de l'URL.
            raise RessourceIntrouvable("Affectation introuvable.")
        affectation.actif = False
        self.db.flush()
        self.journal.enregistrer(
            module="droits",
            type_action=TypeAction.SUPPRIMER,
            utilisateur_id=auteur_id,
            entreprise_id=affectation.entreprise_id,
            type_objet="Affectation",
            objet_id=affectation.id,
            description="Retrait d'affectation.",
            valeurs_avant={"actif": True},
            valeurs_apres={"actif": False},
        )
        # Alerte de sécurité symétrique à `affecter_utilisateur` ci-dessus.
        ServiceNotifications(self.db, affectation.entreprise_id).creer(
            destinataire_id=affectation.utilisateur_id,
            type_notification=TypeNotification.ALERTE_SECURITE.value,
            niveau_criticite=NiveauCriticite.AVERTISSEMENT.value,
            titre="Accès retiré",
            message="Votre accès à cette entreprise a été retiré.",
        )

    # --- Attributions de rôle global (plateforme) ------------------------

    def attribuer_role_global(
        self, *, auteur_id: uuid.UUID, utilisateur_id: uuid.UUID, role_id: uuid.UUID
    ) -> AttributionRoleGlobal:
        role = self.roles.obtenir(role_id)
        if role is None:
            raise RessourceIntrouvable("Rôle introuvable.")
        if not role.est_role_plateforme:
            raise ValidationMetier(
                "Seul un rôle de plateforme peut être attribué globalement."
            )

        attribution = AttributionRoleGlobal(utilisateur_id=utilisateur_id, role_id=role_id)
        self.attributions_globales.ajouter(attribution)
        self.journal.enregistrer(
            module="droits",
            type_action=TypeAction.ADMINISTRER,
            utilisateur_id=auteur_id,
            type_objet="AttributionRoleGlobal",
            objet_id=attribution.id,
            description=f"Attribution du rôle global à l'utilisateur {utilisateur_id}.",
            valeurs_apres={"utilisateur_id": str(utilisateur_id), "role_id": str(role_id)},
        )
        return attribution

    def est_administrateur_plateforme(self, utilisateur_id: uuid.UUID) -> bool:
        """Utilisée par `api/deps.py` (dépendance `exiger_administrateur_plateforme`)."""
        attributions = self.attributions_globales.lister_pour_utilisateur(utilisateur_id)
        if not attributions:
            return False
        roles_ids = {a.role_id for a in attributions}
        return any(
            (role := self.roles.obtenir(role_id)) is not None
            and role.code == CODE_ROLE_ADMINISTRATEUR_PLATEFORME
            for role_id in roles_ids
        )

    # --- Résolution des droits (consommée par api/deps.py) ---------------

    def obtenir_contexte_acces(
        self, utilisateur_id: uuid.UUID, entreprise_id: uuid.UUID
    ) -> tuple[Affectation, set[str]]:
        """Retourne l'affectation active et les codes de permission du rôle.

        Lève `AccesRefuse`... non : lève `RessourceIntrouvable` si aucune
        affectation active n'existe. C'est `api/deps.py` qui décide de la
        convertir en 403 (`AccesRefuse`) plutôt qu'en 404, pour ne pas
        révéler l'existence de l'entreprise à un utilisateur non affecté.
        """
        affectation = self.affectations.obtenir_active(utilisateur_id, entreprise_id)
        if affectation is None:
            raise RessourceIntrouvable("Aucune affectation active sur cette entreprise.")
        codes_permissions = self.roles_permissions.obtenir_codes_permissions(
            affectation.role_id
        )
        return affectation, codes_permissions

    def possede_permission(
        self, utilisateur_id: uuid.UUID, entreprise_id: uuid.UUID, code_permission: str
    ) -> bool:
        try:
            _, codes_permissions = self.obtenir_contexte_acces(utilisateur_id, entreprise_id)
        except RessourceIntrouvable:
            return False
        return code_permission in codes_permissions

    def est_affecte(self, utilisateur_id: uuid.UUID, entreprise_id: uuid.UUID) -> bool:
        """Utilisée par d'autres modules (ex. entreprises/router.py) pour
        savoir si un utilisateur a accès à une entreprise, sans avoir besoin
        du détail de l'affectation ni de ses permissions."""
        return self.affectations.obtenir_active(utilisateur_id, entreprise_id) is not None

    def lister_affectations_utilisateur(self, utilisateur_id: uuid.UUID) -> list[Affectation]:
        """Le portefeuille d'entreprises d'un utilisateur (vue cabinet)."""
        return self.affectations.lister_pour_utilisateur(utilisateur_id)

    def lister_affectations_entreprise(self, entreprise_id: uuid.UUID) -> list[Affectation]:
        return self.affectations.obtenir_pour_entreprise(entreprise_id)

    def lister_contextes_acces_utilisateur(
        self, utilisateur_id: uuid.UUID
    ) -> list[ContexteAccesUtilisateur]:
        """Le portefeuille complet d'un utilisateur, enrichi : pour chaque
        affectation active, l'entreprise, le rôle et les permissions
        résolues du rôle. Pensé pour le frontend (`GET /droits/moi/contextes`)
        qui doit peupler le sélecteur d'entreprise et construire le menu
        après connexion, sans faire une requête par entreprise — il n'a
        plus accès au payload du jeton depuis que celui-ci voyage dans un
        cookie `HttpOnly`."""
        resultats: list[ContexteAccesUtilisateur] = []
        for affectation in self.affectations.lister_pour_utilisateur(utilisateur_id):
            entreprise = self.entreprises.obtenir(affectation.entreprise_id)
            role = self.roles.obtenir(affectation.role_id)
            if entreprise is None or role is None:
                # Incohérence de données (entreprise ou rôle supprimé sans
                # nettoyer l'affectation) : on ignore silencieusement plutôt
                # que de faire échouer tout le portefeuille pour une seule
                # ligne orpheline.
                continue
            codes_permissions = self.roles_permissions.obtenir_codes_permissions(role.id)
            resultats.append(
                ContexteAccesUtilisateur(
                    affectation=affectation,
                    entreprise=entreprise,
                    role=role,
                    codes_permissions=codes_permissions,
                )
            )
        return resultats