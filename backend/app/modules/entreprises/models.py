"""Modèle du module entreprises.

`Entreprise` est la racine du cloisonnement des données (cahier des
charges, section 5 et Annexe B) : c'est elle que `EntrepriseMixin` référence
et que `RepositoryEntreprise` filtre partout ailleurs dans l'application.
Elle-même n'a donc pas d'`entreprise_id` — elle EST le périmètre.

Les champs de classification (`secteur`, `taille`, `niveau_risque`,
`priorite`) restent des chaînes libres et non des énumérations strictes :
le cahier des charges présente ces critères sans fixer leurs valeurs
possibles, et les qualifie lui-même de propositions à valider en atelier.
Y figer des valeurs maintenant reviendrait à inventer une règle métier non
demandée. `statut`, en revanche, conditionne l'accès aux données (une
entreprise archivée doit pouvoir être consultée mais plus modifiée), donc
il est contraint dès maintenant.

Les interlocuteurs (dirigeants, associés, contacts) vivent dans leur
propre module (`interlocuteurs`) et les documents permanents (section
7.1) dans `documents` — ce ne sont pas des champs de cette table.
"""

from enum import StrEnum

from sqlalchemy import Boolean, CheckConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base import Base
from app.shared.mixins import HorodatageMixin, IdentifiantMixin


class StatutEntreprise(StrEnum):
    ACTIVE = "active"
    SUSPENDUE = "suspendue"
    ARCHIVEE = "archivee"


class Entreprise(IdentifiantMixin, HorodatageMixin, Base):
    __tablename__ = "entreprises"
    __table_args__ = (
        CheckConstraint(
            "statut IN ('active', 'suspendue', 'archivee')",
            name="statut_valide",
        ),
    )

    # --- Identification (cahier, section 7.1) -------------------------
    raison_sociale: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sigle: Mapped[str | None] = mapped_column(String(50), nullable=True)
    forme_juridique: Mapped[str | None] = mapped_column(String(100), nullable=True)
    activite: Mapped[str | None] = mapped_column(String(255), nullable=True)
    adresse: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telephone_contact: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # --- Paramètres comptables (cahier, section 7.1) -------------------
    # SYSCOHADA et le franc CFA (XOF) sont les valeurs par défaut cohérentes
    # avec la "zone cible initiale" du cahier (Côte d'Ivoire / OHADA),
    # mais restent modifiables entreprise par entreprise.
    referentiel_comptable: Mapped[str] = mapped_column(
        String(50), nullable=False, default="SYSCOHADA"
    )
    devise: Mapped[str] = mapped_column(String(3), nullable=False, default="XOF")

    # --- Classification (cahier, section 7.3) --------------------------
    secteur: Mapped[str | None] = mapped_column(String(100), nullable=True)
    taille: Mapped[str | None] = mapped_column(String(50), nullable=True)
    niveau_risque: Mapped[str | None] = mapped_column(String(50), nullable=True)
    priorite: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # --- Cycle de vie ----------------------------------------------------
    statut: Mapped[str] = mapped_column(
        String(20), nullable=False, default=StatutEntreprise.ACTIVE.value
    )

    # --- Options de clôture (cahier, section 7.1 "options de clôture" et
    # 7.2 "blocage des écritures après clôture selon paramétrage") -------
    # `True` par défaut : préserve le comportement historique (blocage
    # strict, non paramétrable) pour toute entreprise déjà en base — voir
    # `ServiceComptabilite._verifier_exercice_ouvert`, seul endroit qui lit
    # ce champ.
    blocage_ecritures_cloture: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)