import uuid
from datetime import date

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.main import app  # noqa
from app.modules.utilisateurs.models import Utilisateur
from app.modules.entreprises.models import Entreprise
from app.modules.droits.models import Role, RolePermission, Permission, Affectation
from app.modules.comptabilite.models import Compte, Journal
from app.modules.exercices.models import Exercice

db = SessionLocal()

suffixe = uuid.uuid4().hex[:6]
email = f"stocks.e2e.{suffixe}@example.com"
mot_de_passe = "MotDePasseStocksE2E!2026"

utilisateur = Utilisateur(
    email=email, mot_de_passe_hash=hash_password(mot_de_passe),
    nom="Test", prenom="StocksE2E", actif=True,
)
db.add(utilisateur)
db.flush()

entreprise = Entreprise(raison_sociale=f"Entreprise Stocks E2E {suffixe}")
db.add(entreprise)
db.flush()

role = Role(code=f"role_stocks_e2e_{suffixe}", libelle="Rôle stocks e2e")
db.add(role)
db.flush()
codes = [
    "article.consulter", "article.creer", "article.modifier", "article.archiver",
    "mouvement_stock.consulter", "mouvement_stock.creer",
    "compte.consulter", "journal.consulter",
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

# Compte de stock (classe 3) propre à l'entreprise, numéro distinct des
# comptes globaux déjà seedés par d'autres sessions (voir la note du 409
# rencontré pendant les tests comptabilité : la vérification d'unicité est
# faite au niveau service, sur le référentiel global + les extensions).
compte_stock = Compte(
    entreprise_id=entreprise.id, numero="355500", libelle="Stock de marchandises E2E",
    classe=3, lettrable=False, est_collectif=False, actif=True,
)
db.add(compte_stock)

compte_contrepartie = Compte(
    entreprise_id=entreprise.id, numero="603500", libelle="Achats de marchandises E2E",
    classe=6, lettrable=False, est_collectif=False, actif=True,
)
db.add(compte_contrepartie)

journal = Journal(entreprise_id=entreprise.id, code="OD-STK", libelle="Opérations diverses stocks", type_journal="operations_diverses", actif=True)
db.add(journal)

exercice = Exercice(date_debut=date(2026, 1, 1), date_fin=date(2026, 12, 31), statut="ouvert", entreprise_id=entreprise.id)
db.add(exercice)
db.commit()

print("email:", email)
print("mot_de_passe:", mot_de_passe)
print("entreprise_id:", entreprise.id)
print("compte_stock_numero:", compte_stock.numero)
print("compte_contrepartie_numero:", compte_contrepartie.numero)
print("journal_code:", journal.code)