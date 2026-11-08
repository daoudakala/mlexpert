"""Règles métier du module documents.

`ServiceDocuments` : construit avec `(db, entreprise_id)`, comme
`ServiceTresorerie`/`ServiceImmobilisations`.

Le contenu d'un document est immuable une fois déposé : `modifier_document`
ne touche jamais `contenu`/`nom_fichier`/`type_mime`/`taille_octets`, sur le
même principe que `tiers` n'autorise pas de modifier `code` par la route de
mise à jour générale — remplacer le fichier n'est pas construit à ce stade
(pas de notion de "version" d'un document) ; un remplacement se ferait en
supprimant et en redéposant, pas en éditant en place.

`TAILLE_MAXIMALE_OCTETS` (20 Mo) est une limite raisonnable posée par le
service, pas par le cahier des charges — assumée pour ce premier passage,
comme le stockage en base (voir `models.py`).
"""

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.core.exceptions import RessourceIntrouvable, ValidationMetier
from app.modules.comptabilite.repository import RepositoryEcritures
from app.modules.documents.models import Document
from app.modules.documents.repository import RepositoryDocuments
from app.modules.exercices.repository import RepositoryExercice
from app.modules.journal_activite.models import TypeAction
from app.modules.journal_activite.service import ServiceJournalActivite
from app.modules.tiers.repository import RepositoryTiers

TAILLE_MAXIMALE_OCTETS = 20 * 1024 * 1024


@dataclass
class DocumentDepot:
    categorie: str
    nom_fichier: str
    type_mime: str
    contenu: bytes
    description: str | None = None
    date_document: date | None = None
    date_expiration: date | None = None
    exercice_id: uuid.UUID | None = None
    # Pièce justificative déposée directement en rattachement d'une écriture
    # déjà existante — voir la note de tête de fichier de `models.py`.
    ecriture_id: uuid.UUID | None = None


class ServiceDocuments:
    def __init__(self, db: Session, entreprise_id: uuid.UUID) -> None:
        self.db = db
        self.entreprise_id = entreprise_id
        self.documents = RepositoryDocuments(db, entreprise_id)
        self.exercices = RepositoryExercice(db, entreprise_id)
        self.ecritures = RepositoryEcritures(db, entreprise_id)
        self.tiers = RepositoryTiers(db, entreprise_id)
        self.journal_activite = ServiceJournalActivite(db)

    def deposer_document(self, donnees: DocumentDepot, *, auteur_id: uuid.UUID) -> Document:
        if not donnees.contenu:
            raise ValidationMetier("Le fichier déposé est vide.")
        if len(donnees.contenu) > TAILLE_MAXIMALE_OCTETS:
            raise ValidationMetier(
                f"Le fichier dépasse la taille maximale autorisée "
                f"({TAILLE_MAXIMALE_OCTETS // (1024 * 1024)} Mo)."
            )
        if donnees.exercice_id is not None and self.exercices.obtenir(donnees.exercice_id) is None:
            raise RessourceIntrouvable("Exercice introuvable.")
        if donnees.ecriture_id is not None and self.ecritures.obtenir(donnees.ecriture_id) is None:
            raise RessourceIntrouvable("Écriture introuvable.")

        document = Document(
            categorie=donnees.categorie,
            nom_fichier=donnees.nom_fichier,
            type_mime=donnees.type_mime,
            taille_octets=len(donnees.contenu),
            contenu=donnees.contenu,
            description=donnees.description,
            date_document=donnees.date_document,
            date_expiration=donnees.date_expiration,
            exercice_id=donnees.exercice_id,
            ecriture_id=donnees.ecriture_id,
            depose_par_id=auteur_id,
        )
        self.documents.ajouter(document)
        self.journal_activite.enregistrer(
            module="documents",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Document",
            objet_id=document.id,
            description=f"Dépôt du document '{donnees.nom_fichier}' ({donnees.categorie}).",
            valeurs_apres={"categorie": donnees.categorie, "nom_fichier": donnees.nom_fichier},
        )
        return document

    def modifier_document(
        self,
        document_id: uuid.UUID,
        *,
        auteur_id: uuid.UUID,
        categorie: str | None = None,
        description: str | None = None,
        date_document: date | None = None,
        date_expiration: date | None = None,
    ) -> Document:
        """Métadonnées uniquement — voir la note de tête de fichier sur
        l'immuabilité du contenu."""
        document = self._obtenir_ou_lever(document_id)
        if categorie is not None:
            document.categorie = categorie
        if description is not None:
            document.description = description
        if date_document is not None:
            document.date_document = date_document
        if date_expiration is not None:
            document.date_expiration = date_expiration
        self.db.flush()

        self.journal_activite.enregistrer(
            module="documents",
            type_action=TypeAction.MODIFIER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Document",
            objet_id=document.id,
            description=f"Modification des métadonnées du document '{document.nom_fichier}'.",
        )
        return document

    def definir_visibilite_client(
        self, document_id: uuid.UUID, *, visible_client: bool, auteur_id: uuid.UUID
    ) -> Document:
        """Décision explicite du cabinet de partager (ou non) ce document
        avec les utilisateurs clients — voir la note de tête de fichier de
        `models.py`. Action distincte de `modifier_document` : c'est une
        décision de partage, pas une correction de métadonnées."""
        document = self._obtenir_ou_lever(document_id)
        if document.visible_client == visible_client:
            raise ValidationMetier(
                "Ce document est déjà "
                + ("visible par les clients." if visible_client else "masqué aux clients.")
            )
        document.visible_client = visible_client
        self.db.flush()

        self.journal_activite.enregistrer(
            module="documents",
            type_action=TypeAction.MODIFIER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Document",
            objet_id=document.id,
            description=(
                f"Document '{document.nom_fichier}' "
                + ("rendu visible aux clients." if visible_client else "masqué aux clients.")
            ),
            valeurs_apres={"visible_client": visible_client},
        )
        return document

    def definir_client_rattache(
        self, document_id: uuid.UUID, *, tiers_id: uuid.UUID | None, auteur_id: uuid.UUID
    ) -> Document:
        """Restreint (ou retire la restriction sur) la visibilité client
        d'un document à UN `Tiers` précis de cette entreprise — voir la
        note de tête de `models.py`. Décision distincte de
        `definir_visibilite_client` : un document peut être `visible_client`
        pour tous (`tiers_id=None`, comportement historique) ou pour un
        seul client (`tiers_id` renseigné), indépendamment de QUAND il a
        été rendu visible."""
        document = self._obtenir_ou_lever(document_id)
        if tiers_id is not None and self.tiers.obtenir(tiers_id) is None:
            raise RessourceIntrouvable("Tiers introuvable pour cette entreprise.")

        document.tiers_id = tiers_id
        self.db.flush()

        self.journal_activite.enregistrer(
            module="documents",
            type_action=TypeAction.MODIFIER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Document",
            objet_id=document.id,
            description=(
                f"Document '{document.nom_fichier}' restreint au tiers {tiers_id}."
                if tiers_id is not None
                else f"Document '{document.nom_fichier}' n'est plus restreint à un tiers précis."
            ),
            valeurs_apres={"tiers_id": str(tiers_id) if tiers_id else None},
        )
        return document

    def rattacher_ecriture(
        self, document_id: uuid.UUID, *, ecriture_id: uuid.UUID, auteur_id: uuid.UUID
    ) -> Document:
        """Rattache un document déjà déposé à une écriture, comme pièce
        justificative — voir la note de tête de fichier de `models.py`.
        Librement refaisable : rattacher à une autre écriture remplace
        simplement le rattachement précédent, sans détacher explicitement
        d'abord."""
        document = self._obtenir_ou_lever(document_id)
        if self.ecritures.obtenir(ecriture_id) is None:
            raise RessourceIntrouvable("Écriture introuvable.")
        document.ecriture_id = ecriture_id
        self.db.flush()

        self.journal_activite.enregistrer(
            module="documents",
            type_action=TypeAction.MODIFIER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Document",
            objet_id=document.id,
            description=f"Document '{document.nom_fichier}' rattaché à une écriture.",
            valeurs_apres={"ecriture_id": str(ecriture_id)},
        )
        return document

    def detacher_ecriture(self, document_id: uuid.UUID, *, auteur_id: uuid.UUID) -> Document:
        document = self._obtenir_ou_lever(document_id)
        if document.ecriture_id is None:
            raise ValidationMetier("Ce document n'est rattaché à aucune écriture.")
        document.ecriture_id = None
        self.db.flush()

        self.journal_activite.enregistrer(
            module="documents",
            type_action=TypeAction.MODIFIER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Document",
            objet_id=document.id,
            description=f"Document '{document.nom_fichier}' détaché de son écriture.",
        )
        return document

    def supprimer_document(self, document_id: uuid.UUID, *, auteur_id: uuid.UUID) -> None:
        document = self._obtenir_ou_lever(document_id)
        self.db.delete(document)
        self.db.flush()
        self.journal_activite.enregistrer(
            module="documents",
            type_action=TypeAction.SUPPRIMER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Document",
            objet_id=document_id,
            description=f"Suppression du document '{document.nom_fichier}'.",
        )

    def obtenir_document(self, document_id: uuid.UUID) -> Document:
        return self._obtenir_ou_lever(document_id)

    def lister_documents(
        self,
        *,
        categorie: str | None = None,
        exercice_id: uuid.UUID | None = None,
        dossier_permanent_seulement: bool = False,
        visible_client_seulement: bool = False,
        ecriture_id: uuid.UUID | None = None,
    ) -> list[Document]:
        return self.documents.lister(
            categorie=categorie,
            exercice_id=exercice_id,
            dossier_permanent_seulement=dossier_permanent_seulement,
            visible_client_seulement=visible_client_seulement,
            ecriture_id=ecriture_id,
        )

    def lister_pour_ecriture(self, ecriture_id: uuid.UUID) -> list[Document]:
        return self.documents.lister_pour_ecriture(ecriture_id)

    def _obtenir_ou_lever(self, document_id: uuid.UUID) -> Document:
        document = self.documents.obtenir(document_id)
        if document is None:
            raise RessourceIntrouvable("Document introuvable.")
        return document