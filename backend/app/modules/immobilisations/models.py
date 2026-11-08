"""Modèles du module immobilisations.

Deux tables, sur le même principe que `comptabilite.Ecriture` /
`LigneEcriture` (un en-tête descriptif, un détail calculé) :

- `Immobilisation` : la fiche descriptive — valeur d'origine, durée et
  méthode d'amortissement, et les trois comptes comptables rattachés
  (immobilisation classe 2, amortissement cumulé classe 28, dotation aux
  amortissements classe 68). La cohérence classe==2/28/68 n'est PAS
  vérifiable par un `CHECK` inter-tables : c'est le service qui la
  garantit à la création, comme `compte_comptable_id` dans le module
  `tresorerie`.
- `LigneAmortissement` : le plan d'amortissement calculé, une ligne par
  exercice. `statut` (`prevu`/`comptabilise`) et `ecriture_id` (nullable,
  `ondelete=SET NULL`) suivent le même principe que la validation d'une
  `Ecriture` : une ligne "prevu" n'a pas encore d'écriture de dotation
  postée ; une fois comptabilisée, `ecriture_id` la référence.

Portée volontairement limitée à ce premier passage (comme `comptabilite`
a été scindé en deux) :

- La génération effective de l'écriture de dotation (appel à
  `ServiceComptabilite.creer_ecriture`) n'était pas construite ici non
  plus au départ — ajoutée depuis lors de la passe de consolidation
  comptable (`ServiceImmobilisations.generer_ecriture_amortissement`).

Mise à jour lors de la passe cession/mise au rebut, qui suit la même
logique que la consolidation comptable (comptes de contrepartie fournis à
l'appel plutôt que stockés) :

- `date_sortie`, `prix_cession`, `valeur_nette_comptable_sortie`,
  `plus_ou_moins_value` et `ecriture_sortie_id` sont tous nullables et ne
  se renseignent qu'à la cession/réforme (`ServiceImmobilisations.ceder_immobilisation`/
  `reformer_immobilisation`) — jamais à la création. Une fois `statut`
  passé à `cedee`/`reformee`, ces colonnes deviennent immuables (aucune
  méthode ne les modifie après coup) : la sortie du patrimoine est, comme
  la validation d'une `Ecriture`, une opération à sens unique.
- `prix_cession` distingue les deux cas : renseigné (même à 0) pour une
  cession, toujours `NULL` pour une réforme (mise au rebut, par
  définition sans contrepartie financière) — les `CHECK` ci-dessous
  l'imposent.
- `valeur_nette_comptable_sortie`/`plus_ou_moins_value` sont dénormalisés
  (calculables depuis `valeur_origine`, le cumul d'amortissements de la
  dernière `LigneAmortissement` et `prix_cession`) mais conservés tels
  quels pour ne pas dépendre, en lecture, d'un recalcul dont l'entrée
  (le plan d'amortissement) peut continuer d'évoluer après coup pour
  d'autres exercices non concernés.
- Le plan d'amortissement n'est PAS mis à jour à la date de sortie
  (aucune dotation prorata temporis finale n'est générée automatiquement) :
  le service utilise le cumul le plus récent connu (dernière
  `LigneAmortissement` déjà générée), et laisse au comptable le soin de
  générer une dernière dotation au prorata AVANT de céder/réformer le
  bien, s'il le souhaite — choix assumé pour rester cohérent avec le
  principe déjà en place de génération du plan à la demande, exercice
  par exercice.

Deux méthodes d'amortissement dès ce premier passage : `lineaire` (taux
constant = 1/durée, base constante) et `degressif` (taux constant
appliqué à la valeur nette comptable décroissante, cahier des charges
SYSCOHADA/OHADA). `taux_degressif` n'a de sens qu'en `degressif` — la
contrainte `CHECK` impose sa présence dans ce cas et son absence sinon,
plutôt que de le rendre systématiquement nullable sans le contraindre.
"""

import uuid
from datetime import date
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, SmallInteger, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base import Base
from app.shared.mixins import EntrepriseMixin, HorodatageMixin, IdentifiantMixin


class MethodeAmortissement(StrEnum):
    LINEAIRE = "lineaire"
    DEGRESSIF = "degressif"


class StatutImmobilisation(StrEnum):
    EN_SERVICE = "en_service"
    CEDEE = "cedee"
    REFORMEE = "reformee"


class StatutLigneAmortissement(StrEnum):
    PREVU = "prevu"
    COMPTABILISE = "comptabilise"


class Immobilisation(IdentifiantMixin, HorodatageMixin, EntrepriseMixin, Base):
    __tablename__ = "immobilisations"
    __table_args__ = (
        CheckConstraint("valeur_origine > 0", name="valeur_origine_positive"),
        CheckConstraint(
            "valeur_residuelle >= 0 AND valeur_residuelle < valeur_origine",
            name="valeur_residuelle_coherente",
        ),
        CheckConstraint("duree_amortissement_annees > 0", name="duree_positive"),
        CheckConstraint(
            "date_mise_en_service >= date_acquisition", name="dates_coherentes"
        ),
        CheckConstraint(
            "methode_amortissement IN ('lineaire', 'degressif')",
            name="methode_valide",
        ),
        CheckConstraint(
            "(methode_amortissement = 'degressif' AND taux_degressif IS NOT NULL) OR "
            "(methode_amortissement = 'lineaire' AND taux_degressif IS NULL)",
            name="taux_degressif_coherent",
        ),
        CheckConstraint(
            "statut IN ('en_service', 'cedee', 'reformee')",
            name="statut_valide",
        ),
        CheckConstraint(
            "statut != 'cedee' OR (date_sortie IS NOT NULL AND prix_cession IS NOT NULL)",
            name="cession_coherente",
        ),
        CheckConstraint(
            "statut != 'reformee' OR (date_sortie IS NOT NULL AND prix_cession IS NULL)",
            name="reforme_coherente",
        ),
        CheckConstraint("prix_cession IS NULL OR prix_cession >= 0", name="prix_cession_positif"),
        CheckConstraint(
            "date_sortie IS NULL OR date_sortie >= date_mise_en_service",
            name="date_sortie_coherente",
        ),
    )

    libelle: Mapped[str] = mapped_column(String(255), nullable=False)
    categorie: Mapped[str | None] = mapped_column(String(100), nullable=True)
    numero_inventaire: Mapped[str | None] = mapped_column(String(50), nullable=True)

    date_acquisition: Mapped[date] = mapped_column(Date, nullable=False)
    date_mise_en_service: Mapped[date] = mapped_column(Date, nullable=False)

    valeur_origine: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    valeur_residuelle: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    duree_amortissement_annees: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    methode_amortissement: Mapped[str] = mapped_column(
        String(20), nullable=False, default=MethodeAmortissement.LINEAIRE.value
    )
    # Uniquement renseigné en méthode dégressive (voir la note de tête de
    # fichier et la contrainte CHECK ci-dessus). Stocké en pourcentage
    # (ex. 25.00 pour 25 %), pas en fraction, pour rester lisible côté API.
    taux_degressif: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    statut: Mapped[str] = mapped_column(
        String(20), nullable=False, default=StatutImmobilisation.EN_SERVICE.value
    )

    compte_immobilisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comptes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    compte_amortissement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comptes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    compte_dotation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comptes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Optionnel : une immobilisation n'a pas toujours de fournisseur
    # identifié dans `tiers` (ex. apport, production immobilisée).
    fournisseur_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tiers.id", ondelete="RESTRICT"), nullable=True, index=True
    )

    # Renseignés uniquement à la cession/réforme (voir la note de tête de
    # fichier) — jamais à la création, jamais modifiés après coup.
    date_sortie: Mapped[date | None] = mapped_column(Date, nullable=True)
    prix_cession: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    valeur_nette_comptable_sortie: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    plus_ou_moins_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    ecriture_sortie_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ecritures.id", ondelete="SET NULL"), nullable=True
    )


class LigneAmortissement(IdentifiantMixin, EntrepriseMixin, Base):
    """Pas de `HorodatageMixin` : comme `LigneEcriture`, une ligne est
    recalculée/remplacée en bloc par le service, `cree_le` de
    l'immobilisation parente suffit."""

    __tablename__ = "lignes_amortissement"
    __table_args__ = (
        UniqueConstraint("immobilisation_id", "exercice_id"),
        CheckConstraint(
            "statut IN ('prevu', 'comptabilise')",
            name="statut_valide",
        ),
        CheckConstraint("dotation >= 0", name="dotation_positive"),
        CheckConstraint("cumul_amortissements >= 0", name="cumul_positif"),
        CheckConstraint("valeur_nette_comptable >= 0", name="vnc_positive"),
    )

    immobilisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("immobilisations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    exercice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exercices.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    base_amortissable: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    taux_applique: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    dotation: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    cumul_amortissements: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    valeur_nette_comptable: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    statut: Mapped[str] = mapped_column(
        String(20), nullable=False, default=StatutLigneAmortissement.PREVU.value
    )
    # Renseigné une fois la dotation de cet exercice comptabilisée (portée
    # future, voir la note de tête de fichier) — jamais à la création du
    # plan d'amortissement.
    ecriture_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ecritures.id", ondelete="SET NULL"),
        nullable=True,
    )