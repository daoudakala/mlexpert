"""Crée un utilisateur de test avec un rôle couvrant TOUTES les permissions
du code (pratique pour naviguer le frontend sans se heurter à des 403), une
entreprise, et l'affectation qui les relie.

Usage (depuis backend/, avec le venv actif) :
    python creer_compte_test_complet.py
"""
import uuid

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.main import app  # noqa: importe transitivement tous les modèles

from app.modules.utilisateurs.models import Utilisateur
from app.modules.entreprises.models import Entreprise
from app.modules.droits.models import Role, RolePermission, Permission, Affectation

# Toutes les permissions référencées par exiger_permission(...) dans le code
# (voir app/api/deps.py et chaque module/router.py).
CODES_PERMISSIONS = [
    "article.archiver", "article.consulter", "article.creer", "article.modifier",
    "bulletin.consulter", "bulletin.creer", "bulletin.modifier", "bulletin.valider",
    "compte.archiver", "compte.consulter", "compte.creer",
    "compte_bancaire.archiver", "compte_bancaire.consulter", "compte_bancaire.creer",
    "dashboard.consulter",
    "document.consulter", "document.creer", "document.modifier", "document.supprimer",
    "droits.administrer", "droits.consulter",
    "ecriture.annuler", "ecriture.consulter", "ecriture.creer", "ecriture.modifier",
    "ecriture.supprimer", "ecriture.valider",
    "employe.archiver", "employe.consulter", "employe.creer", "employe.modifier",
    "exercice.annuler", "exercice.consulter", "exercice.creer", "exercice.valider",
    "immobilisation.ceder", "immobilisation.consulter", "immobilisation.creer",
    "immobilisation.modifier", "immobilisation.valider",
    "journal.archiver", "journal.consulter", "journal.creer",
    "journal_activite.consulter",
    "mouvement_stock.consulter", "mouvement_stock.creer",
    "periode.annuler", "periode.consulter", "periode.creer", "periode.valider",
    "portail_client.consulter", "portail_client.demander", "portail_client.traiter",
    "rapprochement.annuler", "rapprochement.creer",
    "releve.consulter", "releve.creer", "releve.modifier", "releve.supprimer",
    "rubrique_paie.archiver", "rubrique_paie.consulter", "rubrique_paie.creer",
    "rubrique_paie.modifier",
    "tiers.annuler", "tiers.archiver", "tiers.consulter", "tiers.creer", "tiers.modifier",
]

db = SessionLocal()

email = "test@example.com"
mot_de_passe = "Test!2026"

utilisateur = db.query(Utilisateur).filter_by(email=email).first()
if utilisateur is None:
    utilisateur = Utilisateur(
        email=email, mot_de_passe_hash=hash_password(mot_de_passe),
        nom="Test", prenom="Compte", actif=True,
    )
    db.add(utilisateur)
    db.flush()
    print(f"Utilisateur créé : {email}")
else:
    print(f"Utilisateur déjà existant, réutilisé : {email}")

role = db.query(Role).filter_by(code="role_test_complet").first()
if role is None:
    role = Role(code="role_test_complet", libelle="Rôle test (toutes permissions)")
    db.add(role)
    db.flush()

    for code in CODES_PERMISSIONS:
        perm = db.query(Permission).filter_by(code=code).first()
        if perm is None:
            perm = Permission(code=code, libelle=code)
            db.add(perm)
            db.flush()
        db.add(RolePermission(role_id=role.id, permission_id=perm.id))
    db.flush()
    print(f"Rôle créé avec {len(CODES_PERMISSIONS)} permissions")
else:
    print("Rôle déjà existant, réutilisé")

entreprise = db.query(Entreprise).filter_by(raison_sociale="Entreprise de test").first()
if entreprise is None:
    entreprise = Entreprise(raison_sociale="Entreprise de test")
    db.add(entreprise)
    db.flush()
    print("Entreprise créée : Entreprise de test")
else:
    print("Entreprise déjà existante, réutilisée")

affectation_existante = (
    db.query(Affectation)
    .filter_by(utilisateur_id=utilisateur.id, entreprise_id=entreprise.id, actif=True)
    .first()
)
if affectation_existante is None:
    db.add(Affectation(utilisateur_id=utilisateur.id, entreprise_id=entreprise.id, role_id=role.id))
    print("Affectation créée")
else:
    print("Affectation déjà existante")

db.commit()

print("\n--- Identifiants de connexion ---")
print(f"email        : {email}")
print(f"mot de passe : {mot_de_passe}")