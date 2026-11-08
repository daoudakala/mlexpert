import uuid
from datetime import date

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.main import app  # noqa
from app.modules.utilisateurs.models import Utilisateur
from app.modules.entreprises.models import Entreprise
from app.modules.droits.models import Role, RolePermission, Permission, Affectation
from app.modules.exercices.models import Exercice

db = SessionLocal()

suffixe = uuid.uuid4().hex[:6]
email = f"comptabilite.e2e.{suffixe}@example.com"
mot_de_passe = "MotDePasseComptabiliteE2E!2026"

utilisateur = Utilisateur(
    email=email, mot_de_passe_hash=hash_password(mot_de_passe),
    nom="Test", prenom="ComptabiliteE2E", actif=True,
)
db.add(utilisateur)
db.flush()

entreprise = Entreprise(raison_sociale=f"Entreprise Comptabilite E2E {suffixe}")
db.add(entreprise)
db.flush()

role = Role(code=f"role_comptabilite_e2e_{suffixe}", libelle="Rôle comptabilité e2e")
db.add(role)
db.flush()
codes = [
    "compte.consulter", "compte.creer", "compte.archiver",
    "journal.consulter", "journal.creer", "journal.archiver",
    "ecriture.creer", "ecriture.consulter", "ecriture.modifier",
    "ecriture.supprimer", "ecriture.valider", "ecriture.annuler",
    "tiers.consulter",
    "exercice.consulter",
]
for code in codes:
    perm = db.query(Permission).filter_by(code=code).first()
    if perm is None:
        perm = Permission(code=code, libelle=code)
        db.add(perm)
        db.flush()
    db.add(RolePermission(role_id=role.id, permission_id=perm.id))
db.flush()

db.add(Affectation(utilisateur_id=utilisateur.id, entreprise_id=entreprise.id, role_id=role.id))

exercice = Exercice(
    date_debut=date(2026, 1, 1), date_fin=date(2026, 12, 31), statut="ouvert",
    entreprise_id=entreprise.id,
)
db.add(exercice)
db.commit()

print("email:", email)
print("mot_de_passe:", mot_de_passe)
print("entreprise_id:", entreprise.id)
print("exercice_id:", exercice.id)