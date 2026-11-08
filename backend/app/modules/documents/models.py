"""Modèle du module documents (gestion électronique de documents, GED).

Une seule table, `Document` : le cahier des charges distingue le "dossier
permanent" (documents qui ne se rattachent à aucun exercice précis —
statuts, immatriculation, bail...) du "dossier annuel" (pièces propres à
un exercice — liasse fiscale, PV d'AG annuelle...). Plutôt que deux
tables, `exercice_id` NULLABLE encode cette distinction directement :
NULL = dossier permanent, renseigné = document rattaché à cet exercice.
Même choix de conception que `Compte.entreprise_id` nullable dans
`comptabilite` (un NULL porteur de sens, pas une absence de donnée).

`categorie` : liste fermée (`CategorieDocument`, cahier section 7.1 —
"statuts, documents juridiques, attestations et autres pièces", étendue
aux pièces du dossier annuel mentionnées dans ce même fichier ci-dessus).
Contrainte posée uniquement côté schémas Pydantic (`schemas.py`), PAS par
un `CheckConstraint` en base : des documents existants portent des
valeurs libres antérieures à cette liste (import initial, saisies
manuelles) qu'une contrainte stricte casserait rétroactivement. Toute
nouvelle écriture passe par l'énumération ; les anciennes valeurs restent
lisibles telles quelles.

Stockage du contenu : le fichier est stocké TEL QUEL en base
(`LargeBinary`), pas sur un système de fichiers ni un object storage
externe. Simplification assumée pour ce premier passage — volontaire,
comme la limite de concurrence documentée dans `comptabilite` : ça évite
de figer une dépendance (chemin de montage, bucket S3) avant que le
cahier ne précise l'environnement de déploiement cible. À revoir avant la
mise en production si les volumes de fichiers deviennent significatifs.

`visible_client` (ajouté pour le module `portail_client`) : `False` par
défaut — un document n'est visible par un utilisateur client qu'après
décision explicite du cabinet, jamais par défaut. Ça reste un simple
booléen plutôt qu'une liste blanche par utilisateur : le cahier ne
demande pas de partage sélectif à UN client précis parmi plusieurs, un
document est visible par TOUS les clients de l'entreprise ou par aucun.

`ecriture_id` (NULLABLE, section 8.2 du cahier — "pièce justificative
rattachable à une écriture") : un document déjà existant peut être
rattaché après coup à une écriture comptable, comme preuve. Direction
INVERSE du `ecriture_id` qu'on trouve sur `LigneAmortissement`/
`BulletinPaie`/`MouvementStock` dans d'autres modules (celui-là porte
"l'écriture GÉNÉRÉE PAR cet enregistrement" — posée une fois à la
validation d'un événement métier). Ici c'est "le document attaché À une
écriture déjà existante" — un rattachement qui peut se faire, se défaire
et se refaire librement, bien après coup, et qui n'a aucun impact sur
l'écriture elle-même (juste une preuve archivée à côté). `ondelete="SET
NULL"` plutôt que `CASCADE` : supprimer l'écriture (ou l'extourner) ne
doit jamais supprimer le document — seulement délier le rattachement, le
document reste consultable comme pièce orpheline.
"""

import uuid
from datetime import date
from enum import StrEnum

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base import Base
from app.shared.mixins import EntrepriseMixin, HorodatageMixin, IdentifiantMixin


class CategorieDocument(StrEnum):
    """Liste fermée pour toute NOUVELLE écriture — voir le docstring de
    tête de fichier pour pourquoi la colonne elle-même reste une chaîne
    libre en base."""

    STATUTS = "statuts"
    JURIDIQUE = "juridique"
    ATTESTATION = "attestation"
    FISCAL = "fiscal"
    COMPTABLE = "comptable"
    SOCIAL = "social"
    AUTRE = "autre"


class Document(IdentifiantMixin, HorodatageMixin, EntrepriseMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("taille_octets >= 0", name="taille_positive"),
    )

    categorie: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    nom_fichier: Mapped[str] = mapped_column(String(255), nullable=False)
    type_mime: Mapped[str] = mapped_column(String(100), nullable=False)
    taille_octets: Mapped[int] = mapped_column(Integer, nullable=False)
    contenu: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Date "métier" du document (date du bail, date du PV...), distincte de
    # `cree_le` (date de dépôt dans MLexpert, posée par HorodatageMixin).
    date_document: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Pour les documents à renouveler (assurance, bail, contrat...) — pas
    # d'alerte automatique construite à ce stade, seulement le stockage.
    date_expiration: Mapped[date | None] = mapped_column(Date, nullable=True)

    # NULL = dossier permanent, renseigné = pièce de ce seul exercice (voir
    # la note de tête de fichier).
    exercice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exercices.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    depose_par_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    visible_client: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Pièce justificative rattachée à une écriture — voir la note de tête
    # de fichier. NULL = document non rattaché (cas général).
    ecriture_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ecritures.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Restreint un document `visible_client` à UN client précis (Étape 6 —
    # auto-gestion des entreprises). NULL (le défaut) = comportement
    # inchangé : visible par TOUS les clients de l'entreprise si
    # `visible_client` est vrai. Renseigné : visible uniquement par le
    # compte portail rattaché à ce `Tiers` (voir `Affectation.tiers_id` et
    # `ServicePortailClient`), les autres clients de l'entreprise ne le
    # voient pas même si `visible_client` est vrai.
    tiers_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tiers.id", ondelete="SET NULL"), nullable=True, index=True
    )