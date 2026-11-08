"""Modèles du module comptabilite.

Partie référentiel (premier passage) :

- `Compte` : le plan comptable SYSCOHADA. Un compte est soit un compte du
  référentiel partagé (`entreprise_id` NULL — les comptes normalisés,
  communs à toutes les entreprises), soit une extension propre à une
  entreprise (`entreprise_id` renseigné). C'est pour ça que `Compte` ne
  compose PAS `EntrepriseMixin` : ce mixin impose `entreprise_id` NOT
  NULL, ce qui interdirait justement les comptes partagés. Deux index
  uniques partiels remplacent la contrainte unique habituelle : un numéro
  de compte est unique parmi les comptes globaux, et unique par
  entreprise parmi les extensions — mais rien n'empêche en base qu'une
  entreprise choisisse un numéro déjà pris par un compte global ; cette
  vérification-là revient au service, pas à la base.
  Indépendamment de ça, `compte_parent_id` porte la hiérarchie
  comptable au sens strict (un sous-compte au sens SYSCOHADA : ex.
  411000 « Clients » → 411001 « Client X ») — un compte « extension »
  et un compte « enfant » sont deux notions orthogonales : une
  extension peut très bien n'avoir aucun parent (un compte autonome
  ajouté par l'entreprise), ou être elle-même parente d'autres
  extensions.
- `Journal` : achats, ventes, banque, caisse, opérations diverses. Chaque
  entreprise définit ses propres journaux (`EntrepriseMixin`, NOT NULL) :
  contrairement au plan comptable, il n'y a pas de "journaux partagés".

Partie transactionnelle (second passage, après `tiers`) :

- `Ecriture` : l'en-tête. Deux statuts, `brouillon` puis `validee` — une
  fois validée, une écriture ne se modifie plus (le service refuse toute
  écriture dessus) ; une correction se fait par une écriture d'extourne
  (`ecriture_extournee_id`, sur la NOUVELLE écriture, qui référence
  celle qu'elle annule — jamais l'inverse : l'original n'est pas marqué,
  ça se déduit par une recherche sur cette colonne).
  `numero` est nullable : une écriture en brouillon n'en a pas encore un.
  Il est attribué séquentiellement (par journal ET par exercice) au
  moment de la validation, dans le service — jamais ici, voir la note
  plus haut sur `Journal`. Un index unique partiel (`numero IS NOT NULL`)
  empêche deux écritures validées de partager un numéro dans le même
  journal et le même exercice, sans rien imposer aux brouillons.
- `LigneEcriture` : le détail débit/crédit. `tiers_id` est optionnel
  (toutes les lignes ne concernent pas un tiers) — voir la note dans
  `models.py` du module `tiers` pour le choix de ce rattachement plutôt
  qu'un compte auxiliaire dédié par tiers. La contrainte `CHECK` impose
  qu'une ligne soit soit débitrice, soit créditrice, jamais les deux ni
  ni l'une ni l'autre. L'équilibre de l'écriture entière (total débit =
  total crédit) n'est PAS vérifiable par une contrainte `CHECK` sur une
  seule ligne : c'est le service qui le vérifie à la validation, sur
  l'ensemble des lignes.
  `date_echeance` (nullable) ne concerne en pratique que les lignes
  portant un `tiers_id` : c'est la base de l'échéancier clients/
  fournisseurs et de la balance âgée (cahier, sections 8.4 et 13).
  Calculée automatiquement par le service à partir de
  `Tiers.delai_paiement_jours` quand elle n'est pas fournie explicitement
  (voir `ServiceComptabilite._calculer_date_echeance`) ; jamais imposée
  par une contrainte, une ligne sans tiers ou sans délai connu reste
  simplement NULL.

`Ecriture` et `LigneEcriture` composent `EntrepriseMixin` avec
`entreprise_id` dénormalisé depuis `Journal`/`Exercice` (même choix que
`Periode` dans `modules/exercices/models.py`) : c'est cette colonne que
`RepositoryEntreprise` filtre directement, la cohérence avec le journal
et l'exercice réels est garantie par le service, pas par la base.
"""

import uuid
from datetime import date
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base import Base
from app.shared.mixins import EntrepriseMixin, HorodatageMixin, IdentifiantMixin


class TypeJournal(StrEnum):
    ACHATS = "achats"
    VENTES = "ventes"
    BANQUE = "banque"
    CAISSE = "caisse"
    OPERATIONS_DIVERSES = "operations_diverses"
    # Journal dédié au report des soldes de bilan (classes 1-5) de
    # l'exercice précédent — voir `ServiceComptabilite.generer_a_nouveaux`
    # (cahier, section 7.2 "gestion des à-nouveaux").
    A_NOUVEAUX = "a_nouveaux"


class Compte(IdentifiantMixin, HorodatageMixin, Base):
    __tablename__ = "comptes"
    __table_args__ = (
        CheckConstraint("classe BETWEEN 1 AND 8", name="classe_valide"),
        CheckConstraint(
            "NOT est_collectif OR lettrable",
            name="collectif_implique_lettrable",
        ),
        Index(
            "uq_comptes_numero_global",
            "numero",
            unique=True,
            postgresql_where=text("entreprise_id IS NULL"),
        ),
        Index(
            "uq_comptes_numero_entreprise",
            "entreprise_id",
            "numero",
            unique=True,
            postgresql_where=text("entreprise_id IS NOT NULL"),
        ),
    )

    numero: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    libelle: Mapped[str] = mapped_column(String(255), nullable=False)
    # Classe SYSCOHADA (1 à 8) : détermine la nature du compte (ressources
    # durables, actif immobilisé, stocks, tiers, trésorerie, charges,
    # produits, autres charges/produits). Le sens normal (débiteur ou
    # créditeur) n'est volontairement pas stocké : il se lit directement
    # du solde (somme des débits moins somme des crédits), calculé à la
    # lecture, pas à l'écriture.
    classe: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    # Un compte lettrable est un compte dont les écritures se pointent
    # entre elles (rapprochement facture / règlement) : typiquement les
    # comptes de tiers (411, 401) et certains comptes de trésorerie.
    lettrable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Un compte collectif est le compte auquel un tiers (module `tiers`)
    # peut être rattaché — explicite plutôt que déduit du numéro, pour ne
    # pas dépendre d'une convention de nommage dans le service. Un compte
    # collectif est toujours lettrable (voir la contrainte ci-dessus) :
    # c'est justement ce qui permet de pointer les écritures d'un tiers
    # entre elles.
    est_collectif: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    actif: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Nullable par exception : voir la note en tête de fichier. Un compte
    # global n'appartient à aucune entreprise ; ondelete=CASCADE ne joue
    # donc que pour les extensions propres à une entreprise.
    entreprise_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entreprises.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Hiérarchie parent/enfant explicite (sous-compte) : un compte global
    # ne peut avoir qu'un compte global pour parent, une extension
    # d'entreprise un compte visible par cette entreprise (global ou
    # extension de la même entreprise) — le service le garantit via le
    # repository utilisé pour résoudre `compte_parent_id`, pas la base
    # (même logique que pour l'unicité du numéro, voir plus haut).
    # `ondelete=RESTRICT` : un compte ayant des enfants ne peut pas être
    # supprimé (en pratique jamais fait — seule la désactivation existe),
    # pour ne jamais laisser un enfant pointer vers un parent disparu.
    compte_parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("comptes.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )


class Journal(IdentifiantMixin, HorodatageMixin, EntrepriseMixin, Base):
    __tablename__ = "journaux"
    __table_args__ = (
        UniqueConstraint("entreprise_id", "code"),
        CheckConstraint(
            "type_journal IN ('achats', 'ventes', 'banque', 'caisse', "
            "'operations_diverses', 'a_nouveaux')",
            name="type_journal_valide",
        ),
    )

    code: Mapped[str] = mapped_column(String(20), nullable=False)
    libelle: Mapped[str] = mapped_column(String(150), nullable=False)
    type_journal: Mapped[str] = mapped_column(String(30), nullable=False)
    actif: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class StatutEcriture(StrEnum):
    BROUILLON = "brouillon"
    VALIDEE = "validee"


class Ecriture(IdentifiantMixin, HorodatageMixin, EntrepriseMixin, Base):
    __tablename__ = "ecritures"
    __table_args__ = (
        CheckConstraint("statut IN ('brouillon', 'validee')", name="statut_valide"),
        Index(
            "uq_ecritures_numero",
            "journal_id",
            "exercice_id",
            "numero",
            unique=True,
            postgresql_where=text("numero IS NOT NULL"),
        ),
    )

    journal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journaux.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    exercice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exercices.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    date_ecriture: Mapped[date] = mapped_column(Date, nullable=False)
    libelle: Mapped[str] = mapped_column(String(255), nullable=False)
    reference_piece: Mapped[str | None] = mapped_column(String(100), nullable=True)
    statut: Mapped[str] = mapped_column(
        String(20), nullable=False, default=StatutEcriture.BROUILLON.value
    )
    # Nul tant que l'écriture est en brouillon ; attribué par le service à
    # la validation (séquentiel par journal et par exercice — voir la note
    # de tête de fichier). Ne JAMAIS renseigner à la création.
    numero: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Sur la NOUVELLE écriture (l'extourne), jamais sur l'originale : voir
    # la note de tête de fichier.
    ecriture_extournee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ecritures.id", ondelete="SET NULL"),
        nullable=True,
    )


class SensLigne(StrEnum):
    """Le sens d'une ligne de modèle — un modèle fige le compte et le
    sens (débit/crédit), jamais le montant : voir `ModeleEcriture`."""

    DEBIT = "debit"
    CREDIT = "credit"


class ModeleEcriture(IdentifiantMixin, HorodatageMixin, EntrepriseMixin, Base):
    """Une structure d'écriture réutilisable (cahier, section 8.2 "Saisie
    par modèle") : un journal + une liste de lignes qui fige le compte,
    le sens et un libellé, mais PAS le montant — celui-ci est toujours
    saisi au moment d'appliquer le modèle (voir
    `ServiceComptabilite.appliquer_modele`), pour ne jamais reconduire un
    montant obsolète (loyer, salaires, dotations...). Le modèle lui-même
    ne produit jamais d'écriture : il sert uniquement de patron."""

    __tablename__ = "modeles_ecriture"
    __table_args__ = (UniqueConstraint("entreprise_id", "code"),)

    code: Mapped[str] = mapped_column(String(20), nullable=False)
    libelle: Mapped[str] = mapped_column(String(150), nullable=False)
    journal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journaux.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    actif: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class LigneModeleEcriture(IdentifiantMixin, EntrepriseMixin, Base):
    """Pas de `HorodatageMixin`, comme `LigneEcriture` : une ligne de
    modèle vit et meurt avec son modèle."""

    __tablename__ = "lignes_modele_ecriture"
    __table_args__ = (
        CheckConstraint("sens IN ('debit', 'credit')", name="sens_ligne_modele_valide"),
    )

    modele_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("modeles_ecriture.id", ondelete="CASCADE"), nullable=False, index=True
    )
    compte_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comptes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    sens: Mapped[str] = mapped_column(String(10), nullable=False)
    libelle: Mapped[str | None] = mapped_column(String(255), nullable=True)


class LigneEcriture(IdentifiantMixin, EntrepriseMixin, Base):
    """Pas de `HorodatageMixin` : une ligne ne se modifie jamais isolément
    (elle vit et meurt avec son écriture, en brouillon) ; `cree_le` suffit,
    porté par l'écriture parente elle-même."""

    __tablename__ = "lignes_ecriture"
    __table_args__ = (
        CheckConstraint(
            "(debit > 0 AND credit = 0) OR (debit = 0 AND credit > 0)",
            name="debit_xor_credit",
        ),
    )

    ecriture_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ecritures.id", ondelete="CASCADE"), nullable=False, index=True
    )
    compte_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comptes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Optionnel : seules les lignes portant sur un compte lettrable de
    # tiers en ont un (voir `modules/tiers/models.py`).
    tiers_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tiers.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    libelle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    debit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    credit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    # Code de rapprochement (lettrage) : les lignes qui partagent ce code
    # sont considérées comme pointées entre elles. Le moteur de lettrage
    # (proposition de rapprochement automatique) n'est pas construit à ce
    # stade — seul le stockage du résultat l'est.
    code_lettrage: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    # Échéancier clients/fournisseurs (voir la note de tête de fichier) :
    # nullable, pertinent seulement sur une ligne avec tiers_id.
    date_echeance: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)


class PeriodiciteRecurrence(StrEnum):
    MENSUELLE = "mensuelle"
    TRIMESTRIELLE = "trimestrielle"
    ANNUELLE = "annuelle"


class EcritureRecurrente(IdentifiantMixin, HorodatageMixin, EntrepriseMixin, Base):
    """Une écriture récurrente (cahier, section 8.4 "Écritures récurrentes") :
    un patron d'écriture, comme `ModeleEcriture`, mais à la différence de
    celui-ci chaque ligne porte un montant FIXE (`LigneEcritureRecurrente.
    montant`) — un loyer, un abonnement, une dotation périodique dont le
    montant ne change pas d'une occurrence à l'autre, contrairement au
    modèle (section 8.2) dont le montant est toujours ressaisi. C'est ce
    qui permet une génération non assistée (`ServiceComptabilite.
    generer_echeances`), alors qu'un modèle demande toujours une saisie
    manuelle du montant.

    `prochaine_echeance` avance à chaque génération (succès ou échec, voir
    `generer_echeances`) ; `date_fin` NULL signifie une récurrence sans
    terme connu. `date_debut` ne se modifie jamais après création (une
    récurrence qui a déjà généré des occurrences ne peut pas revenir dans
    le passé) — seule `prochaine_echeance` avance."""

    __tablename__ = "ecritures_recurrentes"
    __table_args__ = (
        UniqueConstraint("entreprise_id", "code"),
        CheckConstraint(
            "periodicite IN ('mensuelle', 'trimestrielle', 'annuelle')",
            name="periodicite_recurrence_valide",
        ),
    )

    code: Mapped[str] = mapped_column(String(20), nullable=False)
    libelle: Mapped[str] = mapped_column(String(150), nullable=False)
    journal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journaux.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    periodicite: Mapped[str] = mapped_column(String(20), nullable=False)
    reference_piece: Mapped[str | None] = mapped_column(String(100), nullable=True)
    date_debut: Mapped[date] = mapped_column(Date, nullable=False)
    date_fin: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Prochaine date à laquelle une occurrence doit être générée ; initialisée
    # à `date_debut` à la création, avancée par `generer_echeances` à chaque
    # passage (même en cas d'échec de l'occurrence — voir la note du service).
    prochaine_echeance: Mapped[date] = mapped_column(Date, nullable=False)
    actif: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class LigneEcritureRecurrente(IdentifiantMixin, EntrepriseMixin, Base):
    """Pas de `HorodatageMixin`, comme `LigneModeleEcriture` : une ligne de
    récurrence vit et meurt avec sa récurrence. `montant` (fixe, ni débit
    ni crédit séparés) + `sens` suffisent à reconstruire une `LigneSaisie`
    à chaque génération — voir `ServiceComptabilite.generer_echeances`."""

    __tablename__ = "lignes_ecriture_recurrente"
    __table_args__ = (
        CheckConstraint("sens IN ('debit', 'credit')", name="sens_ligne_recurrente_valide"),
        CheckConstraint("montant > 0", name="montant_ligne_recurrente_positif"),
    )

    ecriture_recurrente_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ecritures_recurrentes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    compte_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comptes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    sens: Mapped[str] = mapped_column(String(10), nullable=False)
    montant: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    libelle: Mapped[str | None] = mapped_column(String(255), nullable=True)