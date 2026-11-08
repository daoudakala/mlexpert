"""Seed pour le module paie : un utilisateur avec toutes les permissions
paie.* (+ comptabilite.* nécessaires à la génération d'écriture), une
entreprise, un exercice ouvert, un journal et des comptes comptables
(charge de salaire, dette CNPS, trésorerie pour le net à payer)."""

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
email = f"paie.e2e.{suffixe}@example.com"
mot_de_passe = "MotDePassePaieE2E!2026"

utilisateur = Utilisateur(
    email=email, mot_de_passe_hash=hash_password(mot_de_passe),
    nom="Test", prenom="PaieE2E", actif=True,
)
db.add(utilisateur)
db.flush()

entreprise = Entreprise(raison_sociale=f"Entreprise Paie E2E {suffixe}")
db.add(entreprise)
db.flush()

role = Role(code=f"role_paie_e2e_{suffixe}", libelle="Rôle paie e2e")
db.add(role)
db.flush()

codes = [
    "employe.consulter", "employe.creer", "employe.modifier", "employe.archiver",
    "rubrique_paie.consulter", "rubrique_paie.creer", "rubrique_paie.modifier", "rubrique_paie.archiver",
    "bulletin.consulter", "bulletin.creer", "bulletin.modifier", "bulletin.valider",
    "exercice.consulter", "journal.consulter", "compte.consulter", "ecriture.consulter",
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

compte_charge = Compte(entreprise_id=entreprise.id, numero="661000", libelle="Salaires E2E", classe=6, lettrable=False, est_collectif=False, actif=True)
compte_cnps = Compte(entreprise_id=entreprise.id, numero="431000", libelle="CNPS E2E", classe=4, lettrable=False, est_collectif=False, actif=True)
compte_banque = Compte(entreprise_id=entreprise.id, numero="521000", libelle="Banque E2E", classe=5, lettrable=False, est_collectif=False, actif=True)
db.add_all([compte_charge, compte_cnps, compte_banque])

journal = Journal(entreprise_id=entreprise.id, code="OD-PAIE", libelle="Opérations diverses paie", type_journal="operations_diverses", actif=True)
db.add(journal)

exercice = Exercice(date_debut=date(2026, 1, 1), date_fin=date(2026, 12, 31), statut="ouvert", entreprise_id=entreprise.id)
db.add(exercice)
db.flush()

db.commit()

print("email:", email)
print("mot_de_passe:", mot_de_passe)
print("entreprise_id:", entreprise.id)
print("exercice_id:", exercice.id)
print("compte_charge:", compte_charge.numero)
print("compte_cnps:", compte_cnps.numero)
print("compte_banque:", compte_banque.numero)
print("journal:", journal.code)
