"""Règles métier du module tresorerie.

`ServiceTresorerie` : construit avec `(db, entreprise_id)`, comme
`ServiceComptabilite`. Gère les comptes bancaires, les relevés (+ leurs
lignes) et le rapprochement.

Convention de rapprochement — point le plus délicat du module, à bien
avoir en tête : `LigneReleve.debit`/`credit` suit la convention d'un
relevé bancaire tel qu'il est imprimé (colonne "Débit" = sortie d'argent,
colonne "Crédit" = entrée), alors que `LigneEcriture.debit`/`credit` suit
la convention comptable usuelle sur le compte bancaire lui-même, qui est
un compte d'actif (classe 5) : un débit l'augmente (entrée), un crédit le
diminue (sortie). Les deux conventions sont donc MIROIR l'une de l'autre
sur ce point précis (une entrée bancaire est un crédit côté relevé mais un
débit côté écriture) — c'est la réalité du rapprochement bancaire, pas une
incohérence du modèle. `rapprocher` compare donc :
    (somme crédits relevé - somme débits relevé)
contre :
    (somme débits écriture - somme crédits écriture)
— les deux expriment la même chose : la variation nette de trésorerie sur
les lignes sélectionnées.

`ReleveBancaire` n'a pas d'immuabilité façon `Ecriture` (voir models.py) :
`modifier_releve`/`supprimer_releve` refusent seulement de toucher à une
ligne déjà rapprochée (`code_lettrage` renseigné), pour ne pas casser un
rapprochement existant sans passer par `annuler_rapprochement`.
"""

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import Conflit, RessourceIntrouvable, ValidationMetier
from app.modules.comptabilite.repository import RepositoryComptes, RepositoryJournaux, RepositoryLignesEcriture
from app.modules.journal_activite.models import TypeAction
from app.modules.journal_activite.service import ServiceJournalActivite
from app.modules.tresorerie.models import CompteBancaire, LigneReleve, ReleveBancaire
from app.modules.tresorerie.repository import (
    RepositoryComptesBancaires,
    RepositoryLignesReleve,
    RepositoryRelevesBancaires,
)

TYPES_JOURNAL_TRESORERIE = ("banque", "caisse")
CLASSE_COMPTE_TRESORERIE = 5


@dataclass
class LigneReleveSaisie:
    """Une ligne de relevé saisie côté appelant (voir `LigneSaisie`,
    l'équivalent côté `comptabilite`, pour le même choix de conception)."""

    date_operation: date
    libelle: str
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")
    reference: str | None = None


class ServiceTresorerie:
    def __init__(self, db: Session, entreprise_id: uuid.UUID) -> None:
        self.db = db
        self.entreprise_id = entreprise_id
        self.comptes_bancaires = RepositoryComptesBancaires(db, entreprise_id)
        self.releves = RepositoryRelevesBancaires(db, entreprise_id)
        self.lignes_releve = RepositoryLignesReleve(db, entreprise_id)
        self.journaux = RepositoryJournaux(db, entreprise_id)
        self.comptes = RepositoryComptes(db, entreprise_id)
        self.lignes_ecriture = RepositoryLignesEcriture(db, entreprise_id)
        self.journal_activite = ServiceJournalActivite(db)

    # --- Comptes bancaires ---------------------------------------------------

    def creer_compte_bancaire(
        self,
        *,
        auteur_id: uuid.UUID,
        journal_id: uuid.UUID,
        compte_comptable_id: uuid.UUID,
        libelle: str,
        banque: str | None = None,
        numero_compte: str | None = None,
        iban: str | None = None,
        solde_initial: Decimal = Decimal("0"),
    ) -> CompteBancaire:
        journal = self.journaux.obtenir(journal_id)
        if journal is None:
            raise RessourceIntrouvable("Journal introuvable.")
        if journal.type_journal not in TYPES_JOURNAL_TRESORERIE:
            raise ValidationMetier(
                "Un compte bancaire doit être rattaché à un journal de type "
                "banque ou caisse."
            )
        if self.comptes_bancaires.obtenir_par_journal(journal_id) is not None:
            raise Conflit("Ce journal est déjà rattaché à un compte bancaire.")

        compte = self.comptes.obtenir(compte_comptable_id)
        if compte is None:
            raise RessourceIntrouvable("Compte comptable introuvable.")
        if compte.classe != CLASSE_COMPTE_TRESORERIE:
            raise ValidationMetier(
                "Le compte comptable d'un compte bancaire doit être un compte "
                "de trésorerie (classe 5)."
            )

        compte_bancaire = CompteBancaire(
            journal_id=journal_id,
            compte_comptable_id=compte_comptable_id,
            libelle=libelle,
            banque=banque,
            numero_compte=numero_compte,
            iban=iban,
            solde_initial=solde_initial,
        )
        self.comptes_bancaires.ajouter(compte_bancaire)
        self.journal_activite.enregistrer(
            module="tresorerie",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="CompteBancaire",
            objet_id=compte_bancaire.id,
            description=f"Création du compte bancaire '{libelle}'.",
            valeurs_apres={"libelle": libelle, "journal_id": str(journal_id)},
        )
        return compte_bancaire

    def desactiver_compte_bancaire(self, compte_bancaire_id: uuid.UUID, *, auteur_id: uuid.UUID) -> None:
        compte_bancaire = self._obtenir_compte_bancaire_ou_lever(compte_bancaire_id)
        if not compte_bancaire.actif:
            raise ValidationMetier("Ce compte bancaire est déjà désactivé.")
        compte_bancaire.actif = False
        self.db.flush()
        self.journal_activite.enregistrer(
            module="tresorerie",
            type_action=TypeAction.ARCHIVER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="CompteBancaire",
            objet_id=compte_bancaire.id,
            description=f"Désactivation du compte bancaire '{compte_bancaire.libelle}'.",
            valeurs_avant={"actif": True},
            valeurs_apres={"actif": False},
        )

    def obtenir_compte_bancaire(self, compte_bancaire_id: uuid.UUID) -> CompteBancaire:
        return self._obtenir_compte_bancaire_ou_lever(compte_bancaire_id)

    def lister_comptes_bancaires(self, *, actifs_seulement: bool = True) -> list[CompteBancaire]:
        return self.comptes_bancaires.lister(actifs_seulement=actifs_seulement)

    # --- Relevés bancaires -----------------------------------------------------

    def creer_releve(
        self,
        *,
        auteur_id: uuid.UUID,
        compte_bancaire_id: uuid.UUID,
        date_debut: date,
        date_fin: date,
        solde_debut: Decimal,
        solde_fin: Decimal,
        lignes: list[LigneReleveSaisie],
        reference: str | None = None,
    ) -> ReleveBancaire:
        self._obtenir_compte_bancaire_ou_lever(compte_bancaire_id)
        if date_fin <= date_debut:
            raise ValidationMetier("La date de fin du relevé doit être postérieure à la date de début.")
        self._valider_lignes(lignes)
        self._verifier_coherence_soldes(solde_debut, solde_fin, lignes)

        releve = ReleveBancaire(
            compte_bancaire_id=compte_bancaire_id,
            date_debut=date_debut,
            date_fin=date_fin,
            solde_debut=solde_debut,
            solde_fin=solde_fin,
            reference=reference,
        )
        self.releves.ajouter(releve)
        self._remplacer_lignes(releve.id, lignes)

        self.journal_activite.enregistrer(
            module="tresorerie",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="ReleveBancaire",
            objet_id=releve.id,
            description=f"Création du relevé du {date_debut} au {date_fin}.",
            valeurs_apres={"solde_debut": str(solde_debut), "solde_fin": str(solde_fin)},
        )
        return releve

    def modifier_releve(
        self,
        releve_id: uuid.UUID,
        *,
        auteur_id: uuid.UUID,
        solde_debut: Decimal | None = None,
        solde_fin: Decimal | None = None,
        reference: str | None = None,
        lignes: list[LigneReleveSaisie] | None = None,
    ) -> ReleveBancaire:
        releve = self._obtenir_releve_ou_lever(releve_id)

        if lignes is not None:
            self._verifier_aucune_ligne_rapprochee(releve_id)
            self._valider_lignes(lignes)

        nouveau_solde_debut = solde_debut if solde_debut is not None else releve.solde_debut
        nouveau_solde_fin = solde_fin if solde_fin is not None else releve.solde_fin
        lignes_a_verifier = lignes if lignes is not None else None
        if lignes_a_verifier is not None or solde_debut is not None or solde_fin is not None:
            lignes_pour_controle = lignes_a_verifier
            if lignes_pour_controle is None:
                lignes_pour_controle = [
                    LigneReleveSaisie(
                        date_operation=l.date_operation,
                        libelle=l.libelle,
                        debit=l.debit,
                        credit=l.credit,
                        reference=l.reference,
                    )
                    for l in self.lignes_releve.lister_pour_releve(releve_id)
                ]
            self._verifier_coherence_soldes(nouveau_solde_debut, nouveau_solde_fin, lignes_pour_controle)

        if solde_debut is not None:
            releve.solde_debut = solde_debut
        if solde_fin is not None:
            releve.solde_fin = solde_fin
        if reference is not None:
            releve.reference = reference
        if lignes is not None:
            self.lignes_releve.supprimer_pour_releve(releve_id)
            self._remplacer_lignes(releve_id, lignes)
        self.db.flush()

        self.journal_activite.enregistrer(
            module="tresorerie",
            type_action=TypeAction.MODIFIER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="ReleveBancaire",
            objet_id=releve.id,
            description="Modification d'un relevé bancaire.",
        )
        return releve

    def supprimer_releve(self, releve_id: uuid.UUID, *, auteur_id: uuid.UUID) -> None:
        self._obtenir_releve_ou_lever(releve_id)
        self._verifier_aucune_ligne_rapprochee(releve_id)
        releve = self._obtenir_releve_ou_lever(releve_id)
        self.db.delete(releve)  # les lignes suivent par ondelete=CASCADE
        self.db.flush()
        self.journal_activite.enregistrer(
            module="tresorerie",
            type_action=TypeAction.SUPPRIMER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="ReleveBancaire",
            objet_id=releve_id,
            description="Suppression d'un relevé bancaire.",
        )

    def obtenir_releve(self, releve_id: uuid.UUID) -> ReleveBancaire:
        return self._obtenir_releve_ou_lever(releve_id)

    def lister_releves(self, compte_bancaire_id: uuid.UUID) -> list[ReleveBancaire]:
        return self.releves.lister_pour_compte(compte_bancaire_id)

    def lister_lignes(self, releve_id: uuid.UUID) -> list[LigneReleve]:
        return self.lignes_releve.lister_pour_releve(releve_id)

    def lister_lignes_non_rapprochees(self, compte_bancaire_id: uuid.UUID) -> list[LigneReleve]:
        return self.lignes_releve.lister_non_rapprochees(compte_bancaire_id)

    def lister_ecritures_candidates(self, compte_bancaire_id: uuid.UUID) -> list:
        """Les lignes d'écriture du compte comptable de ce compte bancaire
        pas encore lettrées — le vivier proposé côté comptable pour un
        rapprochement (voir la note de tête de fichier)."""
        compte_bancaire = self._obtenir_compte_bancaire_ou_lever(compte_bancaire_id)
        return self.lignes_ecriture.lister_non_lettrees_pour_compte(compte_bancaire.compte_comptable_id)

    # --- Rapprochement -----------------------------------------------------

    def rapprocher(
        self,
        *,
        auteur_id: uuid.UUID,
        compte_bancaire_id: uuid.UUID,
        ligne_releve_ids: list[uuid.UUID],
        ligne_ecriture_ids: list[uuid.UUID],
    ) -> str:
        compte_bancaire = self._obtenir_compte_bancaire_ou_lever(compte_bancaire_id)

        if not ligne_releve_ids or not ligne_ecriture_ids:
            raise ValidationMetier("Un rapprochement nécessite au moins une ligne de chaque côté.")

        lignes_releve = self.lignes_releve.obtenir_plusieurs(ligne_releve_ids)
        if len(lignes_releve) != len(set(ligne_releve_ids)):
            raise RessourceIntrouvable("Une ou plusieurs lignes de relevé sont introuvables.")
        lignes_ecriture = self.lignes_ecriture.obtenir_plusieurs(ligne_ecriture_ids)
        if len(lignes_ecriture) != len(set(ligne_ecriture_ids)):
            raise RessourceIntrouvable("Une ou plusieurs lignes d'écriture sont introuvables.")

        releves_concernes = {}
        for ligne in lignes_releve:
            if ligne.code_lettrage is not None:
                raise ValidationMetier("Une ligne de relevé déjà rapprochée ne peut pas l'être à nouveau.")
            if ligne.releve_id not in releves_concernes:
                releves_concernes[ligne.releve_id] = self._obtenir_releve_ou_lever(ligne.releve_id)
            if releves_concernes[ligne.releve_id].compte_bancaire_id != compte_bancaire_id:
                raise ValidationMetier(
                    "Toutes les lignes de relevé doivent appartenir à ce compte bancaire."
                )

        for ligne in lignes_ecriture:
            if ligne.code_lettrage is not None:
                raise ValidationMetier("Une ligne d'écriture déjà lettrée ne peut pas l'être à nouveau.")
            if ligne.compte_id != compte_bancaire.compte_comptable_id:
                raise ValidationMetier(
                    "Toutes les lignes d'écriture doivent porter sur le compte comptable "
                    "de ce compte bancaire."
                )

        # Voir la note de tête de fichier sur la correspondance miroir
        # entre les deux conventions.
        mouvement_releve = sum((l.credit - l.debit for l in lignes_releve), Decimal("0"))
        mouvement_ecriture = sum((l.debit - l.credit for l in lignes_ecriture), Decimal("0"))
        if mouvement_releve != mouvement_ecriture:
            raise ValidationMetier(
                "Le rapprochement n'est pas équilibré : mouvement relevé "
                f"{mouvement_releve} ≠ mouvement écriture {mouvement_ecriture}."
            )

        code = f"RAP{uuid.uuid4().hex[:12].upper()}"
        for ligne in lignes_releve:
            ligne.code_lettrage = code
        for ligne in lignes_ecriture:
            ligne.code_lettrage = code
        self.db.flush()

        self.journal_activite.enregistrer(
            module="tresorerie",
            type_action=TypeAction.VALIDER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="CompteBancaire",
            objet_id=compte_bancaire.id,
            description=f"Rapprochement bancaire ({code}) : {len(lignes_releve)} ligne(s) de "
            f"relevé, {len(lignes_ecriture)} ligne(s) d'écriture.",
            valeurs_apres={"code_lettrage": code},
        )
        return code

    def annuler_rapprochement(self, code_lettrage: str, *, auteur_id: uuid.UUID) -> None:
        lignes_releve = self.lignes_releve.lister_par_code_lettrage(code_lettrage)
        lignes_ecriture = self.lignes_ecriture.lister_par_code_lettrage(code_lettrage)
        if not lignes_releve and not lignes_ecriture:
            raise RessourceIntrouvable("Aucun rapprochement trouvé pour ce code.")

        for ligne in lignes_releve:
            ligne.code_lettrage = None
        for ligne in lignes_ecriture:
            ligne.code_lettrage = None
        self.db.flush()

        self.journal_activite.enregistrer(
            module="tresorerie",
            type_action=TypeAction.ANNULER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="CompteBancaire",
            objet_id=None,
            description=f"Annulation du rapprochement {code_lettrage}.",
            valeurs_avant={"code_lettrage": code_lettrage},
        )

    # --- Aides internes -------------------------------------------------------

    def _obtenir_compte_bancaire_ou_lever(self, compte_bancaire_id: uuid.UUID) -> CompteBancaire:
        compte_bancaire = self.comptes_bancaires.obtenir(compte_bancaire_id)
        if compte_bancaire is None:
            raise RessourceIntrouvable("Compte bancaire introuvable.")
        return compte_bancaire

    def _obtenir_releve_ou_lever(self, releve_id: uuid.UUID) -> ReleveBancaire:
        releve = self.releves.obtenir(releve_id)
        if releve is None:
            raise RessourceIntrouvable("Relevé bancaire introuvable.")
        return releve

    def _verifier_aucune_ligne_rapprochee(self, releve_id: uuid.UUID) -> None:
        lignes = self.lignes_releve.lister_pour_releve(releve_id)
        if any(l.code_lettrage is not None for l in lignes):
            raise ValidationMetier(
                "Ce relevé a des lignes déjà rapprochées ; annulez le rapprochement "
                "avant de le modifier ou de le supprimer."
            )

    def _valider_lignes(self, lignes: list[LigneReleveSaisie]) -> None:
        if not lignes:
            raise ValidationMetier("Un relevé doit comporter au moins une ligne.")
        for ligne in lignes:
            if (ligne.debit > 0) == (ligne.credit > 0):
                raise ValidationMetier(
                    "Chaque ligne doit être soit débitrice, soit créditrice (jamais "
                    "les deux, jamais ni l'une ni l'autre)."
                )

    def _verifier_coherence_soldes(
        self, solde_debut: Decimal, solde_fin: Decimal, lignes: list[LigneReleveSaisie]
    ) -> None:
        mouvement = sum((l.credit - l.debit for l in lignes), Decimal("0"))
        if solde_debut + mouvement != solde_fin:
            raise ValidationMetier(
                f"Le solde de fin ({solde_fin}) ne correspond pas au solde de début "
                f"({solde_debut}) plus le mouvement des lignes ({mouvement})."
            )

    def _remplacer_lignes(self, releve_id: uuid.UUID, lignes: list[LigneReleveSaisie]) -> None:
        for ligne in lignes:
            self.lignes_releve.ajouter(
                LigneReleve(
                    releve_id=releve_id,
                    date_operation=ligne.date_operation,
                    libelle=ligne.libelle,
                    reference=ligne.reference,
                    debit=ligne.debit,
                    credit=ligne.credit,
                )
            )