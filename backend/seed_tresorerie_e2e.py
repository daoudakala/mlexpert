import uuid
from datetime import date

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.main import app  # noqa
from app.modules.utilisateurs.models import Utilisateur
from app.modules.entreprises.models import Entreprise
from app.modules.droits.models import Role, RolePermission, Permission, Affectation
from app.modules.comptabilite.models import Compte, Journal, TypeJournal
from app.modules.comptabilite.service import ServiceComptabilite, LigneSaisie
from app.modules.exercices.models import Exercice

db = SessionLocal()

suffixe = uuid.uuid4().hex[:6]
email = f"tresorerie.e2e.{suffixe}@example.com"
mot_de_passe = "MotDePasseTresorerieE2E!2026"

utilisateur = Utilisateur(
    email=email, mot_de_passe_hash=hash_password(mot_de_passe),
    nom="Test", prenom="TresorerieE2E", actif=True,
)
db.add(utilisateur)
db.flush()

entreprise = Entreprise(raison_sociale=f"Entreprise Tresorerie E2E {suffixe}")
db.add(entreprise)
db.flush()

role = Role(code=f"role_tresorerie_e2e_{suffixe}", libelle="Rôle trésorerie e2e")
db.add(role)
db.flush()
codes = [
    "compte_bancaire.consulter", "compte_bancaire.creer", "compte_bancaire.archiver",
    "releve.consulter", "releve.creer", "releve.modifier", "releve.supprimer",
    "rapprochement.creer", "rapprochement.annuler",
    "compte.consulter", "journal.consulter",
    "ecriture.creer", "ecriture.consulter", "ecriture.valider",
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

journal_banque = Journal(
    code="BQ1", libelle="Banque SGBCI", type_journal=TypeJournal.BANQUE.value,
    actif=True, entreprise_id=entreprise.id,
)
journal_od = Journal(
    code="OD1", libelle="Opérations diverses", type_journal=TypeJournal.OPERATIONS_DIVERSES.value,
    actif=True, entreprise_id=entreprise.id,
)
db.add(journal_banque)
db.add(journal_od)
db.flush()

compte_banque = Compte(
    numero="521000", libelle="Banque SGBCI", classe=5, lettrable=False, est_collectif=False, actif=True,
    entreprise_id=entreprise.id,
)
compte_contrepartie = Compte(
    numero="701000", libelle="Ventes", classe=7, lettrable=False, est_collectif=False, actif=True,
    entreprise_id=entreprise.id,
)
db.add(compte_banque)
db.add(compte_contrepartie)
db.flush()

exercice = Exercice(
    date_debut=date(2026, 1, 1), date_fin=date(2026, 12, 31), statut="ouvert",
    entreprise_id=entreprise.id,
)
db.add(exercice)
db.flush()
db.commit()

# Une écriture avec une ligne sur le compte banque, pas encore lettrée —
# servira de candidate au rapprochement.
service = ServiceComptabilite(db, entreprise.id)
ecriture = service.creer_ecriture(
    auteur_id=utilisateur.id,
    journal_id=journal_od.id,
    exercice_id=exercice.id,
    date_ecriture=date(2026, 3, 15),
    libelle="Encaissement client",
    reference_piece=None,
    lignes=[
        LigneSaisie(compte_id=compte_banque.id, debit=50000, credit=0, tiers_id=None, libelle="Encaissement"),
        LigneSaisie(compte_id=compte_contrepartie.id, debit=0, credit=50000, tiers_id=None, libelle="Encaissement"),
    ],
)
db.commit()

print("email:", email)
print("mot_de_passe:", mot_de_passe)
print("entreprise_id:", entreprise.id)
print("journal_banque_id:", journal_banque.id)
print("compte_banque_id:", compte_banque.id)
print("ecriture_id:", ecriture.id)