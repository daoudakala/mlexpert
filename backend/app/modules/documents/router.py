"""Routes HTTP du module documents.

Toutes les routes sont entreprise-scopées
(`/documents/entreprises/{entreprise_id}/...`), protégées par les
permissions `document.*` (`exiger_permission`).

Le dépôt (`POST .../documents`) est un upload multipart (`UploadFile` +
`Form(...)`), pas un corps JSON — voir la note de tête de fichier de
`schemas.py`. Le téléchargement (`GET .../telecharger`) renvoie le
contenu brut avec les en-têtes `Content-Type`/`Content-Disposition`
plutôt qu'un JSON, sur le modèle de tout endpoint de téléchargement de
fichier.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import ContexteEntreprise, exiger_permission
from app.core.database import get_db
from app.modules.documents.models import CategorieDocument
from app.modules.documents.schemas import DocumentLecture, DocumentMiseAJour, DocumentRattachementEcriture
from app.modules.documents.service import DocumentDepot, ServiceDocuments

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "/entreprises/{entreprise_id}/documents",
    response_model=DocumentLecture,
    status_code=status.HTTP_201_CREATED,
)
def deposer_document(
    entreprise_id: uuid.UUID,
    fichier: UploadFile = File(...),
    categorie: CategorieDocument = Form(...),
    description: str | None = Form(default=None, max_length=500),
    date_document: date | None = Form(default=None),
    date_expiration: date | None = Form(default=None),
    exercice_id: uuid.UUID | None = Form(default=None),
    ecriture_id: uuid.UUID | None = Form(default=None),
    contexte: ContexteEntreprise = Depends(exiger_permission("document.creer")),
    db: Session = Depends(get_db),
) -> DocumentLecture:
    service = ServiceDocuments(db, contexte.entreprise_id)
    document = service.deposer_document(
        DocumentDepot(
            categorie=categorie.value,
            nom_fichier=fichier.filename or "sans_nom",
            type_mime=fichier.content_type or "application/octet-stream",
            contenu=fichier.file.read(),
            description=description,
            date_document=date_document,
            date_expiration=date_expiration,
            exercice_id=exercice_id,
            ecriture_id=ecriture_id,
        ),
        auteur_id=contexte.utilisateur_id,
    )
    db.commit()
    return DocumentLecture.model_validate(document)


@router.get(
    "/entreprises/{entreprise_id}/documents",
    response_model=list[DocumentLecture],
)
def lister_documents(
    entreprise_id: uuid.UUID,
    categorie: str | None = None,
    exercice_id: uuid.UUID | None = None,
    dossier_permanent_seulement: bool = False,
    ecriture_id: uuid.UUID | None = None,
    contexte: ContexteEntreprise = Depends(exiger_permission("document.consulter")),
    db: Session = Depends(get_db),
) -> list[DocumentLecture]:
    service = ServiceDocuments(db, contexte.entreprise_id)
    documents = service.lister_documents(
        categorie=categorie,
        exercice_id=exercice_id,
        dossier_permanent_seulement=dossier_permanent_seulement,
        ecriture_id=ecriture_id,
    )
    return [DocumentLecture.model_validate(d) for d in documents]


@router.get(
    "/entreprises/{entreprise_id}/documents/{document_id}",
    response_model=DocumentLecture,
)
def lire_document(
    entreprise_id: uuid.UUID,
    document_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("document.consulter")),
    db: Session = Depends(get_db),
) -> DocumentLecture:
    service = ServiceDocuments(db, contexte.entreprise_id)
    return DocumentLecture.model_validate(service.obtenir_document(document_id))


@router.get("/entreprises/{entreprise_id}/documents/{document_id}/telecharger")
def telecharger_document(
    entreprise_id: uuid.UUID,
    document_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("document.consulter")),
    db: Session = Depends(get_db),
) -> Response:
    service = ServiceDocuments(db, contexte.entreprise_id)
    document = service.obtenir_document(document_id)
    return Response(
        content=document.contenu,
        media_type=document.type_mime,
        headers={"Content-Disposition": f'attachment; filename="{document.nom_fichier}"'},
    )


@router.patch(
    "/entreprises/{entreprise_id}/documents/{document_id}",
    response_model=DocumentLecture,
)
def modifier_document(
    entreprise_id: uuid.UUID,
    document_id: uuid.UUID,
    donnees: DocumentMiseAJour,
    contexte: ContexteEntreprise = Depends(exiger_permission("document.modifier")),
    db: Session = Depends(get_db),
) -> DocumentLecture:
    service = ServiceDocuments(db, contexte.entreprise_id)
    document = service.modifier_document(
        document_id,
        auteur_id=contexte.utilisateur_id,
        categorie=donnees.categorie.value if donnees.categorie is not None else None,
        description=donnees.description,
        date_document=donnees.date_document,
        date_expiration=donnees.date_expiration,
    )
    db.commit()
    return DocumentLecture.model_validate(document)


@router.post(
    "/entreprises/{entreprise_id}/documents/{document_id}/visibilite-client",
    response_model=DocumentLecture,
)
def definir_visibilite_client(
    entreprise_id: uuid.UUID,
    document_id: uuid.UUID,
    visible_client: bool,
    contexte: ContexteEntreprise = Depends(exiger_permission("document.modifier")),
    db: Session = Depends(get_db),
) -> DocumentLecture:
    service = ServiceDocuments(db, contexte.entreprise_id)
    document = service.definir_visibilite_client(
        document_id, visible_client=visible_client, auteur_id=contexte.utilisateur_id
    )
    db.commit()
    return DocumentLecture.model_validate(document)


@router.post(
    "/entreprises/{entreprise_id}/documents/{document_id}/client-rattache",
    response_model=DocumentLecture,
)
def definir_client_rattache(
    entreprise_id: uuid.UUID,
    document_id: uuid.UUID,
    tiers_id: uuid.UUID | None = None,
    contexte: ContexteEntreprise = Depends(exiger_permission("document.modifier")),
    db: Session = Depends(get_db),
) -> DocumentLecture:
    """Restreint ce document (déjà `visible_client`) à UN client précis, ou
    retire la restriction si `tiers_id` est omis — voir
    `ServiceDocuments.definir_client_rattache` (Étape 6)."""
    service = ServiceDocuments(db, contexte.entreprise_id)
    document = service.definir_client_rattache(
        document_id, tiers_id=tiers_id, auteur_id=contexte.utilisateur_id
    )
    db.commit()
    return DocumentLecture.model_validate(document)


@router.post(
    "/entreprises/{entreprise_id}/documents/{document_id}/rattacher-ecriture",
    response_model=DocumentLecture,
)
def rattacher_ecriture(
    entreprise_id: uuid.UUID,
    document_id: uuid.UUID,
    donnees: DocumentRattachementEcriture,
    contexte: ContexteEntreprise = Depends(exiger_permission("document.modifier")),
    db: Session = Depends(get_db),
) -> DocumentLecture:
    service = ServiceDocuments(db, contexte.entreprise_id)
    document = service.rattacher_ecriture(
        document_id, ecriture_id=donnees.ecriture_id, auteur_id=contexte.utilisateur_id
    )
    db.commit()
    return DocumentLecture.model_validate(document)


@router.post(
    "/entreprises/{entreprise_id}/documents/{document_id}/detacher-ecriture",
    response_model=DocumentLecture,
)
def detacher_ecriture(
    entreprise_id: uuid.UUID,
    document_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("document.modifier")),
    db: Session = Depends(get_db),
) -> DocumentLecture:
    service = ServiceDocuments(db, contexte.entreprise_id)
    document = service.detacher_ecriture(document_id, auteur_id=contexte.utilisateur_id)
    db.commit()
    return DocumentLecture.model_validate(document)


@router.post(
    "/entreprises/{entreprise_id}/documents/{document_id}/supprimer",
    status_code=status.HTTP_204_NO_CONTENT,
)
def supprimer_document(
    entreprise_id: uuid.UUID,
    document_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("document.supprimer")),
    db: Session = Depends(get_db),
) -> None:
    service = ServiceDocuments(db, contexte.entreprise_id)
    service.supprimer_document(document_id, auteur_id=contexte.utilisateur_id)
    db.commit()