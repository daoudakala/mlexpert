import uuid

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.main import app  # noqa
from app.modules.utilisateurs.models import Utilisateur
from app.modules.entreprises.models import Entreprise
from app.modules.droits.models import Role, RolePermission, Permission, Affectation
from app.modules.documents.service import DocumentDepot, ServiceDocuments

db = SessionLocal()

suffixe = uuid.uuid4().hex[:6]

# --- Utilisateur cabinet : permissions internes + portail_client.traiter ---
email_cabinet = f"portail.cabinet.{suffixe}@example.com"
mot_de_passe_cabinet = "MotDePasseCabinetE2E!2026"
utilisateur_cabinet = Utilisateur(
    email=email_cabinet, mot_de_passe_hash=hash_password(mot_de_passe_cabinet),
    nom="Test", prenom="CabinetE2E", actif=True,
)
db.add(utilisateur_cabinet)

# --- Utilisateur client : UNIQUEMENT des permissions portail_client.* ---
email_client = f"portail.client.{suffixe}@example.com"
mot_de_passe_client = "MotDePasseClientE2E!2026"
utilisateur_client = Utilisateur(
    email=email_client, mot_de_passe_hash=hash_password(mot_de_passe_client),
    nom="Test", prenom="ClientE2E", actif=True,
)
db.add(utilisateur_client)
db.flush()

entreprise = Entreprise(raison_sociale=f"Entreprise Portail Client E2E {suffixe}")
db.add(entreprise)
db.flush()

role_cabinet = Role(code=f"role_cabinet_e2e_{suffixe}", libelle="Rôle cabinet e2e")
db.add(role_cabinet)
db.flush()
codes_cabinet = [
    "document.consulter", "document.creer", "document.modifier",
    "portail_client.consulter", "portail_client.traiter",
]
for code in codes_cabinet:
    perm = db.query(Permission).filter_by(code=code).first()
    if perm is None:
        perm = Permission(code=code, libelle=code)
        db.add(perm)
        db.flush()
    db.add(RolePermission(role_id=role_cabinet.id, permission_id=perm.id))

role_client = Role(code=f"role_client_e2e_{suffixe}", libelle="Rôle client e2e")
db.add(role_client)
db.flush()
codes_client = ["portail_client.consulter", "portail_client.demander"]
for code in codes_client:
    perm = db.query(Permission).filter_by(code=code).first()
    if perm is None:
        perm = Permission(code=code, libelle=code)
        db.add(perm)
        db.flush()
    db.add(RolePermission(role_id=role_client.id, permission_id=perm.id))
db.flush()

db.add(Affectation(utilisateur_id=utilisateur_cabinet.id, entreprise_id=entreprise.id, role_id=role_cabinet.id))
db.add(Affectation(utilisateur_id=utilisateur_client.id, entreprise_id=entreprise.id, role_id=role_client.id))
db.flush()

# Un document déjà déposé ET rendu visible client, pour que le cabinet
# puisse immédiatement traiter une demande pendant le test.
service_documents = ServiceDocuments(db, entreprise.id)
document = service_documents.deposer_document(
    DocumentDepot(
        categorie="Bilan",
        nom_fichier="bilan_2026_e2e.txt",
        type_mime="text/plain",
        contenu=b"Contenu de test du bilan E2E portail client",
        description="Bilan annuel",
    ),
    auteur_id=utilisateur_cabinet.id,
)
service_documents.definir_visibilite_client(document.id, visible_client=True, auteur_id=utilisateur_cabinet.id)

db.commit()

print("email_cabinet:", email_cabinet)
print("mot_de_passe_cabinet:", mot_de_passe_cabinet)
print("email_client:", email_client)
print("mot_de_passe_client:", mot_de_passe_client)
print("entreprise_id:", entreprise.id)
print("document_nom:", document.nom_fichier)