"""Crée deux comptes collectifs (client + fournisseur) sur "Entreprise de
test" (celle créée par creer_compte_test_complet.py), pour pouvoir tester
le formulaire de création d'un tiers sans liste déroulante vide.

Usage (depuis backend/, avec le venv actif) :
    python creer_comptes_collectifs_test.py
"""
from app.core.database import SessionLocal
from app.main import app  # noqa: importe transitivement tous les modèles
from app.modules.entreprises.models import Entreprise
from app.modules.comptabilite.models import Compte

db = SessionLocal()

entreprise = db.query(Entreprise).filter_by(raison_sociale="Entreprise de test").first()
if entreprise is None:
    raise SystemExit("Entreprise de test introuvable — lance d'abord creer_compte_test_complet.py")

for numero, libelle in [("411000", "Clients"), ("401000", "Fournisseurs")]:
    existant = (
        db.query(Compte)
        .filter_by(entreprise_id=entreprise.id, numero=numero)
        .first()
    )
    if existant is not None:
        print(f"Compte {numero} déjà existant, ignoré")
        continue
    compte = Compte(
        numero=numero, libelle=libelle, classe=4,
        lettrable=True, est_collectif=True, actif=True,
        entreprise_id=entreprise.id,
    )
    db.add(compte)
    print(f"Compte {numero} — {libelle} créé")

db.commit()