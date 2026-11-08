"""Point d'entrée de l'application MLexpert.

Monte tous les routers, enregistre les gestionnaires d'erreurs et la
politique CORS. Importer chaque router ici a un effet de bord voulu :
cela importe transitivement tous les modèles SQLAlchemy (router → service
→ repository → models), ce qui est nécessaire pour que `Base.metadata`
connaisse l'ensemble des tables avant qu'Alembic ou qu'une création de
schéma ne s'appuie dessus.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.exceptions import enregistrer_gestionnaires_erreurs
from app.modules.auth.router import router as router_auth
from app.modules.comptabilite.router import router as router_comptabilite
from app.modules.dashboards.router import router as router_dashboards
from app.modules.documents.router import router as router_documents
from app.modules.droits.router import router as router_droits
from app.modules.entreprises.router import router as router_entreprises
from app.modules.exercices.router import router as router_exercices
from app.modules.immobilisations.router import router as router_immobilisations
from app.modules.interlocuteurs.router import router as router_interlocuteurs
from app.modules.journal_activite.router import router as router_journal_activite
from app.modules.notifications.router import router as router_notifications
from app.modules.paie.router import router as router_paie
from app.modules.portail_client.router import router as router_portail_client
from app.modules.stocks.router import router as router_stocks
from app.modules.tiers.router import router as router_tiers
from app.modules.tresorerie.router import router as router_tresorerie
from app.modules.provisions.router import router as router_provisions
from app.modules.regularisations.router import router as router_regularisations
from app.modules.utilisateurs.router import router as router_utilisateurs

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    # La doc interactive n'a pas sa place en production (cahier, section 27 :
    # exposer le moins possible de surface au public).
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    openapi_url="/openapi.json" if not settings.is_production else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

enregistrer_gestionnaires_erreurs(app)

# L'ordre d'inclusion n'a aucun effet fonctionnel (chaque router porte son
# propre préfixe), il suit seulement l'ordre de dépendance du socle pour
# rester lisible : référentiels d'abord, périmètre ensuite, traçabilité et
# authentification en dernier.
app.include_router(router_utilisateurs)
app.include_router(router_droits)
app.include_router(router_entreprises)
app.include_router(router_exercices)
app.include_router(router_comptabilite)
app.include_router(router_dashboards)
app.include_router(router_tiers)
app.include_router(router_tresorerie)
app.include_router(router_immobilisations)
app.include_router(router_documents)
app.include_router(router_interlocuteurs)
app.include_router(router_portail_client)
app.include_router(router_paie)
app.include_router(router_stocks)
app.include_router(router_journal_activite)
app.include_router(router_notifications)
app.include_router(router_provisions)
app.include_router(router_regularisations)
app.include_router(router_auth)


@app.get("/sante", tags=["Santé"])
def sante() -> dict[str, str]:
    """Vérification de disponibilité (sondes de supervision, section 30 :
    "Service stable et supervision des incidents"). Ne touche pas la base
    de données : un 200 ici signifie seulement que le processus répond."""
    return {"statut": "ok", "environnement": settings.environment}
