"""Modèle du module tiers (clients / fournisseurs).

Un tiers peut être client, fournisseur, ou les deux à la fois (cas fréquent
en pratique). Plutôt qu'un champ `type_tiers` (client/fournisseur/les_deux)
couplé à un unique `compte_collectif_id` — ce qui poserait la question de
savoir quel compte utiliser pour un tiers "les deux" — ce modèle porte
DEUX comptes collectifs optionnels :

- `compte_collectif_client_id` : renseigné si ce tiers facture l'entreprise
  cliente (compte de la classe 411 en pratique).
- `compte_collectif_fournisseur_id` : renseigné si ce tiers est facturé
  (compte de la classe 401 en pratique).

Un tiers "les deux" a simplement les deux renseignés — pas de logique
conditionnelle sur un enum. La contrainte `CHECK` impose qu'au moins un
des deux soit renseigné (un tiers qui n'est ni client ni fournisseur n'a
pas sa place ici). "Client" et "fournisseur" ne sont donc pas stockés
comme un statut mais déduits de ces deux colonnes (voir les propriétés
`est_client` / `est_fournisseur`).

Les deux comptes référencés doivent être des comptes collectifs
(`Compte.est_collectif`) — ce n'est PAS imposé par une contrainte `CHECK`
en base (une contrainte inter-tables n'est pas exprimable ainsi en SQL
standard) : c'est le service qui vérifie `est_collectif` avant d'accepter
la référence.
"""

import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base import Base
from app.shared.mixins import EntrepriseMixin, HorodatageMixin, IdentifiantMixin


class Tiers(IdentifiantMixin, HorodatageMixin, EntrepriseMixin, Base):
    __tablename__ = "tiers"
    __table_args__ = (
        UniqueConstraint("entreprise_id", "code"),
        CheckConstraint(
            "compte_collectif_client_id IS NOT NULL "
            "OR compte_collectif_fournisseur_id IS NOT NULL",
            name="au_moins_un_role",
        ),
    )

    code: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    raison_sociale: Mapped[str] = mapped_column(String(255), nullable=False)

    # Identification fiscale (cahier : zone cible Côte d'Ivoire / OHADA).
    # Ni l'un ni l'autre n'a de contrainte d'unicité : le cahier ne précise
    # pas de règle de validation ou de format à cette étape.
    nif: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rccm: Mapped[str | None] = mapped_column(String(50), nullable=True)

    adresse: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telephone: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Conditions commerciales : champs simples, pas de modélisation plus
    # fine (échéancier, remises...) tant que le cahier ne le demande pas.
    delai_paiement_jours: Mapped[int | None] = mapped_column(nullable=True)
    plafond_credit: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)

    actif: Mapped[bool] = mapped_column(nullable=False, default=True)

    compte_collectif_client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("comptes.id", ondelete="RESTRICT"),
        nullable=True,
    )
    compte_collectif_fournisseur_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("comptes.id", ondelete="RESTRICT"),
        nullable=True,
    )

    @property
    def est_client(self) -> bool:
        return self.compte_collectif_client_id is not None

    @property
    def est_fournisseur(self) -> bool:
        return self.compte_collectif_fournisseur_id is not None