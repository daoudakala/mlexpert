"""Règles métier du module portail_client.

`ServicePortailClient` : construit avec `(db, entreprise_id)`, comme les
autres services entreprise-scopés.

Pas de nouveau mécanisme d'authentification ni de notion d'utilisateur
"client" : un client est un `Utilisateur` classique, rattaché à
l'entreprise via une `Affectation` (module `droits`) portant un rôle aux
permissions volontairement limitées (ex. `portail_client.consulter`,
sans aucune des permissions internes `ecriture.*`/`compte.*`...). C'est
la configuration des rôles/permissions qui distingue un client d'un
collaborateur du cabinet, pas ce module.

Deux responsabilités bien séparées :

- Exposer en LECTURE SEULE les documents que le cabinet a explicitement
  rendus visibles (`Document.visible_client`, module `documents`) — un
  document non marqué reste invisible ici même si son `entreprise_id`
  correspond, quelle que soit la permission du client (voir
  `_obtenir_document_visible_ou_lever` : absence de distinction entre
  "n'existe pas" et "pas partagé", pour ne rien révéler d'un document
  interne).
- Gérer les demandes de documents (`DemandeDocument`) : un client
  demande, le cabinet traite (en liant un document DÉJÀ visible — le
  traitement d'une demande ne rend pas un document visible tout seul,
  ce sont deux décisions distinctes) ou refuse avec un motif.
- Porter le fil de commentaires (`CommentaireDemande`) rattaché à chaque
  demande — voir `ajouter_commentaire` pour la règle de notification :
  pas de notification "à l'aveugle" quand aucun destinataire n'est
  certain (demande pas encore prise en charge par un collaborateur).
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.exceptions import RessourceIntrouvable, ValidationMetier
from app.modules.documents.models import Document
from app.modules.documents.repository import RepositoryDocuments
from app.modules.journal_activite.models import TypeAction
from app.modules.journal_activite.service import ServiceJournalActivite
from app.modules.notifications.models import NiveauCriticite, TypeNotification
from app.modules.notifications.service import ServiceNotifications
from app.modules.portail_client.models import CommentaireDemande, DemandeDocument, StatutDemandeDocument
from app.modules.portail_client.repository import RepositoryCommentairesDemandes, RepositoryDemandesDocuments


class ServicePortailClient:
    def __init__(self, db: Session, entreprise_id: uuid.UUID) -> None:
        self.db = db
        self.entreprise_id = entreprise_id
        self.demandes = RepositoryDemandesDocuments(db, entreprise_id)
        self.commentaires = RepositoryCommentairesDemandes(db, entreprise_id)
        self.documents = RepositoryDocuments(db, entreprise_id)
        self.journal_activite = ServiceJournalActivite(db)
        self.notifications = ServiceNotifications(db, entreprise_id)

    # --- Documents partagés avec le client -----------------------------------

    def lister_documents_visibles(
        self,
        *,
        categorie: str | None = None,
        exercice_id: uuid.UUID | None = None,
        dossier_permanent_seulement: bool = False,
        tiers_id_scope: uuid.UUID | None = None,
    ) -> list[Document]:
        """`tiers_id_scope` (Étape 6) : à fournir quand l'appelant est un
        compte portail rattaché à un `Tiers` précis (`contexte.affectation.
        tiers_id`, voir `router.py`) — restreint alors aux documents non
        réservés à un autre client. `None` pour un collaborateur du
        cabinet (vue complète, comportement inchangé)."""
        return self.documents.lister(
            categorie=categorie,
            exercice_id=exercice_id,
            dossier_permanent_seulement=dossier_permanent_seulement,
            visible_client_seulement=True,
            tiers_id_scope=tiers_id_scope,
        )

    def obtenir_document_visible(
        self, document_id: uuid.UUID, *, tiers_id_scope: uuid.UUID | None = None
    ) -> Document:
        return self._obtenir_document_visible_ou_lever(document_id, tiers_id_scope=tiers_id_scope)

    # --- Demandes de documents -------------------------------------------------

    def creer_demande(
        self, *, demandeur_id: uuid.UUID, libelle: str, description: str | None = None
    ) -> DemandeDocument:
        demande = DemandeDocument(
            libelle=libelle,
            description=description,
            statut=StatutDemandeDocument.EN_ATTENTE.value,
            demandeur_id=demandeur_id,
        )
        self.demandes.ajouter(demande)
        self.journal_activite.enregistrer(
            module="portail_client",
            type_action=TypeAction.CREER,
            utilisateur_id=demandeur_id,
            entreprise_id=self.entreprise_id,
            type_objet="DemandeDocument",
            objet_id=demande.id,
            description=f"Demande de document : '{libelle}'.",
        )
        return demande

    def traiter_demande(
        self, demande_id: uuid.UUID, *, auteur_id: uuid.UUID, document_id: uuid.UUID
    ) -> DemandeDocument:
        demande = self._obtenir_demande_ou_lever(demande_id)
        self._verifier_en_attente(demande)
        # Le document doit déjà être marqué visible par le cabinet — traiter
        # une demande ne décide pas, en plus, de le partager (voir la note
        # de tête de fichier).
        self._obtenir_document_visible_ou_lever(document_id)

        demande.statut = StatutDemandeDocument.TRAITEE.value
        demande.document_id = document_id
        demande.traitee_par_id = auteur_id
        demande.traitee_le = datetime.now(UTC)
        self.db.flush()

        self.journal_activite.enregistrer(
            module="portail_client",
            type_action=TypeAction.MODIFIER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="DemandeDocument",
            objet_id=demande.id,
            description=f"Demande '{demande.libelle}' traitée.",
            valeurs_apres={"statut": StatutDemandeDocument.TRAITEE.value},
        )
        return demande

    def refuser_demande(self, demande_id: uuid.UUID, *, auteur_id: uuid.UUID, motif: str) -> DemandeDocument:
        demande = self._obtenir_demande_ou_lever(demande_id)
        self._verifier_en_attente(demande)

        demande.statut = StatutDemandeDocument.REFUSEE.value
        demande.reponse = motif
        demande.traitee_par_id = auteur_id
        demande.traitee_le = datetime.now(UTC)
        self.db.flush()

        self.journal_activite.enregistrer(
            module="portail_client",
            type_action=TypeAction.MODIFIER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="DemandeDocument",
            objet_id=demande.id,
            description=f"Demande '{demande.libelle}' refusée : {motif}",
            valeurs_apres={"statut": StatutDemandeDocument.REFUSEE.value},
        )
        return demande

    def obtenir_demande(self, demande_id: uuid.UUID) -> DemandeDocument:
        return self._obtenir_demande_ou_lever(demande_id)

    def lister_demandes(
        self, *, demandeur_id: uuid.UUID | None = None, statut: str | None = None
    ) -> list[DemandeDocument]:
        return self.demandes.lister(demandeur_id=demandeur_id, statut=statut)

    # --- Commentaires (messagerie contextualisée) -----------------------------

    def lister_commentaires(self, demande_id: uuid.UUID) -> list[CommentaireDemande]:
        self._obtenir_demande_ou_lever(demande_id)
        return self.commentaires.lister_pour_demande(demande_id)

    def ajouter_commentaire(
        self, demande_id: uuid.UUID, *, auteur_id: uuid.UUID, message: str
    ) -> CommentaireDemande:
        demande = self._obtenir_demande_ou_lever(demande_id)

        commentaire = CommentaireDemande(demande_id=demande_id, auteur_id=auteur_id, message=message)
        self.commentaires.ajouter(commentaire)
        self.journal_activite.enregistrer(
            module="portail_client",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="CommentaireDemande",
            objet_id=commentaire.id,
            description=f"Commentaire ajouté sur la demande '{demande.libelle}'.",
        )

        # Qui notifier dépend de qui écrit. Un collaborateur du cabinet a
        # toujours un destinataire certain : le client demandeur. Un
        # client, en revanche, n'a un destinataire certain que si un
        # collaborateur s'est déjà approprié la demande (`traitee_par_id`)
        # — sinon on ne notifie personne plutôt que de deviner (voir note
        # de tête de fichier).
        if auteur_id == demande.demandeur_id:
            if demande.traitee_par_id is not None:
                self.notifications.creer(
                    destinataire_id=demande.traitee_par_id,
                    type_notification=TypeNotification.MESSAGE_PORTAIL.value,
                    niveau_criticite=NiveauCriticite.INFO.value,
                    titre="Nouveau message sur une demande client",
                    message=f"Le client a commenté la demande '{demande.libelle}'.",
                    type_objet="DemandeDocument",
                    objet_id=demande.id,
                )
        else:
            self.notifications.creer(
                destinataire_id=demande.demandeur_id,
                type_notification=TypeNotification.MESSAGE_PORTAIL.value,
                niveau_criticite=NiveauCriticite.INFO.value,
                titre="Nouveau message du cabinet",
                message=f"Le cabinet a répondu sur la demande '{demande.libelle}'.",
                type_objet="DemandeDocument",
                objet_id=demande.id,
            )

        return commentaire

    # --- Aides internes -------------------------------------------------------

    def _obtenir_demande_ou_lever(self, demande_id: uuid.UUID) -> DemandeDocument:
        demande = self.demandes.obtenir(demande_id)
        if demande is None:
            raise RessourceIntrouvable("Demande introuvable.")
        return demande

    def _verifier_en_attente(self, demande: DemandeDocument) -> None:
        if demande.statut != StatutDemandeDocument.EN_ATTENTE.value:
            raise ValidationMetier("Cette demande a déjà été traitée ou refusée.")

    def _obtenir_document_visible_ou_lever(
        self, document_id: uuid.UUID, *, tiers_id_scope: uuid.UUID | None = None
    ) -> Document:
        document = self.documents.obtenir(document_id)
        if document is None or not document.visible_client:
            raise RessourceIntrouvable("Document introuvable.")
        # Même non-distinction "n'existe pas" / "pas partagé avec moi" que
        # ci-dessus (Étape 6) : un document réservé à un AUTRE client reste
        # une 404, jamais un 403 qui en révélerait l'existence.
        if (
            tiers_id_scope is not None
            and document.tiers_id is not None
            and document.tiers_id != tiers_id_scope
        ):
            raise RessourceIntrouvable("Document introuvable.")
        return document