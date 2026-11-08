"""Règles métier du module paie.

Portée volontairement limitée : voir la note de tête de fichier de
`models.py`. Aucune formule CNPS/ITS ici — `creer_bulletin` se contente
de valider et de totaliser les lignes saisies par le comptable.

Trois familles de règles :

- `Employe` : matricule unique par entreprise, salaire de base strictement
  positif, désactivation/réactivation via `statut` + `date_sortie` (comme
  `CompteBancaire.actif`, mais avec en plus une date de sortie).
- `RubriquePaie` : code unique par entreprise, désactivation logique
  (`actif`) plutôt que suppression — une rubrique déjà utilisée dans des
  lignes de bulletin ne doit pas disparaître.
- `BulletinPaie` : cycle brouillon → validé, sur le même principe
  d'immuabilité qu'`Ecriture` (`ServiceComptabilite.valider_ecriture`) :
  une fois validé, plus aucune modification ni suppression. `creer_bulletin`
  recalcule `salaire_brut`/`total_retenues`/`net_a_payer` à partir des
  lignes fournies, groupées par `RubriquePaie.type_rubrique` — jamais
  saisis directement (voir `models.py`).
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import RessourceIntrouvable, ValidationMetier
from app.modules.comptabilite.models import Ecriture
from app.modules.comptabilite.repository import RepositoryComptes
from app.modules.comptabilite.service import LigneSaisie, ServiceComptabilite
from app.modules.exercices.models import StatutExercice
from app.modules.exercices.repository import RepositoryExercice
from app.modules.journal_activite.models import TypeAction
from app.modules.journal_activite.service import ServiceJournalActivite
from app.modules.paie.models import (
    BulletinPaie,
    Employe,
    LigneBulletin,
    RubriquePaie,
    StatutBulletin,
    StatutEmploye,
    TypeRubriquePaie,
)
from app.modules.paie.repository import (
    RepositoryBulletinsPaie,
    RepositoryEmployes,
    RepositoryLignesBulletin,
    RepositoryRubriquesPaie,
)


@dataclass
class LigneBulletinSaisie:
    rubrique_id: uuid.UUID
    montant: Decimal
    libelle: str | None = None


@dataclass
class BulletinCreation:
    employe_id: uuid.UUID
    exercice_id: uuid.UUID
    periode_debut: date
    periode_fin: date
    lignes: list[LigneBulletinSaisie]


class ServicePaie:
    def __init__(self, db: Session, entreprise_id: uuid.UUID) -> None:
        self.db = db
        self.entreprise_id = entreprise_id
        self.employes = RepositoryEmployes(db, entreprise_id)
        self.rubriques = RepositoryRubriquesPaie(db, entreprise_id)
        self.bulletins = RepositoryBulletinsPaie(db, entreprise_id)
        self.lignes_bulletin = RepositoryLignesBulletin(db, entreprise_id)
        self.exercices = RepositoryExercice(db, entreprise_id)
        self.comptes = RepositoryComptes(db, entreprise_id)
        self.journal_activite = ServiceJournalActivite(db)

    # --- Employés --------------------------------------------------------

    def creer_employe(
        self,
        *,
        matricule: str,
        nom: str,
        prenom: str,
        date_embauche: date,
        salaire_base: Decimal,
        poste: str | None = None,
        auteur_id: uuid.UUID,
    ) -> Employe:
        if salaire_base <= 0:
            raise ValidationMetier("Le salaire de base doit être strictement positif.")
        if self.employes.obtenir_par_matricule(matricule) is not None:
            raise ValidationMetier(f"Le matricule '{matricule}' est déjà utilisé.")

        employe = Employe(
            matricule=matricule,
            nom=nom,
            prenom=prenom,
            poste=poste,
            date_embauche=date_embauche,
            salaire_base=salaire_base,
            statut=StatutEmploye.ACTIF.value,
        )
        self.employes.ajouter(employe)
        self.journal_activite.enregistrer(
            module="paie",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Employe",
            objet_id=employe.id,
            description=f"Création de l'employé '{nom} {prenom}' (matricule {matricule}).",
            valeurs_apres={"matricule": matricule, "salaire_base": str(salaire_base)},
        )
        return employe

    def modifier_employe(
        self,
        employe_id: uuid.UUID,
        *,
        auteur_id: uuid.UUID,
        nom: str | None = None,
        prenom: str | None = None,
        poste: str | None = None,
        salaire_base: Decimal | None = None,
    ) -> Employe:
        employe = self._obtenir_employe_ou_lever(employe_id)
        if salaire_base is not None and salaire_base <= 0:
            raise ValidationMetier("Le salaire de base doit être strictement positif.")

        if nom is not None:
            employe.nom = nom
        if prenom is not None:
            employe.prenom = prenom
        if poste is not None:
            employe.poste = poste
        if salaire_base is not None:
            employe.salaire_base = salaire_base
        self.db.flush()

        self.journal_activite.enregistrer(
            module="paie",
            type_action=TypeAction.MODIFIER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Employe",
            objet_id=employe.id,
            description=f"Modification de l'employé '{employe.nom} {employe.prenom}'.",
        )
        return employe

    def desactiver_employe(
        self, employe_id: uuid.UUID, *, date_sortie: date, auteur_id: uuid.UUID
    ) -> Employe:
        employe = self._obtenir_employe_ou_lever(employe_id)
        if employe.statut == StatutEmploye.INACTIF.value:
            raise ValidationMetier("Cet employé est déjà inactif.")
        if date_sortie < employe.date_embauche:
            raise ValidationMetier("La date de sortie ne peut pas précéder la date d'embauche.")

        employe.statut = StatutEmploye.INACTIF.value
        employe.date_sortie = date_sortie
        self.db.flush()

        self.journal_activite.enregistrer(
            module="paie",
            type_action=TypeAction.MODIFIER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Employe",
            objet_id=employe.id,
            description=f"Désactivation de l'employé '{employe.nom} {employe.prenom}'.",
            valeurs_avant={"statut": StatutEmploye.ACTIF.value},
            valeurs_apres={"statut": StatutEmploye.INACTIF.value, "date_sortie": str(date_sortie)},
        )
        return employe

    def reactiver_employe(self, employe_id: uuid.UUID, *, auteur_id: uuid.UUID) -> Employe:
        employe = self._obtenir_employe_ou_lever(employe_id)
        if employe.statut == StatutEmploye.ACTIF.value:
            raise ValidationMetier("Cet employé est déjà actif.")

        employe.statut = StatutEmploye.ACTIF.value
        employe.date_sortie = None
        self.db.flush()

        self.journal_activite.enregistrer(
            module="paie",
            type_action=TypeAction.MODIFIER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Employe",
            objet_id=employe.id,
            description=f"Réactivation de l'employé '{employe.nom} {employe.prenom}'.",
            valeurs_avant={"statut": StatutEmploye.INACTIF.value},
            valeurs_apres={"statut": StatutEmploye.ACTIF.value},
        )
        return employe

    def obtenir_employe(self, employe_id: uuid.UUID) -> Employe:
        return self._obtenir_employe_ou_lever(employe_id)

    def lister_employes(self, *, actifs_seulement: bool = True) -> list[Employe]:
        return self.employes.lister(actifs_seulement=actifs_seulement)

    # --- Rubriques de paie -------------------------------------------------

    def creer_rubrique(
        self,
        *,
        code: str,
        libelle: str,
        type_rubrique: TypeRubriquePaie,
        auteur_id: uuid.UUID,
        compte_comptable_id: uuid.UUID | None = None,
    ) -> RubriquePaie:
        if self.rubriques.obtenir_par_code(code) is not None:
            raise ValidationMetier(f"Le code de rubrique '{code}' est déjà utilisé.")
        if compte_comptable_id is not None and self.comptes.obtenir(compte_comptable_id) is None:
            raise RessourceIntrouvable("Compte comptable introuvable.")

        rubrique = RubriquePaie(
            code=code,
            libelle=libelle,
            type_rubrique=type_rubrique.value,
            actif=True,
            compte_comptable_id=compte_comptable_id,
        )
        self.rubriques.ajouter(rubrique)
        self.journal_activite.enregistrer(
            module="paie",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="RubriquePaie",
            objet_id=rubrique.id,
            description=f"Création de la rubrique '{code}' ({libelle}).",
            valeurs_apres={"code": code, "type_rubrique": type_rubrique.value},
        )
        return rubrique

    def definir_compte_comptable(
        self, rubrique_id: uuid.UUID, *, compte_comptable_id: uuid.UUID, auteur_id: uuid.UUID
    ) -> RubriquePaie:
        """Affecte (ou change) le compte comptable d'une rubrique —
        nécessaire avant de pouvoir générer une écriture à partir d'un
        bulletin qui l'utilise (voir `generer_ecriture_bulletin`)."""
        rubrique = self._obtenir_rubrique_ou_lever(rubrique_id)
        if self.comptes.obtenir(compte_comptable_id) is None:
            raise RessourceIntrouvable("Compte comptable introuvable.")

        rubrique.compte_comptable_id = compte_comptable_id
        self.db.flush()

        self.journal_activite.enregistrer(
            module="paie",
            type_action=TypeAction.MODIFIER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="RubriquePaie",
            objet_id=rubrique.id,
            description=f"Affectation du compte comptable de la rubrique '{rubrique.code}'.",
        )
        return rubrique

    def desactiver_rubrique(self, rubrique_id: uuid.UUID, *, auteur_id: uuid.UUID) -> RubriquePaie:
        rubrique = self._obtenir_rubrique_ou_lever(rubrique_id)
        if not rubrique.actif:
            raise ValidationMetier("Cette rubrique est déjà désactivée.")

        rubrique.actif = False
        self.db.flush()

        self.journal_activite.enregistrer(
            module="paie",
            type_action=TypeAction.MODIFIER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="RubriquePaie",
            objet_id=rubrique.id,
            description=f"Désactivation de la rubrique '{rubrique.code}'.",
            valeurs_avant={"actif": True},
            valeurs_apres={"actif": False},
        )
        return rubrique

    def obtenir_rubrique(self, rubrique_id: uuid.UUID) -> RubriquePaie:
        return self._obtenir_rubrique_ou_lever(rubrique_id)

    def lister_rubriques(self, *, actifs_seulement: bool = True) -> list[RubriquePaie]:
        return self.rubriques.lister(actifs_seulement=actifs_seulement)

    # --- Bulletins de paie --------------------------------------------------

    def creer_bulletin(self, donnees: BulletinCreation, *, auteur_id: uuid.UUID) -> BulletinPaie:
        employe = self._obtenir_employe_ou_lever(donnees.employe_id)
        if employe.statut != StatutEmploye.ACTIF.value:
            raise ValidationMetier("Impossible d'établir un bulletin pour un employé inactif.")

        exercice = self.exercices.obtenir(donnees.exercice_id)
        if exercice is None:
            raise RessourceIntrouvable("Exercice introuvable.")
        if exercice.statut != StatutExercice.OUVERT.value:
            raise ValidationMetier("Impossible d'établir un bulletin sur un exercice clôturé.")

        if donnees.periode_fin <= donnees.periode_debut:
            raise ValidationMetier("La période de fin doit être postérieure à la période de début.")

        if self.bulletins.obtenir_pour_periode(
            donnees.employe_id, donnees.periode_debut, donnees.periode_fin
        ) is not None:
            raise ValidationMetier("Un bulletin existe déjà pour cet employé sur cette période.")

        if not donnees.lignes:
            raise ValidationMetier("Un bulletin doit comporter au moins une ligne.")

        rubriques_par_id = self._valider_lignes(donnees.lignes)

        salaire_brut, total_retenues = self._totaliser(donnees.lignes, rubriques_par_id)
        net_a_payer = salaire_brut - total_retenues

        bulletin = BulletinPaie(
            employe_id=donnees.employe_id,
            exercice_id=donnees.exercice_id,
            periode_debut=donnees.periode_debut,
            periode_fin=donnees.periode_fin,
            statut=StatutBulletin.BROUILLON.value,
            salaire_brut=salaire_brut,
            total_retenues=total_retenues,
            net_a_payer=net_a_payer,
        )
        self.bulletins.ajouter(bulletin)
        self.db.flush()

        for ligne in donnees.lignes:
            self.lignes_bulletin.ajouter(
                LigneBulletin(
                    bulletin_id=bulletin.id,
                    rubrique_id=ligne.rubrique_id,
                    libelle=ligne.libelle,
                    montant=ligne.montant,
                )
            )

        self.journal_activite.enregistrer(
            module="paie",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="BulletinPaie",
            objet_id=bulletin.id,
            description=(
                f"Création du bulletin de '{employe.nom} {employe.prenom}' pour la "
                f"période {donnees.periode_debut} - {donnees.periode_fin}."
            ),
            valeurs_apres={"salaire_brut": str(salaire_brut), "net_a_payer": str(net_a_payer)},
        )
        return bulletin

    def modifier_bulletin(
        self, bulletin_id: uuid.UUID, *, lignes: list[LigneBulletinSaisie], auteur_id: uuid.UUID
    ) -> BulletinPaie:
        bulletin = self._obtenir_bulletin_ou_lever(bulletin_id)
        if bulletin.statut != StatutBulletin.BROUILLON.value:
            raise ValidationMetier("Seul un bulletin en brouillon peut être modifié.")
        if not lignes:
            raise ValidationMetier("Un bulletin doit comporter au moins une ligne.")

        rubriques_par_id = self._valider_lignes(lignes)
        salaire_brut, total_retenues = self._totaliser(lignes, rubriques_par_id)

        self.lignes_bulletin.supprimer_pour_bulletin(bulletin_id)
        for ligne in lignes:
            self.lignes_bulletin.ajouter(
                LigneBulletin(
                    bulletin_id=bulletin.id,
                    rubrique_id=ligne.rubrique_id,
                    libelle=ligne.libelle,
                    montant=ligne.montant,
                )
            )

        bulletin.salaire_brut = salaire_brut
        bulletin.total_retenues = total_retenues
        bulletin.net_a_payer = salaire_brut - total_retenues
        self.db.flush()

        self.journal_activite.enregistrer(
            module="paie",
            type_action=TypeAction.MODIFIER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="BulletinPaie",
            objet_id=bulletin.id,
            description="Modification des lignes du bulletin.",
            valeurs_apres={"salaire_brut": str(salaire_brut), "net_a_payer": str(bulletin.net_a_payer)},
        )
        return bulletin

    def supprimer_bulletin(self, bulletin_id: uuid.UUID, *, auteur_id: uuid.UUID) -> None:
        bulletin = self._obtenir_bulletin_ou_lever(bulletin_id)
        if bulletin.statut != StatutBulletin.BROUILLON.value:
            raise ValidationMetier("Seul un bulletin en brouillon peut être supprimé.")

        self.lignes_bulletin.supprimer_pour_bulletin(bulletin_id)
        self.bulletins.supprimer(bulletin)

        self.journal_activite.enregistrer(
            module="paie",
            type_action=TypeAction.SUPPRIMER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="BulletinPaie",
            objet_id=bulletin_id,
            description="Suppression d'un bulletin en brouillon.",
        )

    def valider_bulletin(self, bulletin_id: uuid.UUID, *, auteur_id: uuid.UUID) -> BulletinPaie:
        bulletin = self._obtenir_bulletin_ou_lever(bulletin_id)
        if bulletin.statut == StatutBulletin.VALIDE.value:
            raise ValidationMetier("Ce bulletin est déjà validé.")

        bulletin.statut = StatutBulletin.VALIDE.value
        self.db.flush()

        self.journal_activite.enregistrer(
            module="paie",
            type_action=TypeAction.VALIDER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="BulletinPaie",
            objet_id=bulletin.id,
            description="Validation du bulletin (devient immuable).",
            valeurs_avant={"statut": StatutBulletin.BROUILLON.value},
            valeurs_apres={"statut": StatutBulletin.VALIDE.value},
        )
        return bulletin

    def generer_ecriture_bulletin(
        self,
        bulletin_id: uuid.UUID,
        *,
        journal_id: uuid.UUID,
        compte_net_a_payer_id: uuid.UUID,
        auteur_id: uuid.UUID,
    ) -> Ecriture:
        """Comptabilise un bulletin déjà validé : une ligne de débit par
        rubrique de type `gain` (compte de charge de la rubrique), une
        ligne de crédit par rubrique de type `retenue` (compte de dette de
        la rubrique), et une ligne de crédit pour le net à payer sur
        `compte_net_a_payer_id` — ce dernier n'est pas stocké sur le
        modèle (il peut varier, ex. selon le mode de paiement) : il est
        fourni à l'appel, comme le compte de contrepartie dans
        `stocks.ServiceStocks.generer_ecriture_mouvement`.

        L'équilibre est garanti par construction : somme des gains
        (débits) = salaire_brut = total_retenues (crédits) + net_a_payer
        (crédit) — `ServiceComptabilite.creer_ecriture` le revérifie
        quand même, comme pour toute écriture."""
        bulletin = self._obtenir_bulletin_ou_lever(bulletin_id)
        if bulletin.statut != StatutBulletin.VALIDE.value:
            raise ValidationMetier("Seul un bulletin validé peut être comptabilisé.")
        if bulletin.ecriture_id is not None:
            raise ValidationMetier("Ce bulletin a déjà une écriture générée.")

        employe = self._obtenir_employe_ou_lever(bulletin.employe_id)
        if self.comptes.obtenir(compte_net_a_payer_id) is None:
            raise RessourceIntrouvable("Compte comptable introuvable.")

        lignes_bulletin = self.lignes_bulletin.lister_pour_bulletin(bulletin_id)
        totaux_par_rubrique: dict[uuid.UUID, Decimal] = {}
        for ligne in lignes_bulletin:
            totaux_par_rubrique[ligne.rubrique_id] = (
                totaux_par_rubrique.get(ligne.rubrique_id, Decimal("0")) + ligne.montant
            )

        lignes_saisies: list[LigneSaisie] = []
        for rubrique_id, montant in totaux_par_rubrique.items():
            rubrique = self._obtenir_rubrique_ou_lever(rubrique_id)
            if rubrique.compte_comptable_id is None:
                raise ValidationMetier(
                    f"La rubrique '{rubrique.code}' n'a pas de compte comptable configuré "
                    "(voir `definir_compte_comptable`)."
                )
            if rubrique.type_rubrique == TypeRubriquePaie.GAIN.value:
                lignes_saisies.append(LigneSaisie(compte_id=rubrique.compte_comptable_id, debit=montant))
            else:
                lignes_saisies.append(LigneSaisie(compte_id=rubrique.compte_comptable_id, credit=montant))

        if bulletin.net_a_payer > 0:
            lignes_saisies.append(
                LigneSaisie(compte_id=compte_net_a_payer_id, credit=bulletin.net_a_payer)
            )

        service_comptabilite = ServiceComptabilite(self.db, self.entreprise_id)
        ecriture = service_comptabilite.creer_ecriture(
            auteur_id=auteur_id,
            journal_id=journal_id,
            exercice_id=bulletin.exercice_id,
            date_ecriture=bulletin.periode_fin,
            libelle=(
                f"Paie {employe.nom} {employe.prenom} - période "
                f"{bulletin.periode_debut} au {bulletin.periode_fin}"
            ),
            lignes=lignes_saisies,
        )

        bulletin.ecriture_id = ecriture.id
        self.db.flush()

        self.journal_activite.enregistrer(
            module="paie",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="BulletinPaie",
            objet_id=bulletin.id,
            description=f"Génération de l'écriture de paie pour '{employe.nom} {employe.prenom}'.",
            valeurs_apres={"ecriture_id": str(ecriture.id)},
        )
        return ecriture

    def obtenir_bulletin(self, bulletin_id: uuid.UUID) -> BulletinPaie:
        return self._obtenir_bulletin_ou_lever(bulletin_id)

    def lister_bulletins(
        self,
        *,
        employe_id: uuid.UUID | None = None,
        exercice_id: uuid.UUID | None = None,
        statut: str | None = None,
    ) -> list[BulletinPaie]:
        return self.bulletins.lister(employe_id=employe_id, exercice_id=exercice_id, statut=statut)

    def lister_lignes(self, bulletin_id: uuid.UUID) -> list[LigneBulletin]:
        return self.lignes_bulletin.lister_pour_bulletin(bulletin_id)

    # --- Aides internes ------------------------------------------------------

    def _valider_lignes(
        self, lignes: list[LigneBulletinSaisie]
    ) -> dict[uuid.UUID, RubriquePaie]:
        rubriques_par_id: dict[uuid.UUID, RubriquePaie] = {}
        for ligne in lignes:
            if ligne.montant < 0:
                raise ValidationMetier("Le montant d'une ligne ne peut pas être négatif.")
            if ligne.rubrique_id not in rubriques_par_id:
                rubrique = self.rubriques.obtenir(ligne.rubrique_id)
                if rubrique is None:
                    raise RessourceIntrouvable("Rubrique de paie introuvable.")
                if not rubrique.actif:
                    raise ValidationMetier(f"La rubrique '{rubrique.code}' est désactivée.")
                rubriques_par_id[ligne.rubrique_id] = rubrique
        return rubriques_par_id

    def _totaliser(
        self, lignes: list[LigneBulletinSaisie], rubriques_par_id: dict[uuid.UUID, RubriquePaie]
    ) -> tuple[Decimal, Decimal]:
        salaire_brut = Decimal("0")
        total_retenues = Decimal("0")
        for ligne in lignes:
            rubrique = rubriques_par_id[ligne.rubrique_id]
            if rubrique.type_rubrique == TypeRubriquePaie.GAIN.value:
                salaire_brut += ligne.montant
            else:
                total_retenues += ligne.montant
        return salaire_brut, total_retenues

    def _obtenir_employe_ou_lever(self, employe_id: uuid.UUID) -> Employe:
        employe = self.employes.obtenir(employe_id)
        if employe is None:
            raise RessourceIntrouvable("Employé introuvable.")
        return employe

    def _obtenir_rubrique_ou_lever(self, rubrique_id: uuid.UUID) -> RubriquePaie:
        rubrique = self.rubriques.obtenir(rubrique_id)
        if rubrique is None:
            raise RessourceIntrouvable("Rubrique de paie introuvable.")
        return rubrique

    def _obtenir_bulletin_ou_lever(self, bulletin_id: uuid.UUID) -> BulletinPaie:
        bulletin = self.bulletins.obtenir(bulletin_id)
        if bulletin is None:
            raise RessourceIntrouvable("Bulletin de paie introuvable.")
        return bulletin