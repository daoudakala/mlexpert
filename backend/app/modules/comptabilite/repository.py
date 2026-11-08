"""Accès aux données du module comptabilite.

Partie référentiel : le plan comptable ne se laisse filtrer ni par
`Repository` (aucune notion d'entreprise) ni par `RepositoryEntreprise`
(qui exclurait les comptes globaux) : un compte est visible dès que
`entreprise_id` est NULL (le référentiel partagé) OU égal à l'entreprise
du contexte (une extension). D'où deux repositories dédiés à `Compte`,
plutôt qu'un héritage des classes génériques de `shared/repository.py` :

- `RepositoryComptesGlobal` : gère uniquement les comptes globaux, sans
  aucun contexte entreprise — utilisé par l'administration plateforme.
- `RepositoryComptes` : la vue applicable à UNE entreprise (global ∪
  extensions), et le seul des deux à pouvoir créer des extensions.

`Journal`, en revanche, n'a rien de particulier : chaque entreprise a ses
propres journaux, donc `RepositoryJournaux` hérite normalement de
`RepositoryEntreprise`.

Partie transactionnelle : `Ecriture` et `LigneEcriture` sont des tables
entreprise-scopées classiques (`entreprise_id` dénormalisé, voir
models.py), donc `RepositoryEcritures` et `RepositoryLignesEcriture`
héritent normalement de `RepositoryEntreprise`, comme `RepositoryJournaux`.
"""

import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.modules.comptabilite.models import (
    Compte,
    Ecriture,
    EcritureRecurrente,
    Journal,
    LigneEcriture,
    LigneEcritureRecurrente,
    LigneModeleEcriture,
    ModeleEcriture,
    StatutEcriture,
)
from app.shared.repository import Repository, RepositoryEntreprise


class RepositoryComptesGlobal(Repository[Compte]):
    """Le référentiel partagé seul (`entreprise_id IS NULL`)."""

    modele = Compte

    def obtenir(self, id_: uuid.UUID) -> Compte | None:
        requete = select(Compte).where(Compte.id == id_, Compte.entreprise_id.is_(None))
        return self.db.scalars(requete).first()

    def obtenir_par_numero(self, numero: str) -> Compte | None:
        requete = select(Compte).where(Compte.numero == numero, Compte.entreprise_id.is_(None))
        return self.db.scalars(requete).first()

    def lister(
        self,
        *,
        actifs_seulement: bool = True,
        recherche: str | None = None,
        classe: int | None = None,
        limite: int = 1000,
        decalage: int = 0,
    ) -> list[Compte]:
        requete = select(Compte).where(Compte.entreprise_id.is_(None))
        if actifs_seulement:
            requete = requete.where(Compte.actif.is_(True))
        if recherche:
            motif = f"%{recherche}%"
            requete = requete.where(or_(Compte.numero.ilike(motif), Compte.libelle.ilike(motif)))
        if classe is not None:
            requete = requete.where(Compte.classe == classe)
        requete = requete.order_by(Compte.numero).limit(limite).offset(decalage)
        return list(self.db.scalars(requete).all())

    def ajouter(self, objet: Compte) -> Compte:
        # Toujours un compte global, quoi que l'appelant ait renseigné.
        objet.entreprise_id = None
        return super().ajouter(objet)


class RepositoryComptes:
    """Le plan comptable applicable à une entreprise : global ∪ extensions.

    Ne réutilise pas `Repository`/`RepositoryEntreprise` : leurs signatures
    ne collent pas à un filtre "NULL OU cette entreprise" (voir le
    docstring du fichier).
    """

    modele = Compte

    def __init__(self, db: Session, entreprise_id: uuid.UUID) -> None:
        self.db = db
        self.entreprise_id = entreprise_id

    def _visible_par_entreprise(self):
        return or_(Compte.entreprise_id.is_(None), Compte.entreprise_id == self.entreprise_id)

    def obtenir(self, id_: uuid.UUID) -> Compte | None:
        requete = select(Compte).where(Compte.id == id_, self._visible_par_entreprise())
        return self.db.scalars(requete).first()

    def obtenir_par_numero_extension(self, numero: str) -> Compte | None:
        """Une extension EXISTANTE de cette entreprise pour ce numéro,
        sans regarder le référentiel global — utilisé pour vérifier qu'un
        numéro n'est pas déjà pris avant d'en créer une nouvelle."""
        requete = select(Compte).where(
            Compte.numero == numero, Compte.entreprise_id == self.entreprise_id
        )
        return self.db.scalars(requete).first()

    def lister(
        self,
        *,
        actifs_seulement: bool = True,
        recherche: str | None = None,
        classe: int | None = None,
        limite: int = 1000,
        decalage: int = 0,
    ) -> list[Compte]:
        requete = select(Compte).where(self._visible_par_entreprise())
        if actifs_seulement:
            requete = requete.where(Compte.actif.is_(True))
        if recherche:
            motif = f"%{recherche}%"
            requete = requete.where(or_(Compte.numero.ilike(motif), Compte.libelle.ilike(motif)))
        if classe is not None:
            requete = requete.where(Compte.classe == classe)
        requete = requete.order_by(Compte.numero).limit(limite).offset(decalage)
        return list(self.db.scalars(requete).all())

    def lister_extensions(self, *, actifs_seulement: bool = True) -> list[Compte]:
        """Les seuls sous-comptes propres à cette entreprise, sans le
        référentiel global — utile pour un écran qui distingue les deux."""
        requete = select(Compte).where(Compte.entreprise_id == self.entreprise_id)
        if actifs_seulement:
            requete = requete.where(Compte.actif.is_(True))
        requete = requete.order_by(Compte.numero)
        return list(self.db.scalars(requete).all())

    def lister_comptes_collectifs(self) -> list[Compte]:
        """Les comptes éligibles comme compte collectif d'un tiers (module
        `tiers`, à venir) : global ∪ extensions, actifs, `est_collectif`."""
        requete = select(Compte).where(
            self._visible_par_entreprise(),
            Compte.est_collectif.is_(True),
            Compte.actif.is_(True),
        )
        return list(self.db.scalars(requete).all())

    def ajouter(self, objet: Compte) -> Compte:
        # Toute création via ce repository est une extension de
        # l'entreprise du contexte — jamais un compte global (voir
        # `RepositoryComptesGlobal` pour ça).
        objet.entreprise_id = self.entreprise_id
        self.db.add(objet)
        self.db.flush()
        return objet


class RepositoryJournaux(RepositoryEntreprise[Journal]):
    modele = Journal

    def obtenir_par_code(self, code: str) -> Journal | None:
        requete = select(Journal).where(
            Journal.code == code, Journal.entreprise_id == self.entreprise_id
        )
        return self.db.scalars(requete).first()


class RepositoryEcritures(RepositoryEntreprise[Ecriture]):
    modele = Ecriture

    def compter_validees(self, *, journal_id: uuid.UUID, exercice_id: uuid.UUID) -> int:
        """Le nombre d'écritures déjà validées pour ce couple journal/
        exercice — sert de base au prochain numéro séquentiel (voir
        `ServiceComptabilite.valider_ecriture`)."""
        requete = select(Ecriture).where(
            Ecriture.entreprise_id == self.entreprise_id,
            Ecriture.journal_id == journal_id,
            Ecriture.exercice_id == exercice_id,
            Ecriture.statut == StatutEcriture.VALIDEE.value,
        )
        return len(list(self.db.scalars(requete).all()))

    def lister_extournant(self, ecriture_id: uuid.UUID) -> list[Ecriture]:
        """Les écritures qui extournent celle-ci — l'originale elle-même
        n'est jamais marquée (voir models.py), on le déduit d'ici."""
        requete = select(Ecriture).where(
            Ecriture.entreprise_id == self.entreprise_id,
            Ecriture.ecriture_extournee_id == ecriture_id,
        )
        return list(self.db.scalars(requete).all())

    def lister(
        self,
        *,
        journal_id: uuid.UUID | None = None,
        exercice_id: uuid.UUID | None = None,
        statut: str | None = None,
        limite: int = 100,
        decalage: int = 0,
    ) -> list[Ecriture]:
        requete = select(Ecriture).where(Ecriture.entreprise_id == self.entreprise_id)
        if journal_id is not None:
            requete = requete.where(Ecriture.journal_id == journal_id)
        if exercice_id is not None:
            requete = requete.where(Ecriture.exercice_id == exercice_id)
        if statut is not None:
            requete = requete.where(Ecriture.statut == statut)
        requete = (
            requete.order_by(Ecriture.date_ecriture.desc()).limit(limite).offset(decalage)
        )
        return list(self.db.scalars(requete).all())


class RepositoryModelesEcriture(RepositoryEntreprise[ModeleEcriture]):
    modele = ModeleEcriture

    def obtenir_par_code(self, code: str) -> ModeleEcriture | None:
        requete = select(ModeleEcriture).where(
            ModeleEcriture.code == code, ModeleEcriture.entreprise_id == self.entreprise_id
        )
        return self.db.scalars(requete).first()

    def lister(self, *, actifs_seulement: bool = True) -> list[ModeleEcriture]:
        requete = select(ModeleEcriture).where(ModeleEcriture.entreprise_id == self.entreprise_id)
        if actifs_seulement:
            requete = requete.where(ModeleEcriture.actif.is_(True))
        requete = requete.order_by(ModeleEcriture.code)
        return list(self.db.scalars(requete).all())


class RepositoryLignesModeleEcriture(RepositoryEntreprise[LigneModeleEcriture]):
    modele = LigneModeleEcriture

    def lister_pour_modele(self, modele_id: uuid.UUID) -> list[LigneModeleEcriture]:
        requete = select(LigneModeleEcriture).where(
            LigneModeleEcriture.entreprise_id == self.entreprise_id,
            LigneModeleEcriture.modele_id == modele_id,
        )
        return list(self.db.scalars(requete).all())

    def supprimer_pour_modele(self, modele_id: uuid.UUID) -> None:
        for ligne in self.lister_pour_modele(modele_id):
            self.db.delete(ligne)
        self.db.flush()


class RepositoryEcrituresRecurrentes(RepositoryEntreprise[EcritureRecurrente]):
    modele = EcritureRecurrente

    def obtenir_par_code(self, code: str) -> EcritureRecurrente | None:
        requete = select(EcritureRecurrente).where(
            EcritureRecurrente.code == code, EcritureRecurrente.entreprise_id == self.entreprise_id
        )
        return self.db.scalars(requete).first()

    def lister(self, *, actifs_seulement: bool = True) -> list[EcritureRecurrente]:
        requete = select(EcritureRecurrente).where(
            EcritureRecurrente.entreprise_id == self.entreprise_id
        )
        if actifs_seulement:
            requete = requete.where(EcritureRecurrente.actif.is_(True))
        requete = requete.order_by(EcritureRecurrente.code)
        return list(self.db.scalars(requete).all())

    def lister_dues(self, *, jusquau) -> list[EcritureRecurrente]:
        """Les récurrences actives dont la prochaine échéance tombe au plus
        tard à `jusquau` — utilisé par `generer_echeances` lorsqu'il est
        appelé sans récurrence précise (génération groupée, non exposée en
        première passe mais prévue par ce repository)."""
        requete = select(EcritureRecurrente).where(
            EcritureRecurrente.entreprise_id == self.entreprise_id,
            EcritureRecurrente.actif.is_(True),
            EcritureRecurrente.prochaine_echeance <= jusquau,
        )
        return list(self.db.scalars(requete).all())


class RepositoryLignesEcritureRecurrente(RepositoryEntreprise[LigneEcritureRecurrente]):
    modele = LigneEcritureRecurrente

    def lister_pour_ecriture_recurrente(
        self, ecriture_recurrente_id: uuid.UUID
    ) -> list[LigneEcritureRecurrente]:
        requete = select(LigneEcritureRecurrente).where(
            LigneEcritureRecurrente.entreprise_id == self.entreprise_id,
            LigneEcritureRecurrente.ecriture_recurrente_id == ecriture_recurrente_id,
        )
        return list(self.db.scalars(requete).all())

    def supprimer_pour_ecriture_recurrente(self, ecriture_recurrente_id: uuid.UUID) -> None:
        for ligne in self.lister_pour_ecriture_recurrente(ecriture_recurrente_id):
            self.db.delete(ligne)
        self.db.flush()


class RepositoryLignesEcriture(RepositoryEntreprise[LigneEcriture]):
    modele = LigneEcriture

    def lister_pour_ecriture(self, ecriture_id: uuid.UUID) -> list[LigneEcriture]:
        requete = select(LigneEcriture).where(
            LigneEcriture.entreprise_id == self.entreprise_id,
            LigneEcriture.ecriture_id == ecriture_id,
        )
        return list(self.db.scalars(requete).all())

    def obtenir_plusieurs(self, ids: list[uuid.UUID]) -> list[LigneEcriture]:
        """Utilisé par le module `tresorerie` pour résoudre les lignes
        d'écriture désignées côté rapprochement bancaire."""
        requete = select(LigneEcriture).where(
            LigneEcriture.entreprise_id == self.entreprise_id,
            LigneEcriture.id.in_(ids),
        )
        return list(self.db.scalars(requete).all())

    def lister_par_code_lettrage(self, code_lettrage: str) -> list[LigneEcriture]:
        requete = select(LigneEcriture).where(
            LigneEcriture.entreprise_id == self.entreprise_id,
            LigneEcriture.code_lettrage == code_lettrage,
        )
        return list(self.db.scalars(requete).all())

    def lister_non_lettrees_pour_compte(
        self, compte_id: uuid.UUID, *, limite: int = 200, decalage: int = 0
    ) -> list[LigneEcriture]:
        """Les lignes d'écriture sur ce compte pas encore lettrées — sert
        de vivier de candidates au rapprochement bancaire (`tresorerie`)."""
        requete = (
            select(LigneEcriture)
            .where(
                LigneEcriture.entreprise_id == self.entreprise_id,
                LigneEcriture.compte_id == compte_id,
                LigneEcriture.code_lettrage.is_(None),
            )
            .order_by(LigneEcriture.id)
            .limit(limite)
            .offset(decalage)
        )
        return list(self.db.scalars(requete).all())

    def lister_pour_lettrage(
        self,
        compte_id: uuid.UUID,
        *,
        tiers_id: uuid.UUID | None = None,
        lettrees: bool | None = None,
    ):
        """Lignes d'un compte avec les informations de l'écriture porteuse
        (date, numéro, référence, libellé) nécessaires à l'écran de
        lettrage manuel (cahier, section 8.2). Seules les lignes
        d'écritures VALIDÉES sont retournées : une écriture en brouillon
        reste modifiable/supprimable à tout moment (`modifier_ecriture`/
        `supprimer_ecriture`), ce qui casserait un lettrage posé dessus.

        `lettrees` filtre : `None` = toutes, `True` = seulement les lignes
        déjà lettrées (pour l'écran "annuler un lettrage"), `False` =
        seulement les candidates non lettrées.

        Retourne des tuples `(LigneEcriture, date_ecriture, numero,
        reference_piece, libelle_ecriture)` — pas d'objet ORM dédié, le
        service les recompose en `LigneLettrage`."""
        requete = (
            select(
                LigneEcriture,
                Ecriture.date_ecriture,
                Ecriture.numero,
                Ecriture.reference_piece,
                Ecriture.libelle,
            )
            .join(Ecriture, Ecriture.id == LigneEcriture.ecriture_id)
            .where(
                LigneEcriture.entreprise_id == self.entreprise_id,
                LigneEcriture.compte_id == compte_id,
                Ecriture.statut == StatutEcriture.VALIDEE.value,
            )
            .order_by(Ecriture.date_ecriture, Ecriture.numero)
        )
        if tiers_id is not None:
            requete = requete.where(LigneEcriture.tiers_id == tiers_id)
        if lettrees is True:
            requete = requete.where(LigneEcriture.code_lettrage.isnot(None))
        elif lettrees is False:
            requete = requete.where(LigneEcriture.code_lettrage.is_(None))
        return list(self.db.execute(requete).all())

    def supprimer_pour_ecriture(self, ecriture_id: uuid.UUID) -> None:
        """Utilisé pour remplacer intégralement les lignes d'un brouillon
        (voir `ServiceComptabilite.modifier_ecriture`) : plus simple et
        moins source d'erreurs qu'un diff ligne à ligne."""
        for ligne in self.lister_pour_ecriture(ecriture_id):
            self.db.delete(ligne)
        self.db.flush()