"""Règles métier du module entreprises.

Toutes les écritures de ce service sont des actions d'administration
(cahier, section 26) : chaque méthode qui écrit prend `auteur_id`, fourni
par le router à partir de l'administrateur authentifié.
"""

import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import RessourceIntrouvable, ValidationMetier
from app.modules.droits.service import CODE_ROLE_ADMINISTRATEUR_ENTREPRISE, ServiceDroits
from app.modules.entreprises.models import Entreprise, StatutEntreprise
from app.modules.entreprises.repository import RepositoryEntreprises
from app.modules.journal_activite.models import TypeAction
from app.modules.journal_activite.service import ServiceJournalActivite


class ServiceEntreprises:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.entreprises = RepositoryEntreprises(db)
        self.journal = ServiceJournalActivite(db)

    def creer_entreprise(
        self,
        *,
        auteur_id: uuid.UUID,
        raison_sociale: str,
        sigle: str | None = None,
        forme_juridique: str | None = None,
        activite: str | None = None,
        adresse: str | None = None,
        email_contact: str | None = None,
        telephone_contact: str | None = None,
        referentiel_comptable: str = "SYSCOHADA",
        devise: str = "XOF",
        secteur: str | None = None,
        taille: str | None = None,
        niveau_risque: str | None = None,
        priorite: str | None = None,
        blocage_ecritures_cloture: bool = True,
    ) -> Entreprise:
        entreprise = Entreprise(
            raison_sociale=raison_sociale,
            sigle=sigle,
            forme_juridique=forme_juridique,
            activite=activite,
            adresse=adresse,
            email_contact=email_contact,
            telephone_contact=telephone_contact,
            referentiel_comptable=referentiel_comptable,
            devise=devise,
            secteur=secteur,
            taille=taille,
            niveau_risque=niveau_risque,
            priorite=priorite,
            blocage_ecritures_cloture=blocage_ecritures_cloture,
        )
        self.entreprises.ajouter(entreprise)
        self.db.flush()  # entreprise.id doit exister avant l'affectation ci-dessous
        self.journal.enregistrer(
            module="entreprises",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            entreprise_id=entreprise.id,
            type_objet="Entreprise",
            objet_id=entreprise.id,
            description=f"Création de l'entreprise '{raison_sociale}'.",
            valeurs_apres={"raison_sociale": raison_sociale, "statut": entreprise.statut},
        )

        # Onboarding automatique (Étape 6 — auto-gestion des entreprises) :
        # le créateur est affecté au rôle "Administrateur d'entreprise" dès
        # la création, ce qui lui permet ensuite d'inviter lui-même ses
        # collaborateurs et comptes clients sans repasser par l'administrateur
        # de plateforme pour chaque affectation. Si ce rôle n'est pas encore
        # seedé en base (migration a2f6c9e1b438 pas encore appliquée), on ne
        # bloque pas la création de l'entreprise pour autant — on se contente
        # de sauter cette étape, rattrapable manuellement ensuite.
        service_droits = ServiceDroits(self.db)
        role_administrateur_entreprise = service_droits.roles.obtenir_par_code(
            CODE_ROLE_ADMINISTRATEUR_ENTREPRISE
        )
        if role_administrateur_entreprise is not None:
            service_droits.affecter_utilisateur(
                auteur_id=auteur_id,
                utilisateur_id=auteur_id,
                entreprise_id=entreprise.id,
                role_id=role_administrateur_entreprise.id,
            )
        return entreprise

    def mettre_a_jour_fiche(
        self,
        entreprise_id: uuid.UUID,
        *,
        auteur_id: uuid.UUID,
        raison_sociale: str | None = None,
        sigle: str | None = None,
        forme_juridique: str | None = None,
        activite: str | None = None,
        adresse: str | None = None,
        email_contact: str | None = None,
        telephone_contact: str | None = None,
        referentiel_comptable: str | None = None,
        devise: str | None = None,
        secteur: str | None = None,
        taille: str | None = None,
        niveau_risque: str | None = None,
        priorite: str | None = None,
        blocage_ecritures_cloture: bool | None = None,
    ) -> Entreprise:
        """Met à jour uniquement les champs fournis (non None).

        Le statut n'est volontairement pas modifiable ici : il passe par
        `archiver`, `suspendre` ou `reactiver`, qui portent chacun leur
        propre règle plutôt qu'une simple affectation de valeur.
        """
        entreprise = self._obtenir_ou_lever(entreprise_id)

        champs = {
            "raison_sociale": raison_sociale,
            "sigle": sigle,
            "forme_juridique": forme_juridique,
            "activite": activite,
            "adresse": adresse,
            "email_contact": email_contact,
            "telephone_contact": telephone_contact,
            "referentiel_comptable": referentiel_comptable,
            "devise": devise,
            "secteur": secteur,
            "taille": taille,
            "niveau_risque": niveau_risque,
            "priorite": priorite,
            "blocage_ecritures_cloture": blocage_ecritures_cloture,
        }
        champs_modifies = {k: v for k, v in champs.items() if v is not None}
        valeurs_avant = {k: getattr(entreprise, k) for k in champs_modifies}
        for nom_champ, valeur in champs_modifies.items():
            setattr(entreprise, nom_champ, valeur)

        self.db.flush()
        if champs_modifies:
            self.journal.enregistrer(
                module="entreprises",
                type_action=TypeAction.MODIFIER,
                utilisateur_id=auteur_id,
                entreprise_id=entreprise.id,
                type_objet="Entreprise",
                objet_id=entreprise.id,
                description=f"Modification de la fiche de '{entreprise.raison_sociale}'.",
                valeurs_avant=valeurs_avant,
                valeurs_apres=champs_modifies,
            )
        return entreprise

    def archiver(self, entreprise_id: uuid.UUID, *, auteur_id: uuid.UUID) -> None:
        self._changer_statut(entreprise_id, StatutEntreprise.ARCHIVEE, auteur_id=auteur_id)

    def suspendre(self, entreprise_id: uuid.UUID, *, auteur_id: uuid.UUID) -> None:
        self._changer_statut(entreprise_id, StatutEntreprise.SUSPENDUE, auteur_id=auteur_id)

    def reactiver(self, entreprise_id: uuid.UUID, *, auteur_id: uuid.UUID) -> None:
        self._changer_statut(entreprise_id, StatutEntreprise.ACTIVE, auteur_id=auteur_id)

    def obtenir_entreprise(self, entreprise_id: uuid.UUID) -> Entreprise:
        return self._obtenir_ou_lever(entreprise_id)

    def lister_entreprises(self, *, limite: int = 100, decalage: int = 0) -> list[Entreprise]:
        return self.entreprises.lister(limite=limite, decalage=decalage)

    def rechercher_entreprises(self, terme: str) -> list[Entreprise]:
        return self.entreprises.rechercher(terme)

    # --- Aides internes ---------------------------------------------------

    def _obtenir_ou_lever(self, entreprise_id: uuid.UUID) -> Entreprise:
        entreprise = self.entreprises.obtenir(entreprise_id)
        if entreprise is None:
            raise RessourceIntrouvable("Entreprise introuvable.")
        return entreprise

    def _changer_statut(
        self, entreprise_id: uuid.UUID, statut: StatutEntreprise, *, auteur_id: uuid.UUID
    ) -> None:
        entreprise = self._obtenir_ou_lever(entreprise_id)
        if entreprise.statut == statut.value:
            raise ValidationMetier(f"L'entreprise est déjà au statut '{statut.value}'.")
        statut_avant = entreprise.statut
        entreprise.statut = statut.value
        self.db.flush()
        self.journal.enregistrer(
            module="entreprises",
            type_action=TypeAction.ARCHIVER
            if statut == StatutEntreprise.ARCHIVEE
            else TypeAction.MODIFIER,
            utilisateur_id=auteur_id,
            entreprise_id=entreprise.id,
            type_objet="Entreprise",
            objet_id=entreprise.id,
            description=f"Changement de statut vers '{statut.value}'.",
            valeurs_avant={"statut": statut_avant},
            valeurs_apres={"statut": statut.value},
        )