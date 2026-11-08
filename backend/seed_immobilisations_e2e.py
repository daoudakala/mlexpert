import uuid
from datetime import date

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.main import app  # noqa
from app.modules.utilisateurs.models import Utilisateur
from app.modules.entreprises.models import Entreprise
from app.modules.droits.models import Role, RolePermission, Permission, Affectation
from app.modules.comptabilite.models import Compte, Journal, TypeJournal
from app.modules.exercices.models import Exercice

db = SessionLocal()

suffixe = uuid.uuid4().hex[:6]
email = f"immobilisations.e2e.{suffixe}@example.com"
mot_de_passe = "MotDePasseImmoE2E!2026"

utilisateur = Utilisateur(
    email=email, mot_de_passe_hash=hash_password(mot_de_passe),
    nom="Test", prenom="ImmoE2E", actif=True,
)
db.add(utilisateur)
db.flush()

entreprise = Entreprise(raison_sociale=f"Entreprise Immo E2E {suffixe}")
db.add(entreprise)
db.flush()

role = Role(code=f"role_immo_e2e_{suffixe}", libelle="Rôle immobilisations e2e")
db.add(role)
db.flush()
codes = [
    "immobilisation.consulter", "immobilisation.creer", "immobilisation.modifier",
    "immobilisation.valider", "immobilisation.ceder",
    "compte.consulter", "journal.consulter", "exercice.consulter", "tiers.consulter",
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

journal_od = Journal(
    code="OD1", libelle="Opérations diverses", type_journal=TypeJournal.OPERATIONS_DIVERSES.value,
    actif=True, entreprise_id=entreprise.id,
)
db.add(journal_od)

comptes = [
    ("241000", "Matériel et outillage", 2),
    ("284100", "Amortissements matériel et outillage", 2),
    ("681100", "Dotations aux amortissements", 6),
    ("521000", "Banque", 5),
    ("822000", "Produits de cession d'immobilisations", 8),
    ("812000", "Valeur comptable des cessions d'immobilisations", 8),
]
objets_comptes = {}
for numero, libelle, classe in comptes:
    c = Compte(numero=numero, libelle=libelle, classe=classe, lettrable=False, est_collectif=False, actif=True, entreprise_id=entreprise.id)
    db.add(c)
    objets_comptes[numero] = c
db.flush()

exercice = Exercice(date_debut=date(2026, 1, 1), date_fin=date(2026, 12, 31), statut="ouvert", entreprise_id=entreprise.id)
db.add(exercice)
db.commit()

print("email:", email)
print("mot_de_passe:", mot_de_passe)
print("entreprise_id:", entreprise.id)
print("exercice_id:", exercice.id)