"""Schémas Pydantic du module utilisateurs."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UtilisateurCreation(BaseModel):
    email: EmailStr
    mot_de_passe: str = Field(min_length=8)
    nom: str = Field(min_length=1, max_length=100)
    prenom: str = Field(min_length=1, max_length=100)
    telephone: str | None = None


class UtilisateurLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    nom: str
    prenom: str
    telephone: str | None
    actif: bool
    mfa_active: bool
    derniere_connexion_le: datetime | None
    cree_le: datetime


class MonProfilLecture(UtilisateurLecture):
    """`UtilisateurLecture` + le statut d'administrateur plateforme —
    uniquement pour GET /utilisateurs/moi : c'est ce que le frontend
    utilise pour savoir s'il doit proposer les écrans d'administration
    (gestion des entreprises, des rôles...), un mécanisme séparé des
    permissions par entreprise (voir ServiceDroits.est_administrateur_plateforme).
    Pas ajouté à UtilisateurLecture directement pour ne pas forcer ce calcul
    sur chaque ligne de `lister_utilisateurs`."""

    administrateur_plateforme: bool


class UtilisateurMiseAJourProfil(BaseModel):
    nom: str | None = Field(default=None, min_length=1, max_length=100)
    prenom: str | None = Field(default=None, min_length=1, max_length=100)
    telephone: str | None = None


class ChangementMotDePasse(BaseModel):
    ancien_mot_de_passe: str
    nouveau_mot_de_passe: str = Field(min_length=8)


class ReinitialisationMotDePasse(BaseModel):
    nouveau_mot_de_passe: str = Field(min_length=8)
