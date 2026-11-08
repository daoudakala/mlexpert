"""Modèles du module stocks.

Décisions actées avec l'utilisateur avant ce fichier :

- Deux méthodes de valorisation, au choix par article (`Article.methode_valorisation`) :
  - `cmup` (coût moyen unitaire pondéré) : recalculé à chaque entrée
    (`Article.cout_unitaire_moyen`), appliqué tel quel à toute sortie
    suivante — pas de notion de lot.
  - `fifo` (premier entré, premier sorti) : chaque entrée crée un
    `LotEntreeStock` ; une sortie consomme les lots les plus anciens
    d'abord (`quantite_restante > 0`, triés par `date_entree`), et
    `LigneConsommationLot` trace quel lot a été consommé, pour combien,
    et à quel coût.
- Le stock ne peut jamais devenir négatif : une sortie dont la quantité
  dépasse `Article.quantite_en_stock` est rejetée (voir `service.py`).
- La génération de l'écriture comptable correspondant à un mouvement
  (débit/crédit des comptes de classe 3/6/7) était explicitement HORS DE
  LA PORTÉE de ce premier passage — même choix que pour la paie
  (`app/modules/paie/models.py`). Mise à jour lors de la passe de
  consolidation comptable qui a suivi : `MouvementStock.ecriture_id`
  (nullable, `SET NULL`) a été ajouté, sur le même principe que
  `LigneAmortissement.ecriture_id` dans `immobilisations` — `None` tant
  que le mouvement n'a pas d'écriture postée. Le compte de contrepartie
  (achat/vente en face du compte de stock) n'est PAS stocké sur le
  mouvement : il varie selon le contexte (fournisseur, client, régularisation...)
  et est fourni à l'appel de génération (voir `service.py::generer_ecriture_mouvement`).
- Simplification assumée, pour contenir la portée : un `MouvementStock`
  est append-only (pas de modification, pas d'annulation formelle) —
  comme une ligne de grand livre, il vit tel quel une fois créé. Corriger
  une saisie erronée se fait en enregistrant un mouvement inverse
  (une entrée pour compenser une sortie erronée, ou l'inverse), exactement
  comme on le ferait sur un stock physique — pas de mécanisme dédié
  d'extourne ici (à la différence d'`Ecriture.extourner`).

Cinq tables :

- `Article` : la fiche article, avec le compte comptable de stock rattaché
  (classe 3, validé par le service) et l'état courant dénormalisé
  (`quantite_en_stock`, `valeur_stock`, `cout_unitaire_moyen`) — recalculé
  à chaque mouvement plutôt que recalculé à la volée, pour des lectures
  rapides (comme `Compte` n'a pas de solde dénormalisé, mais ici la
  fraîcheur du stock disponible est consultée bien plus souvent que les
  soldes comptables, d'où le choix inverse).
- `MouvementStock` : une entrée ou une sortie, avec la quantité et le coût
  unitaire APPLIQUÉ à ce mouvement (donné pour une entrée, calculé par le
  service pour une sortie selon la méthode de l'article).
- `LotEntreeStock` : une entrée de stock, pour les articles en FIFO
  uniquement (ne sert à rien pour un article en CMUP — voir `service.py`,
  qui ne le peuple pas dans ce cas).
- `LigneConsommationLot` : le détail d'une sortie en FIFO, un lot consommé
  à la fois (une sortie peut consommer plusieurs lots si le plus ancien ne
  suffit pas).
- `InventairePhysique` (cahier, section 8, point 5 — "Stocks : variation de
  stock en fin d'exercice") : la fiche d'un comptage physique, qui compare
  la quantité théorique (tenue par les mouvements) à la quantité
  réellement comptée. Volontairement PAS une écriture de "variation de
  stock" classique (SI/SF, comptes 603x/713x) : ce module tient un
  inventaire PERMANENT (le compte de stock classe 3 est déjà à jour en
  temps réel via `MouvementStock`/`generer_ecriture_mouvement`), donc ce
  qu'il reste à constater en fin d'exercice est un ÉCART entre ce stock
  théorique et le comptage physique réel (perte, casse, vol, ou surplus).
  L'écart, s'il n'est pas nul, déclenche un `MouvementStock` ordinaire
  (entrée pour un surplus, sortie pour un manquant) via les méthodes déjà
  existantes de `ServiceStocks`, et son écriture, via
  `generer_ecriture_mouvement` déjà existant également — voir
  `ServiceStocks.creer_inventaire_physique` dans `service.py`.
"""

import uuid
from datetime import date
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base import Base
from app.shared.mixins import EntrepriseMixin, HorodatageMixin, IdentifiantMixin


class MethodeValorisation(StrEnum):
    CMUP = "cmup"
    FIFO = "fifo"


class TypeMouvement(StrEnum):
    ENTREE = "entree"
    SORTIE = "sortie"


class Article(IdentifiantMixin, HorodatageMixin, EntrepriseMixin, Base):
    __tablename__ = "articles"
    __table_args__ = (
        UniqueConstraint("entreprise_id", "code"),
        CheckConstraint("methode_valorisation IN ('cmup', 'fifo')", name="methode_valide"),
        CheckConstraint("quantite_en_stock >= 0", name="quantite_en_stock_positive"),
        CheckConstraint("cout_unitaire_moyen >= 0", name="cout_unitaire_moyen_positif"),
        CheckConstraint("valeur_stock >= 0", name="valeur_stock_positive"),
    )

    code: Mapped[str] = mapped_column(String(30), nullable=False)
    libelle: Mapped[str] = mapped_column(String(150), nullable=False)
    unite: Mapped[str] = mapped_column(String(20), nullable=False)
    methode_valorisation: Mapped[str] = mapped_column(String(10), nullable=False)
    compte_stock_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comptes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    actif: Mapped[bool] = mapped_column(nullable=False, default=True)
    # État courant, dénormalisé et maintenu par le service à chaque
    # mouvement (voir la note de tête de fichier).
    quantite_en_stock: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    cout_unitaire_moyen: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=0)
    valeur_stock: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)


class MouvementStock(IdentifiantMixin, HorodatageMixin, EntrepriseMixin, Base):
    __tablename__ = "mouvements_stock"
    __table_args__ = (
        CheckConstraint("type_mouvement IN ('entree', 'sortie')", name="type_valide"),
        CheckConstraint("quantite > 0", name="quantite_positive"),
        CheckConstraint("cout_unitaire >= 0", name="cout_unitaire_positif"),
        CheckConstraint("cout_total >= 0", name="cout_total_positif"),
    )

    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    type_mouvement: Mapped[str] = mapped_column(String(10), nullable=False)
    date_mouvement: Mapped[date] = mapped_column(Date, nullable=False)
    quantite: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    # Coût unitaire APPLIQUÉ à ce mouvement : saisi pour une entrée, calculé
    # par le service pour une sortie (CMUP courant, ou coût moyen pondéré
    # des lots FIFO consommés) — voir la note de tête de fichier.
    cout_unitaire: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    cout_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    libelle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tiers_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tiers.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    # Renseigné une fois le mouvement comptabilisé (voir la note de tête
    # de fichier) — jamais à la création du mouvement.
    ecriture_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ecritures.id", ondelete="SET NULL"), nullable=True
    )


class LotEntreeStock(IdentifiantMixin, EntrepriseMixin, Base):
    """Une entrée de stock pour un article en FIFO. Ne sert à rien pour un
    article en CMUP (le service ne le peuple pas dans ce cas) — voir la
    note de tête de fichier."""

    __tablename__ = "lots_entree_stock"
    __table_args__ = (
        CheckConstraint("quantite_initiale > 0", name="quantite_initiale_positive"),
        CheckConstraint("quantite_restante >= 0", name="quantite_restante_positive"),
        CheckConstraint(
            "quantite_restante <= quantite_initiale", name="quantite_restante_coherente"
        ),
        CheckConstraint("cout_unitaire >= 0", name="cout_unitaire_positif"),
    )

    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    mouvement_entree_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mouvements_stock.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    date_entree: Mapped[date] = mapped_column(Date, nullable=False)
    quantite_initiale: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    quantite_restante: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    cout_unitaire: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)


class LigneConsommationLot(IdentifiantMixin, EntrepriseMixin, Base):
    """Le détail d'une sortie FIFO : un lot consommé, avec la quantité
    prise dessus et le coût unitaire du lot au moment de la consommation
    (recopié pour l'historique, même s'il ne varie jamais après coup)."""

    __tablename__ = "lignes_consommation_lot"
    __table_args__ = (CheckConstraint("quantite_consommee > 0", name="quantite_consommee_positive"),)

    mouvement_sortie_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mouvements_stock.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    lot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lots_entree_stock.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantite_consommee: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    cout_unitaire: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)


class InventairePhysique(IdentifiantMixin, HorodatageMixin, EntrepriseMixin, Base):
    """Un comptage physique de fin d'exercice pour un article — voir la
    note de tête de fichier. `quantite_theorique` est un instantané de
    `Article.quantite_en_stock` au moment du comptage (jamais recalculée a
    posteriori, même si des mouvements sont enregistrés plus tard sur une
    date antérieure). `ecart` = `quantite_physique` − `quantite_theorique`,
    stocké pour éviter de le recalculer à chaque lecture (positif =
    surplus, négatif = manquant, nul = rien à régulariser).

    `mouvement_ajustement_id` reste NULL quand `ecart` est nul (aucun
    mouvement à générer) ; sinon il pointe vers le `MouvementStock` créé
    pour corriger l'écart (entrée si surplus, sortie si manquant)."""

    __tablename__ = "inventaires_physiques"
    __table_args__ = (CheckConstraint("quantite_physique >= 0", name="quantite_physique_positive"),)

    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    exercice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exercices.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    date_inventaire: Mapped[date] = mapped_column(Date, nullable=False)
    quantite_theorique: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    quantite_physique: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    ecart: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    mouvement_ajustement_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mouvements_stock.id", ondelete="SET NULL"), nullable=True
    )