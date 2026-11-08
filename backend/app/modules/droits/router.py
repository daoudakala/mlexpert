"""Routes HTTP du module droits.

Convention de permission pour ce module : `droits.administrer` /
`droits.consulter`.

Les routes qui écrivent capturent l'utilisateur authentifié comme
paramètre (pas seulement dans `dependencies=[]`) pour pouvoir transmettre
`auteur_id` au service, qui l'utilise pour tracer l'action dans le journal
d'activité.
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import (
    ContexteEntreprise,
    exiger_administrateur_plateforme,
    exiger_permission,
    get_utilisateur_courant,
)
from app.core.database import get_db
from app.modules.droits.schemas import (
    AffectationCreation,
    AffectationLecture,
    AttributionRoleGlobalCreation,
    AttributionRoleGlobalLecture,
    ContexteAccesUtilisateurLecture,
    InvitationCreation,
    InvitationResultat,
    PermissionLecture,
    RoleAvecPermissions,
    RoleCreation,
    RoleLecture,
    RoleMiseAJour,
)
from app.modules.droits.service import ServiceDroits
from app.modules.entreprises.schemas import EntrepriseLecture
from app.modules.utilisateurs.models import Utilisateur

router = APIRouter(prefix="/droits", tags=["Droits"])


# --- Portefeuille d'accès de l'utilisateur connecté (self-service) ----------


@router.get("/moi/contextes", response_model=list[ContexteAccesUtilisateurLecture])
def lister_mes_contextes_acces(
    utilisateur: Utilisateur = Depends(get_utilisateur_courant),
    db: Session = Depends(get_db),
) -> list[ContexteAccesUtilisateurLecture]:
    """Le portefeuille complet de l'utilisateur connecté : une entrée par
    entreprise où il a une affectation active, avec le rôle et les
    permissions résolues. Route self-service (pas de `exiger_permission` :
    chacun peut consulter son propre portefeuille) — c'est elle que le
    frontend appelle juste après la connexion, faute de pouvoir lire le
    contenu du jeton d'accès (cookie `HttpOnly`)."""
    service = ServiceDroits(db)
    contextes = service.lister_contextes_acces_utilisateur(utilisateur.id)
    return [
        ContexteAccesUtilisateurLecture(
            affectation_id=c.affectation.id,
            entreprise=EntrepriseLecture.model_validate(c.entreprise),
            role=RoleLecture.model_validate(c.role),
            module_restreint=c.affectation.module_restreint,
            exercice_id_restreint=c.affectation.exercice_id_restreint,
            codes_permissions=sorted(c.codes_permissions),
        )
        for c in contextes
    ]


# --- Rôles et permissions : administration de plateforme --------------------


@router.post("/roles", response_model=RoleLecture, status_code=status.HTTP_201_CREATED)
def creer_role(
    donnees: RoleCreation,
    administrateur: Utilisateur = Depends(exiger_administrateur_plateforme),
    db: Session = Depends(get_db),
) -> RoleLecture:
    service = ServiceDroits(db)
    role = service.creer_role(
        auteur_id=administrateur.id,
        code=donnees.code,
        libelle=donnees.libelle,
        est_role_plateforme=donnees.est_role_plateforme,
        codes_permissions=donnees.codes_permissions,
    )
    db.commit()
    return RoleLecture.model_validate(role)


def _role_avec_permissions(service: ServiceDroits, role) -> RoleAvecPermissions:
    permissions = service.lister_permissions_role(role.id)
    return RoleAvecPermissions.model_validate(
        {
            **RoleLecture.model_validate(role).model_dump(),
            "permissions": [PermissionLecture.model_validate(p) for p in permissions],
        }
    )


@router.get("/roles", response_model=list[RoleAvecPermissions])
def lister_roles(db: Session = Depends(get_db)) -> list[RoleAvecPermissions]:
    """Renvoie désormais les permissions de chaque rôle (RoleAvecPermissions) :
    c'est ce qui manquait jusqu'ici pour que l'écran d'administration
    puisse afficher et éditer le jeu de permissions d'un rôle existant,
    plutôt que seulement celui saisi à sa création (voir modifier_role)."""
    service = ServiceDroits(db)
    return [_role_avec_permissions(service, r) for r in service.lister_roles()]


@router.get("/roles/{role_id}", response_model=RoleAvecPermissions)
def lire_role(
    role_id: uuid.UUID,
    administrateur: Utilisateur = Depends(exiger_administrateur_plateforme),
    db: Session = Depends(get_db),
) -> RoleAvecPermissions:
    service = ServiceDroits(db)
    role = service.obtenir_role(role_id)
    return _role_avec_permissions(service, role)


@router.patch("/roles/{role_id}", response_model=RoleAvecPermissions)
def modifier_role(
    role_id: uuid.UUID,
    donnees: RoleMiseAJour,
    administrateur: Utilisateur = Depends(exiger_administrateur_plateforme),
    db: Session = Depends(get_db),
) -> RoleAvecPermissions:
    service = ServiceDroits(db)
    role = service.modifier_role(
        role_id,
        auteur_id=administrateur.id,
        code=donnees.code,
        libelle=donnees.libelle,
        codes_permissions=donnees.codes_permissions,
    )
    db.commit()
    return _role_avec_permissions(service, role)


@router.get("/permissions", response_model=list[PermissionLecture])
def lister_permissions(db: Session = Depends(get_db)) -> list[PermissionLecture]:
    service = ServiceDroits(db)
    return [PermissionLecture.model_validate(p) for p in service.lister_permissions()]


# --- Affectations : gérées dans le périmètre d'une entreprise ---------------


@router.post(
    "/entreprises/{entreprise_id}/affectations",
    response_model=AffectationLecture,
    status_code=status.HTTP_201_CREATED,
)
def affecter_utilisateur(
    entreprise_id: uuid.UUID,
    donnees: AffectationCreation,
    contexte: ContexteEntreprise = Depends(exiger_permission("droits.administrer")),
    db: Session = Depends(get_db),
) -> AffectationLecture:
    service = ServiceDroits(db)
    affectation = service.affecter_utilisateur(
        auteur_id=contexte.utilisateur_id,
        utilisateur_id=donnees.utilisateur_id,
        entreprise_id=entreprise_id,
        role_id=donnees.role_id,
        module_restreint=donnees.module_restreint,
        exercice_id_restreint=donnees.exercice_id_restreint,
    )
    db.commit()
    return AffectationLecture.model_validate(affectation)


@router.get(
    "/entreprises/{entreprise_id}/affectations",
    response_model=list[AffectationLecture],
)
def lister_affectations(
    entreprise_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("droits.consulter")),
    db: Session = Depends(get_db),
) -> list[AffectationLecture]:
    service = ServiceDroits(db)
    affectations = service.lister_affectations_entreprise(entreprise_id)
    return [AffectationLecture.model_validate(a) for a in affectations]


@router.delete(
    "/entreprises/{entreprise_id}/affectations/{affectation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def retirer_affectation(
    entreprise_id: uuid.UUID,
    affectation_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("droits.administrer")),
    db: Session = Depends(get_db),
) -> None:
    """Scopée à l'entreprise depuis l'Étape 6 (auto-gestion des
    entreprises) : symétrique de `affecter_utilisateur`/`inviter_utilisateur`
    ci-dessus, plutôt que réservée à l'administrateur de plateforme comme
    c'était le cas jusqu'ici."""
    service = ServiceDroits(db)
    service.retirer_affectation(
        affectation_id, entreprise_id=entreprise_id, auteur_id=contexte.utilisateur_id
    )
    db.commit()


@router.post(
    "/entreprises/{entreprise_id}/inviter",
    response_model=InvitationResultat,
    status_code=status.HTTP_201_CREATED,
)
def inviter_utilisateur(
    entreprise_id: uuid.UUID,
    donnees: InvitationCreation,
    contexte: ContexteEntreprise = Depends(exiger_permission("droits.administrer")),
    db: Session = Depends(get_db),
) -> InvitationResultat:
    """Invitation self-service d'un collaborateur ou d'un compte client
    (Étape 6) — voir la docstring de `ServiceDroits.inviter_utilisateur`
    pour le détail (création ou réutilisation du compte, mot de passe
    temporaire renvoyé une seule fois)."""
    service = ServiceDroits(db)
    affectation, utilisateur, mot_de_passe_temporaire = service.inviter_utilisateur(
        auteur_id=contexte.utilisateur_id,
        entreprise_id=entreprise_id,
        email=donnees.email,
        nom=donnees.nom,
        prenom=donnees.prenom,
        role_id=donnees.role_id,
        telephone=donnees.telephone,
        tiers_id=donnees.tiers_id,
    )
    db.commit()
    return InvitationResultat(
        affectation=AffectationLecture.model_validate(affectation),
        utilisateur_id=utilisateur.id,
        email=utilisateur.email,
        compte_existant=mot_de_passe_temporaire is None,
        mot_de_passe_temporaire=mot_de_passe_temporaire,
    )


@router.get(
    "/entreprises/{entreprise_id}/roles-disponibles",
    response_model=list[RoleLecture],
)
def lister_roles_disponibles(
    entreprise_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("droits.administrer")),
    db: Session = Depends(get_db),
) -> list[RoleLecture]:
    """Les rôles que l'administrateur de cette entreprise peut choisir pour
    `inviter_utilisateur`/`affecter_utilisateur` : tous les rôles non-
    plateforme du catalogue. La CRÉATION de nouveaux rôles reste réservée
    à l'administrateur de plateforme (`POST /droits/roles` ci-dessus) —
    cette route ne fait que lister ceux déjà définis."""
    service = ServiceDroits(db)
    return [RoleLecture.model_validate(r) for r in service.lister_roles() if not r.est_role_plateforme]


# --- Attributions de rôle global (plateforme) --------------------------------


@router.post(
    "/attributions-globales",
    response_model=AttributionRoleGlobalLecture,
    status_code=status.HTTP_201_CREATED,
)
def attribuer_role_global(
    donnees: AttributionRoleGlobalCreation,
    administrateur: Utilisateur = Depends(exiger_administrateur_plateforme),
    db: Session = Depends(get_db),
) -> AttributionRoleGlobalLecture:
    service = ServiceDroits(db)
    attribution = service.attribuer_role_global(
        auteur_id=administrateur.id,
        utilisateur_id=donnees.utilisateur_id,
        role_id=donnees.role_id,
    )
    db.commit()
    return AttributionRoleGlobalLecture.model_validate(attribution)