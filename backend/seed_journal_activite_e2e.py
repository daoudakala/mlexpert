import uuid
from datetime import date
from decimal import Decimal

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.main import app  # noqa
from app.modules.utilisateurs.models import Utilisateur
from app.modules.entreprises.models import Entreprise
from app.modules.droits.models import Role, RolePermission, Permission, Affectation
from app.modules.comptabilite.models import Compte, Journal
from app.modules.comptabilite.service import LigneSaisie, ServiceComptabilite
from app.modules.exercices.models import Exercice

db = SessionLocal()

suffixe = uuid.uuid4().hex[:6]
email = f"journalactivite.e2e.{suffixe}@example.com"
mot_de_passe = "MotDePasseJournalActiviteE2E!2026"

utilisateur = Utilisateur(
    email=email, mot_de_passe_hash=hash_password(mot_de_passe),
    nom="Test", prenom="JournalActiviteE2E", actif=True,
)
db.add(utilisateur)
db.flush()

entreprise = Entreprise(raison_sociale=f"Entreprise Journal Activite E2E {suffixe}")
db.add(entreprise)
db.flush()

role = Role(code=f"role_journalactivite_e2e_{suffixe}", libelle="Rôle journal activité e2e")
db.add(role)
db.flush()
codes = [
    "journal_activite.consulter", "ecriture.consulter", "ecriture.creer", "ecriture.valider",
    "compte.consulter", "journal.consulter", "exercice.consulter",
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

compte_banque = Compte(entreprise_id=entreprise.id, numero="521000", libelle="Banque E2E", classe=5, lettrable=False, est_collectif=False, actif=True)
compte_produit = Compte(entreprise_id=entreprise.id, numero="706500", libelle="Prestations E2E", classe=7, lettrable=False, est_collectif=False, actif=True)
db.add_all([compte_banque, compte_produit])

journal = Journal(entreprise_id=entreprise.id, code="OD-JA", libelle="Opérations diverses journal activité", type_journal="operations_diverses", actif=True)
db.add(journal)

exercice = Exercice(date_debut=date(2026, 1, 1), date_fin=date(2026, 12, 31), statut="ouvert", entreprise_id=entreprise.id)
db.add(exercice)
db.flush()

# Une écriture créée PUIS validée : deux entrées de journal distinctes
# (module="comptabilite", type_action="creer" puis "valider") pour que la
# page de recherche ait de quoi filtrer.
service = ServiceComptabilite(db, entreprise.id)
ecriture = service.creer_ecriture(
    auteur_id=utilisateur.id,
    journal_id=journal.id,
    exercice_id=exercice.id,
    date_ecriture=date(2026, 3, 1),
    libelle="Prestation facturée (journal activité E2E)",
    lignes=[
        LigneSaisie(compte_id=compte_banque.id, debit=Decimal("500000"), credit=Decimal("0")),
        LigneSaisie(compte_id=compte_produit.id, debit=Decimal("0"), credit=Decimal("500000")),
    ],
)
service.valider_ecriture(ecriture.id, auteur_id=utilisateur.id)

db.commit()

print("email:", email)
print("mot_de_passe:", mot_de_passe)
print("entreprise_id:", entreprise.id)
print("ecriture_id:", ecriture.id)