"""Modèle du module interlocuteurs (cahier des charges, section 7.1).

Une seule table, `Interlocuteur` : dirigeants, associés, responsables
financiers, comptables et "autres contacts" partagent les mêmes champs
(identité, fonction, coordonnées) — seul `role` les distingue, d'où une
énumération plutôt que des sous-tables séparées.

Contrairement à `Entreprise.secteur`/`taille` (restés en texte libre faute
de liste fermée imposée par le cahier), `role` ICI est contraint : le
cahier des charges nomme explicitement les quatre catégories ("dirigeants,
associés, responsables financiers, comptables") plus "contacts" — une
liste fermée that le cahier fixe lui-même, donc une énumération est fidèle
au besoin plutôt qu'une invention de règle métier.

`pourcentage_detention` ne s'applique qu'aux associés (`role == ASSOCIE`)
mais reste un champ nullable commun plutôt qu'une sous-table : un
associé qui devient aussi dirigeant n'a pas besoin d'une seconde fiche.
Aucune contrainte à ce stade n'impose la somme des pourcentages à 100 —
le cahier ne le demande pas, et une entreprise peut très bien ne pas
connaître tous ses associés au moment de la saisie.

Pas de lien vers `Utilisateur` : ce sont des informations de contact
externes à l'application, indépendantes des comptes qui s'y connectent
(décision prise explicitement, voir l'historique de conception).
"""

import uuid
from enum import StrEnum

from sqlalchemy import Boolean, CheckConstraint, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base import Base
from app.shared.mixins import EntrepriseMixin, HorodatageMixin, IdentifiantMixin


class RoleInterlocuteur(StrEnum):
    DIRIGEANT = "dirigeant"
    ASSOCIE = "associe"
    RESPONSABLE_FINANCIER = "responsable_financier"
    COMPTABLE = "comptable"
    CONTACT = "contact"


class Interlocuteur(IdentifiantMixin, HorodatageMixin, EntrepriseMixin, Base):
    __tablename__ = "interlocuteurs"
    __table_args__ = (
        CheckConstraint(
            "role IN ('dirigeant', 'associe', 'responsable_financier', 'comptable', 'contact')",
            name="role_interlocuteur_valide",
        ),
        CheckConstraint(
            "pourcentage_detention IS NULL OR "
            "(pourcentage_detention >= 0 AND pourcentage_detention <= 100)",
            name="pourcentage_detention_valide",
        ),
    )

    nom: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    fonction: Mapped[str | None] = mapped_column(String(150), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telephone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # Uniquement significatif pour role == ASSOCIE (voir le docstring de
    # tête de fichier) — validé par le service, pas en base.
    pourcentage_detention: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    actif: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
