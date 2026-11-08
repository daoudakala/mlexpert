"""Modèle du module regularisations (point 8.3 et 8.4 du cahier —
"Écritures d'inventaire / de régularisation" : charges et produits
constatés d'avance (CCA/PCA) ET charges à payer / produits à recevoir).

Une seule table pour les 4 types, contrairement à `immobilisations`/
`provisions` : il n'y a ici aucun solde à suivre dans le temps (une
régularisation ne s'accumule pas d'exercice en exercice, chacune est
propre à UN exercice), donc pas de distinction fiche/mouvement —
`Regularisation` EST l'événement, et son écriture est créée avec elle,
atomiquement (même raisonnement que `MouvementProvision.ecriture_id`,
jamais nul).

Les charges à payer / produits à recevoir sont le miroir exact des
CCA/PCA — même paire de comptes (origine classe 6 ou 7, régularisation
classe 4), mais le sens de l'écriture s'inverse puisqu'il s'agit d'AJOUTER
une charge/produit à l'exercice plutôt que d'en RETIRER un. D'où le même
modèle, mais une logique de sens à 4 branches dans `service.py` plutôt
qu'un simple test CCA/PCA.

Deux comptes par régularisation :

- `compte_origine_id` : le compte déjà mouvementé (ou à mouvementer) —
  une charge (classe 6) pour une CCA ou une charge à payer, un produit
  (classe 7) pour une PCA ou un produit à recevoir.
- `compte_regularisation_id` : le compte de régularisation — toujours
  classe 4 quel que soit le type (476 CCA, 477 PCA, 408 "Fournisseurs —
  factures non parvenues" pour une charge à payer, 418 "Clients —
  factures à établir" pour un produit à recevoir) — à la différence de
  `compte_origine_id` dont la classe attendue dépend du type (voir
  `CLASSE_ORIGINE_PAR_TYPE` dans `service.py`).

L'extourne au début de l'exercice suivant n'est PAS réimplémentée ici :
elle réutilise `ServiceComptabilite.extourner_ecriture`, déjà disponible
sur toute écriture validée (bouton existant côté `EcritureFormulaire.vue`)
— une régularisation n'est qu'une écriture comme une autre de ce point de
vue, qui n'a pas besoin de son propre mécanisme de contre-passation.
"""

import uuid
from datetime import date
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base import Base
from app.shared.mixins import EntrepriseMixin, HorodatageMixin, IdentifiantMixin


class TypeRegularisation(StrEnum):
    CHARGE_CONSTATEE_AVANCE = "charge_constatee_avance"
    PRODUIT_CONSTATE_AVANCE = "produit_constate_avance"
    CHARGE_A_PAYER = "charge_a_payer"
    PRODUIT_A_RECEVOIR = "produit_a_recevoir"


class Regularisation(IdentifiantMixin, HorodatageMixin, EntrepriseMixin, Base):
    __tablename__ = "regularisations_cca_pca"
    __table_args__ = (
        CheckConstraint(
            "type_regularisation IN ("
            "'charge_constatee_avance', 'produit_constate_avance', "
            "'charge_a_payer', 'produit_a_recevoir'"
            ")",
            name="type_regularisation_valide",
        ),
        CheckConstraint("montant > 0", name="montant_positif"),
    )

    libelle: Mapped[str] = mapped_column(String(255), nullable=False)
    type_regularisation: Mapped[str] = mapped_column(String(30), nullable=False)

    exercice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exercices.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    compte_origine_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comptes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    compte_regularisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comptes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    montant: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    date_regularisation: Mapped[date] = mapped_column(Date, nullable=False)

    # Jamais nul : voir la note de tête de fichier.
    ecriture_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ecritures.id", ondelete="RESTRICT"), nullable=False, index=True
    )