"""Routes HTTP du module portail_client.

Toutes les routes sont entreprise-scopées
(`/portail-client/entreprises/{entreprise_id}/...`), protégées par les
permissions `portail_client.*` (`exiger_permission`).

Convention de permission : `demander` (créer une demande, côté client),
`consulter` (lire demandes/documents visibles, cabinet ET client) et
`traiter` (clore une demande — traitement ou refus, réservé au cabinet).

`mes_demandes_seulement` sur le listing des demandes : un utilisateur
client ne devrait voir que les siennes, un collaborateur du cabinet
toutes celles de l'entreprise — ce module ne distingue pas les deux par
le rôle (voir `service.py`), donc c'est ce paramètre, positionné côté
client par le frontend, qui fait la restriction plutôt qu'une inspection
du rôle de l'appelant.
"""

import uuid

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import ContexteEntreprise, exiger_permission
from app.core.database import get_db
from app.modules.documents.schemas import DocumentLecture
from app.modules.portail_client.schemas import (
    CommentaireDemandeCreation,
    CommentaireDemandeLecture,
    DemandeDocumentCreation,
    DemandeDocumentLecture,
    DemandeDocumentRefus,
    DemandeDocumentTraitement,
)
from app.modules.portail_client.service import ServicePortailClient

router = APIRouter(prefix="/portail-client", tags=["Portail client"])


# --- Documents partagés avec le client ---------------------------------------


@router.get(
    "/entreprises/{entreprise_id}/documents",
    response_model=list[DocumentLecture],
)
def lister_documents_visibles(
    entreprise_id: uuid.UUID,
    categorie: str | None = None,
    exercice_id: uuid.UUID | None = None,
    dossier_permanent_seulement: bool = False,
    contexte: ContexteEntreprise = Depends(exiger_permission("portail_client.consulter")),
    db: Session = Depends(get_db),
) -> list[DocumentLecture]:
    service = ServicePortailClient(db, contexte.entreprise_id)
    documents = service.lister_documents_visibles(
        categorie=categorie, exercice_id=exercice_id,
        dossier_permanent_seulement=dossier_permanent_seulement,
        tiers_id_scope=contexte.affectation.tiers_id,
    )
    return [DocumentLecture.model_validate(d) for d in documents]


@router.get("/entreprises/{entreprise_id}/documents/{document_id}/telecharger")
def telecharger_document_visible(
    entreprise_id: uuid.UUID,
    document_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("portail_client.consulter")),
    db: Session = Depends(get_db),
) -> Response:
    service = ServicePortailClient(db, contexte.entreprise_id)
    document = service.obtenir_document_visible(
        document_id, tiers_id_scope=contexte.affectation.tiers_id
    )
    return Response(
        content=document.contenu,
        media_type=document.type_mime,
        headers={"Content-Disposition": f'attachment; filename="{document.nom_fichier}"'},
    )


# --- Demandes de documents ---------------------------------------------------


@router.post(
    "/entreprises/{entreprise_id}/demandes",
    response_model=DemandeDocumentLecture,
    status_code=status.HTTP_201_CREATED,
)
def creer_demande(
    entreprise_id: uuid.UUID,
    donnees: DemandeDocumentCreation,
    contexte: ContexteEntreprise = Depends(exiger_permission("portail_client.demander")),
    db: Session = Depends(get_db),
) -> DemandeDocumentLecture:
    service = ServicePortailClient(db, contexte.entreprise_id)
    demande = service.creer_demande(
        demandeur_id=contexte.utilisateur_id, libelle=donnees.libelle, description=donnees.description
    )
    db.commit()
    return DemandeDocumentLecture.model_validate(demande)


@router.get(
    "/entreprises/{entreprise_id}/demandes",
    response_model=list[DemandeDocumentLecture],
)
def lister_demandes(
    entreprise_id: uuid.UUID,
    statut: str | None = None,
    mes_demandes_seulement: bool = False,
    contexte: ContexteEntreprise = Depends(exiger_permission("portail_client.consulter")),
    db: Session = Depends(get_db),
) -> list[DemandeDocumentLecture]:
    service = ServicePortailClient(db, contexte.entreprise_id)
    demandeur_id = contexte.utilisateur_id if mes_demandes_seulement else None
    return [
        DemandeDocumentLecture.model_validate(d)
        for d in service.lister_demandes(demandeur_id=demandeur_id, statut=statut)
    ]


@router.get(
    "/entreprises/{entreprise_id}/demandes/{demande_id}",
    response_model=DemandeDocumentLecture,
)
def lire_demande(
    entreprise_id: uuid.UUID,
    demande_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("portail_client.consulter")),
    db: Session = Depends(get_db),
) -> DemandeDocumentLecture:
    service = ServicePortailClient(db, contexte.entreprise_id)
    return DemandeDocumentLecture.model_validate(service.obtenir_demande(demande_id))


@router.post(
    "/entreprises/{entreprise_id}/demandes/{demande_id}/traiter",
    response_model=DemandeDocumentLecture,
)
def traiter_demande(
    entreprise_id: uuid.UUID,
    demande_id: uuid.UUID,
    donnees: DemandeDocumentTraitement,
    contexte: ContexteEntreprise = Depends(exiger_permission("portail_client.traiter")),
    db: Session = Depends(get_db),
) -> DemandeDocumentLecture:
    service = ServicePortailClient(db, contexte.entreprise_id)
    demande = service.traiter_demande(
        demande_id, auteur_id=contexte.utilisateur_id, document_id=donnees.document_id
    )
    db.commit()
    return DemandeDocumentLecture.model_validate(demande)


@router.post(
    "/entreprises/{entreprise_id}/demandes/{demande_id}/refuser",
    response_model=DemandeDocumentLecture,
)
def refuser_demande(
    entreprise_id: uuid.UUID,
    demande_id: uuid.UUID,
    donnees: DemandeDocumentRefus,
    contexte: ContexteEntreprise = Depends(exiger_permission("portail_client.traiter")),
    db: Session = Depends(get_db),
) -> DemandeDocumentLecture:
    service = ServicePortailClient(db, contexte.entreprise_id)
    demande = service.refuser_demande(demande_id, auteur_id=contexte.utilisateur_id, motif=donnees.motif)
    db.commit()
    return DemandeDocumentLecture.model_validate(demande)


# --- Commentaires (messagerie contextualisée) ---------------------------------


@router.get(
    "/entreprises/{entreprise_id}/demandes/{demande_id}/commentaires",
    response_model=list[CommentaireDemandeLecture],
)
def lister_commentaires(
    entreprise_id: uuid.UUID,
    demande_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("portail_client.consulter")),
    db: Session = Depends(get_db),
) -> list[CommentaireDemandeLecture]:
    service = ServicePortailClient(db, contexte.entreprise_id)
    return [
        CommentaireDemandeLecture.model_validate(c) for c in service.lister_commentaires(demande_id)
    ]


@router.post(
    "/entreprises/{entreprise_id}/demandes/{demande_id}/commentaires",
    response_model=CommentaireDemandeLecture,
    status_code=status.HTTP_201_CREATED,
)
def ajouter_commentaire(
    entreprise_id: uuid.UUID,
    demande_id: uuid.UUID,
    donnees: CommentaireDemandeCreation,
    contexte: ContexteEntreprise = Depends(exiger_permission("portail_client.consulter")),
    db: Session = Depends(get_db),
) -> CommentaireDemandeLecture:
    service = ServicePortailClient(db, contexte.entreprise_id)
    commentaire = service.ajouter_commentaire(
        demande_id, auteur_id=contexte.utilisateur_id, message=donnees.message
    )
    db.commit()
    return CommentaireDemandeLecture.model_validate(commentaire)