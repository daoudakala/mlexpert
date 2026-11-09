"""Seed pour les modules d'administration (entreprises, utilisateurs,
droits, exercices).

Crée :
- un administrateur plateforme (rôle `administrateur_plateforme`,
  est_role_plateforme=True, via AttributionRoleGlobal) — aucun chemin
  self-service n'existe pour devenir administrateur plateforme, d'où la
  création directe en base ;
- une entreprise existante avec un collaborateur affecté, avec un rôle
  métier portant `droits.administrer`, `droits.consulter`,
  `exercice.*`, `periode.*` — pour tester les pages Exercices et
  Affectations sans être administrateur plateforme.
"""

import uuid

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.main import app  # noqa
from app.modules.utilisateurs.models import Utilisateur
from app.modules.entreprises.models import Entreprise
from app.modules.droits.models import Role, RolePermission, Permission, Affectation, AttributionRoleGlobal
from app.modules.droits.service import CODE_ROLE_ADMINISTRATEUR_PLATEFORME

db = SessionLocal()

suffixe = uuid.uuid4().hex[:6]

# --- Administrateur plateforme ----------------------------------------------

email_admin = f"admin.{suffixe}@mlexpert.com"
mot_de_passe_admin = "AdminE2E!2026"

administrateur = Utilisateur(
    email=email_admin, mot_de_passe_hash=hash_password(mot_de_passe_admin),
    nom="Plateforme", prenom="AdminE2E", actif=True,
)
db.add(administrateur)
db.flush()

role_plateforme = db.query(Role).filter_by(code=CODE_ROLE_ADMINISTRATEUR_PLATEFORME).first()
if role_plateforme is None:
    role_plateforme = Role(
        code=CODE_ROLE_ADMINISTRATEUR_PLATEFORME,
        libelle="Administrateur plateforme",
        est_role_plateforme=True,
    )
    db.add(role_plateforme)
    db.flush()

db.add(AttributionRoleGlobal(utilisateur_id=administrateur.id, role_id=role_plateforme.id))
db.flush()

# --- Entreprise + collaborateur (droits.*, exercice.*, periode.*) ----------

email_collab = f"collab.administration.{suffixe}@mlexpert.com"
mot_de_passe_collab = "CollabE2E!2026"

collaborateur = Utilisateur(
    email=email_collab, mot_de_passe_hash=hash_password(mot_de_passe_collab),
    nom="Collaborateur", prenom="AdministrationE2E", actif=True,
)
db.add(collaborateur)
db.flush()

entreprise = Entreprise(raison_sociale=f"Entreprise Administration E2E {suffixe}")
db.add(entreprise)
db.flush()

role_collab = Role(code=f"role_administration_e2e_{suffixe}", libelle="Rôle administration e2e")
db.add(role_collab)
db.flush()

codes = [
    "droits.administrer", "droits.consulter",
    "exercice.creer", "exercice.consulter", "exercice.valider", "exercice.annuler",
    "periode.creer", "periode.consulter", "periode.valider", "periode.annuler",
]
for code in codes:
    perm = db.query(Permission).filter_by(code=code).first()
    if perm is None:
        perm = Permission(code=code, libelle=code)
        db.add(perm)
        db.flush()
    db.add(RolePermission(role_id=role_collab.id, permission_id=perm.id))
db.flush()

db.add(Affectation(utilisateur_id=collaborateur.id, entreprise_id=entreprise.id, role_id=role_collab.id))

db.commit()

print("email_admin:", email_admin)
print("mot_de_passe_admin:", mot_de_passe_admin)
print("email_collab:", email_collab)
print("mot_de_passe_collab:", mot_de_passe_collab)
print("entreprise_id:", entreprise.id)
print("administrateur_id:", administrateur.id)
print("role_collab_id:", role_collab.id)
