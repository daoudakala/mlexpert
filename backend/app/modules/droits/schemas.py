"""Schémas Pydantic du module droits (entrées/sorties de l'API)."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.entreprises.schemas import EntrepriseLecture


# --- Rôles et permissions ---------------------------------------------------


class PermissionLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    libelle: str


class RoleCreation(BaseModel):
    code: str = Field(min_length=2, max_length=50)
    libelle: str = Field(min_length=2, max_length=100)
    est_role_plateforme: bool = False
    codes_permissions: list[str] | None = None


class RoleLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    libelle: str
    est_role_plateforme: bool
    cree_le: datetime


class RoleAvecPermissions(RoleLecture):
    permissions: list[PermissionLecture] = []


class RoleMiseAJour(BaseModel):
    """Mise à jour partielle (voir `ServiceDroits.modifier_role`).
    `est_role_plateforme` n'est volontairement pas modifiable. Fournir
    `codes_permissions` remplace l'intégralité des permissions du rôle,
    une liste vide les retire toutes."""

    code: str | None = Field(default=None, min_length=2, max_length=50)
    libelle: str | None = Field(default=None, min_length=2, max_length=100)
    codes_permissions: list[str] | None = None


# --- Affectations (rôle métier sur une entreprise) --------------------------


class AffectationCreation(BaseModel):
    utilisateur_id: uuid.UUID
    role_id: uuid.UUID
    module_restreint: str | None = None
    exercice_id_restreint: uuid.UUID | None = None
    date_debut: date | None = None
    date_fin: date | None = None


class AffectationLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    utilisateur_id: uuid.UUID
    entreprise_id: uuid.UUID
    role_id: uuid.UUID
    module_restreint: str | None
    exercice_id_restreint: uuid.UUID | None
    actif: bool
    date_debut: date | None
    date_fin: date | None
    cree_le: datetime


# --- Invitation self-service (Étape 6 — auto-gestion des entreprises) -------


class InvitationCreation(BaseModel):
    """Si `email` correspond à un compte existant, il est réutilisé tel
    quel (`nom`/`prenom`/`telephone` fournis sont alors ignorés pour la
    création — le compte garde ses informations actuelles) ; sinon un
    nouveau compte est créé avec ces informations et un mot de passe
    temporaire généré par le serveur. `tiers_id`, s'il est fourni, rattache
    le compte à ce dossier client — voir `Affectation.tiers_id`."""

    email: EmailStr
    nom: str = Field(min_length=1, max_length=100)
    prenom: str = Field(min_length=1, max_length=100)
    telephone: str | None = None
    role_id: uuid.UUID
    tiers_id: uuid.UUID | None = None


class InvitationResultat(BaseModel):
    utilisateur_id: uuid.UUID
    email: str
    compte_existant: bool
    # Présent UNE SEULE FOIS, à cet instant, seulement si un nouveau compte
    # a été créé (`compte_existant=False`) — jamais reloggé ni récupérable
    # ensuite (voir `ServiceDroits.inviter_utilisateur`).
    mot_de_passe_temporaire: str | None
    affectation: AffectationLecture


# --- Attributions de rôle global (plateforme) --------------------------------


class AttributionRoleGlobalCreation(BaseModel):
    utilisateur_id: uuid.UUID
    role_id: uuid.UUID


class AttributionRoleGlobalLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    utilisateur_id: uuid.UUID
    role_id: uuid.UUID
    actif: bool


# --- Portefeuille d'accès de l'utilisateur connecté (self-service) ----------


class ContexteAccesUtilisateurLecture(BaseModel):
    """Une entrée du portefeuille d'accès de l'utilisateur connecté : une
    entreprise, le rôle qui y est exercé, et les permissions résolues de
    ce rôle. Voir `ServiceDroits.lister_contextes_acces_utilisateur`."""

    affectation_id: uuid.UUID
    entreprise: EntrepriseLecture
    role: RoleLecture
    module_restreint: str | None
    exercice_id_restreint: uuid.UUID | None
    codes_permissions: list[str]