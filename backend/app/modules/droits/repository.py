"""Accès aux données du module droits.

Aucune classe ici n'hérite de `RepositoryEntreprise` : ce module est
justement celui qui *établit* le contexte d'entreprise consommé ailleurs
(voir shared/repository.py). `RepositoryAffectation.obtenir_active` reçoit
`entreprise_id` en paramètre explicite, il ne le tient pas d'un contexte
déjà résolu — ce serait circulaire.
"""

import uuid

from sqlalchemy import select

from app.modules.droits.models import (
    Affectation,
    AttributionRoleGlobal,
    Permission,
    Role,
    RolePermission,
)
from app.shared.repository import Repository


class RepositoryRole(Repository[Role]):
    modele = Role

    def obtenir_par_code(self, code: str) -> Role | None:
        requete = select(Role).where(Role.code == code)
        return self.db.scalars(requete).first()


class RepositoryPermission(Repository[Permission]):
    modele = Permission

    def obtenir_par_code(self, code: str) -> Permission | None:
        requete = select(Permission).where(Permission.code == code)
        return self.db.scalars(requete).first()

    def obtenir_plusieurs_par_code(self, codes: list[str]) -> list[Permission]:
        requete = select(Permission).where(Permission.code.in_(codes))
        return list(self.db.scalars(requete).all())


class RepositoryAffectation(Repository[Affectation]):
    modele = Affectation

    def obtenir_active(
        self, utilisateur_id: uuid.UUID, entreprise_id: uuid.UUID
    ) -> Affectation | None:
        """Utilisée par `api/deps.py` pour établir le contexte d'entreprise."""
        requete = select(Affectation).where(
            Affectation.utilisateur_id == utilisateur_id,
            Affectation.entreprise_id == entreprise_id,
            Affectation.actif.is_(True),
        )
        return self.db.scalars(requete).first()

    def lister_pour_utilisateur(self, utilisateur_id: uuid.UUID) -> list[Affectation]:
        """Le portefeuille d'entreprises d'un utilisateur (vue cabinet)."""
        requete = select(Affectation).where(
            Affectation.utilisateur_id == utilisateur_id,
            Affectation.actif.is_(True),
        )
        return list(self.db.scalars(requete).all())

    def obtenir_pour_entreprise(
        self, entreprise_id: uuid.UUID, *, limite: int = 100, decalage: int = 0
    ) -> list[Affectation]:
        """Les utilisateurs affectés à une entreprise donnée."""
        requete = (
            select(Affectation)
            .where(
                Affectation.entreprise_id == entreprise_id,
                Affectation.actif.is_(True),
            )
            .limit(limite)
            .offset(decalage)
        )
        return list(self.db.scalars(requete).all())

    def lister_utilisateurs_avec_permission(
        self, entreprise_id: uuid.UUID, code_permission: str
    ) -> list[uuid.UUID]:
        """Les utilisateurs de cette entreprise dont le rôle actif porte
        cette permission — utilisée par `notifications.alertes` (Étape 5)
        pour trouver les destinataires d'une alerte quand aucun
        utilisateur précis n'est désigné par l'objet concerné (ex. "des
        écritures en brouillon", par opposition à "la demande X de telle
        personne")."""
        requete = (
            select(Affectation.utilisateur_id)
            .join(Role, Role.id == Affectation.role_id)
            .join(RolePermission, RolePermission.role_id == Role.id)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .where(
                Affectation.entreprise_id == entreprise_id,
                Affectation.actif.is_(True),
                Permission.code == code_permission,
            )
            .distinct()
        )
        return list(self.db.scalars(requete).all())


class RepositoryAttributionRoleGlobal(Repository[AttributionRoleGlobal]):
    modele = AttributionRoleGlobal

    def lister_pour_utilisateur(
        self, utilisateur_id: uuid.UUID
    ) -> list[AttributionRoleGlobal]:
        requete = select(AttributionRoleGlobal).where(
            AttributionRoleGlobal.utilisateur_id == utilisateur_id,
            AttributionRoleGlobal.actif.is_(True),
        )
        return list(self.db.scalars(requete).all())


class RepositoryRolePermission(Repository[RolePermission]):
    modele = RolePermission

    def obtenir_codes_permissions(self, role_id: uuid.UUID) -> set[str]:
        requete = (
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role_id)
        )
        return set(self.db.scalars(requete).all())

    def lister_permissions_pour_role(self, role_id: uuid.UUID) -> list[Permission]:
        """Comme `obtenir_codes_permissions`, mais les objets `Permission`
        complets (id + libellé) — utilisée pour afficher/éditer le détail
        d'un rôle (`ServiceDroits.modifier_role`), alors que
        `obtenir_codes_permissions` sert la résolution des droits (juste
        les codes, consommée par `api/deps.py`)."""
        requete = (
            select(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role_id)
            .order_by(Permission.code)
        )
        return list(self.db.scalars(requete).all())

    def supprimer_pour_role(self, role_id: uuid.UUID) -> None:
        requete = select(RolePermission).where(RolePermission.role_id == role_id)
        for association in self.db.scalars(requete).all():
            self.db.delete(association)
        self.db.flush()