"""Règles métier du module interlocuteurs.

`ServiceInterlocuteurs` : construit avec `(db, entreprise_id)`, comme
`ServiceDocuments`/`ServiceTresorerie`.

La seule règle métier propre à ce module : `pourcentage_detention` n'a de
sens que pour un associé (voir le docstring de `models.py`) — le service
refuse de l'enregistrer pour tout autre rôle plutôt que de l'accepter
silencieusement et de laisser une donnée incohérente en base. Sur
`modifier_interlocuteur`, si le rôle final (après fusion des champs
fournis) n'est plus "associe", `pourcentage_detention` est remis à `None`
automatiquement plutôt que de lever une erreur — un changement de rôle
est une opération légitime même si l'appelant n'a pas pensé à vider ce
champ lui-même.

Pas de suppression physique : `desactiver`/`reactiver` (comme
`Compte.actif`/`Journal.actif`), pour conserver la traçabilité d'un
interlocuteur qui ne serait plus en poste (un dirigeant qui part reste
visible dans l'historique) plutôt que de perdre l'information.

`modifier_interlocuteur` est une mise à jour PARTIELLE : seuls les champs
non-`None` transmis sont appliqués, même convention que
`ServiceTiers.modifier_tiers`/`ServiceDocuments.modifier_document` — pas
un remplacement intégral de la fiche.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.exceptions import RessourceIntrouvable, ValidationMetier
from app.modules.interlocuteurs.models import Interlocuteur, RoleInterlocuteur
from app.modules.interlocuteurs.repository import RepositoryInterlocuteurs
from app.modules.journal_activite.models import TypeAction
from app.modules.journal_activite.service import ServiceJournalActivite

ROLES_VALIDES = {r.value for r in RoleInterlocuteur}


@dataclass
class InterlocuteurCreationDonnees:
    nom: str
    role: str
    fonction: str | None = None
    email: str | None = None
    telephone: str | None = None
    pourcentage_detention: float | None = None
    notes: str | None = None


def _valider_role(role: str) -> None:
    if role not in ROLES_VALIDES:
        raise ValidationMetier(f"Rôle d'interlocuteur invalide : '{role}'.")


def _valider_pourcentage(role: str, pourcentage: float | None) -> None:
    if pourcentage is None:
        return
    if role != RoleInterlocuteur.ASSOCIE.value:
        raise ValidationMetier("Le pourcentage de détention ne s'applique qu'aux associés.")
    if not (0 <= pourcentage <= 100):
        raise ValidationMetier("Le pourcentage de détention doit être entre 0 et 100.")


class ServiceInterlocuteurs:
    def __init__(self, db: Session, entreprise_id: uuid.UUID) -> None:
        self.db = db
        self.entreprise_id = entreprise_id
        self.interlocuteurs = RepositoryInterlocuteurs(db, entreprise_id)
        self.journal_activite = ServiceJournalActivite(db)

    def creer_interlocuteur(
        self, donnees: InterlocuteurCreationDonnees, *, auteur_id: uuid.UUID
    ) -> Interlocuteur:
        _valider_role(donnees.role)
        _valider_pourcentage(donnees.role, donnees.pourcentage_detention)
        interlocuteur = Interlocuteur(
            nom=donnees.nom,
            role=donnees.role,
            fonction=donnees.fonction,
            email=donnees.email,
            telephone=donnees.telephone,
            pourcentage_detention=donnees.pourcentage_detention,
            notes=donnees.notes,
        )
        self.interlocuteurs.ajouter(interlocuteur)
        self.journal_activite.enregistrer(
            module="interlocuteur",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Interlocuteur",
            objet_id=interlocuteur.id,
            description=f"Ajout de l'interlocuteur '{donnees.nom}' ({donnees.role}).",
            valeurs_apres={"nom": donnees.nom, "role": donnees.role},
        )
        return interlocuteur

    def modifier_interlocuteur(
        self,
        interlocuteur_id: uuid.UUID,
        *,
        auteur_id: uuid.UUID,
        nom: str | None = None,
        role: str | None = None,
        fonction: str | None = None,
        email: str | None = None,
        telephone: str | None = None,
        pourcentage_detention: float | None = None,
        notes: str | None = None,
    ) -> Interlocuteur:
        """Mise à jour partielle — voir le docstring de tête de fichier."""
        interlocuteur = self._obtenir_ou_lever(interlocuteur_id)

        if nom is not None:
            interlocuteur.nom = nom
        if role is not None:
            _valider_role(role)
            interlocuteur.role = role
        if fonction is not None:
            interlocuteur.fonction = fonction
        if email is not None:
            interlocuteur.email = email
        if telephone is not None:
            interlocuteur.telephone = telephone
        if pourcentage_detention is not None:
            _valider_pourcentage(interlocuteur.role, pourcentage_detention)
            interlocuteur.pourcentage_detention = pourcentage_detention
        if notes is not None:
            interlocuteur.notes = notes

        # Invariant à maintenir après fusion, pas seulement sur le delta
        # fourni : un changement de rôle qui quitte "associe" vide le
        # pourcentage plutôt que de laisser une donnée incohérente (voir
        # le docstring de tête de fichier).
        if interlocuteur.role != RoleInterlocuteur.ASSOCIE.value:
            interlocuteur.pourcentage_detention = None

        self.db.flush()

        self.journal_activite.enregistrer(
            module="interlocuteur",
            type_action=TypeAction.MODIFIER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Interlocuteur",
            objet_id=interlocuteur.id,
            description=f"Modification de l'interlocuteur '{interlocuteur.nom}'.",
        )
        return interlocuteur

    def desactiver_interlocuteur(
        self, interlocuteur_id: uuid.UUID, *, auteur_id: uuid.UUID
    ) -> Interlocuteur:
        interlocuteur = self._obtenir_ou_lever(interlocuteur_id)
        if not interlocuteur.actif:
            raise ValidationMetier("Cet interlocuteur est déjà désactivé.")
        interlocuteur.actif = False
        self.db.flush()

        self.journal_activite.enregistrer(
            module="interlocuteur",
            type_action=TypeAction.MODIFIER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Interlocuteur",
            objet_id=interlocuteur.id,
            description=f"Désactivation de l'interlocuteur '{interlocuteur.nom}'.",
            valeurs_apres={"actif": False},
        )
        return interlocuteur

    def reactiver_interlocuteur(
        self, interlocuteur_id: uuid.UUID, *, auteur_id: uuid.UUID
    ) -> Interlocuteur:
        interlocuteur = self._obtenir_ou_lever(interlocuteur_id)
        if interlocuteur.actif:
            raise ValidationMetier("Cet interlocuteur est déjà actif.")
        interlocuteur.actif = True
        self.db.flush()

        self.journal_activite.enregistrer(
            module="interlocuteur",
            type_action=TypeAction.MODIFIER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Interlocuteur",
            objet_id=interlocuteur.id,
            description=f"Réactivation de l'interlocuteur '{interlocuteur.nom}'.",
            valeurs_apres={"actif": True},
        )
        return interlocuteur

    def obtenir_interlocuteur(self, interlocuteur_id: uuid.UUID) -> Interlocuteur:
        return self._obtenir_ou_lever(interlocuteur_id)

    def lister_interlocuteurs(
        self, *, role: str | None = None, actifs_seulement: bool = True
    ) -> list[Interlocuteur]:
        return self.interlocuteurs.lister(role=role, actifs_seulement=actifs_seulement)

    def _obtenir_ou_lever(self, interlocuteur_id: uuid.UUID) -> Interlocuteur:
        interlocuteur = self.interlocuteurs.obtenir(interlocuteur_id)
        if interlocuteur is None:
            raise RessourceIntrouvable("Interlocuteur introuvable.")
        return interlocuteur
