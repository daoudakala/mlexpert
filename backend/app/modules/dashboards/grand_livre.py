"""Grand livre général : pour chaque compte, les écritures classées par date
avec numéro de pièce, libellé, journal, débit, crédit et solde cumulé.

C'est « le point sur toutes les écritures » (PDF « Point sur MLexpert »,
V). Filtres : plage de comptes, journal, période. Toutes les écritures
VALIDÉES de la période y figurent, report à nouveau compris. Quand la
période ne commence pas au début de l'exercice, une ligne de solde
antérieur ouvre le compte pour que le solde cumulé reste juste.
"""

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import RessourceIntrouvable, ValidationMetier
from app.modules.dashboards.repository import RepositoryReporting
from app.modules.entreprises.models import Entreprise
from app.modules.exercices.models import Exercice
from app.modules.exercices.repository import RepositoryExercice
from app.shared.export_excel import (
    classeur_vers_bytes,
    ecrire_feuille,
    ecrire_ligne_totaux,
    nouveau_classeur,
)

ZERO = Decimal("0")


@dataclass
class LigneGrandLivreGeneral:
    ligne_ecriture_id: uuid.UUID
    ecriture_id: uuid.UUID
    date_ecriture: date
    code_journal: str
    numero_piece: str | None
    libelle: str
    debit: Decimal
    credit: Decimal
    solde_progressif: Decimal  # débit − crédit cumulé : positif = débiteur
    code_lettrage: str | None


@dataclass
class CompteGrandLivre:
    compte_id: uuid.UUID
    numero: str
    libelle: str
    solde_anterieur: Decimal
    lignes: list[LigneGrandLivreGeneral] = field(default_factory=list)
    total_debit: Decimal = ZERO
    total_credit: Decimal = ZERO
    solde_final: Decimal = ZERO


@dataclass
class GrandLivreGeneral:
    exercice_id: uuid.UUID
    date_debut: date
    date_fin: date
    comptes: list[CompteGrandLivre] = field(default_factory=list)
    total_debit: Decimal = ZERO
    total_credit: Decimal = ZERO


def construire_grand_livre(
    lignes_brutes: list[tuple],
    anterieurs: dict[uuid.UUID, Decimal],
    *,
    exercice_id: uuid.UUID,
    date_debut: date,
    date_fin: date,
) -> GrandLivreGeneral:
    """Regroupe les lignes (déjà triées par compte puis date) et calcule le
    solde cumulé de chaque compte. Un compte qui n'a qu'un solde antérieur
    (aucun mouvement sur la période) n'est pas affiché."""
    grand_livre = GrandLivreGeneral(exercice_id=exercice_id, date_debut=date_debut, date_fin=date_fin)
    courant: CompteGrandLivre | None = None
    cumul = ZERO

    for (
        compte_id,
        numero,
        libelle_compte,
        ligne_id,
        ecriture_id,
        date_ecriture,
        code_journal,
        numero_piece,
        libelle_ligne,
        libelle_ecriture,
        debit,
        credit,
        code_lettrage,
    ) in lignes_brutes:
        if courant is None or courant.compte_id != compte_id:
            anterieur = anterieurs.get(compte_id, ZERO)
            courant = CompteGrandLivre(
                compte_id=compte_id, numero=numero, libelle=libelle_compte, solde_anterieur=anterieur
            )
            grand_livre.comptes.append(courant)
            cumul = anterieur

        cumul += debit - credit
        courant.lignes.append(
            LigneGrandLivreGeneral(
                ligne_ecriture_id=ligne_id,
                ecriture_id=ecriture_id,
                date_ecriture=date_ecriture,
                code_journal=code_journal,
                numero_piece=numero_piece,
                libelle=libelle_ligne or libelle_ecriture,
                debit=debit,
                credit=credit,
                solde_progressif=cumul,
                code_lettrage=code_lettrage,
            )
        )
        courant.total_debit += debit
        courant.total_credit += credit
        courant.solde_final = cumul
        grand_livre.total_debit += debit
        grand_livre.total_credit += credit

    return grand_livre


class ServiceGrandLivre:
    def __init__(self, db: Session, entreprise_id: uuid.UUID) -> None:
        self.reporting = RepositoryReporting(db, entreprise_id)
        self.exercices = RepositoryExercice(db, entreprise_id)

    def grand_livre_general(
        self,
        exercice_id: uuid.UUID,
        *,
        date_debut: date | None = None,
        date_fin: date | None = None,
        compte_debut: str | None = None,
        compte_fin: str | None = None,
        journal_id: uuid.UUID | None = None,
    ) -> GrandLivreGeneral:
        exercice = self.exercices.obtenir(exercice_id)
        if exercice is None:
            raise RessourceIntrouvable("Exercice introuvable.")
        debut = max(date_debut, exercice.date_debut) if date_debut else exercice.date_debut
        fin = min(date_fin, exercice.date_fin) if date_fin else exercice.date_fin
        if debut > fin:
            raise ValidationMetier("La période demandée est en dehors de l'exercice ou inversée.")

        compte_debut = compte_debut.strip() if compte_debut else None
        compte_fin = compte_fin.strip() if compte_fin else None
        filtres = dict(compte_debut=compte_debut, compte_fin=compte_fin, journal_id=journal_id)

        lignes = self.reporting.lignes_grand_livre_general(
            exercice_id, date_debut=debut, date_fin=fin, **filtres
        )
        anterieurs = (
            self.reporting.soldes_anterieurs_grand_livre(exercice_id, avant=debut, **filtres)
            if debut > exercice.date_debut
            else {}
        )
        return construire_grand_livre(
            lignes, anterieurs, exercice_id=exercice_id, date_debut=debut, date_fin=fin
        )


ENTETES_EXPORT = [
    "Compte",
    "Intitulé du compte",
    "Journal",
    "Date",
    "N° de pièce",
    "Libellé",
    "Débit",
    "Crédit",
    "Solde débit",
    "Solde crédit",
    "Lettrage",
]


def _solde_en_colonnes(solde: Decimal) -> tuple[Decimal, Decimal]:
    return (solde, ZERO) if solde > 0 else (ZERO, -solde)


def exporter_grand_livre(
    *, entreprise: Entreprise, exercice: Exercice, grand_livre: GrandLivreGeneral
) -> bytes:
    classeur = nouveau_classeur()
    feuille = classeur.create_sheet("Grand livre")
    titre = (
        f"{entreprise.raison_sociale} — Grand livre du {grand_livre.date_debut:%d/%m/%Y} "
        f"au {grand_livre.date_fin:%d/%m/%Y} (exercice {exercice.date_debut:%Y}-{exercice.date_fin:%Y})"
    )
    lignes: list[list[object]] = []
    indices_totaux: list[int] = []
    for compte in grand_livre.comptes:
        if compte.solde_anterieur != 0:
            sd, sc = _solde_en_colonnes(compte.solde_anterieur)
            lignes.append([compte.numero, compte.libelle, "", "", "", "Solde antérieur", "", "", sd, sc, ""])
        for l in compte.lignes:
            sd, sc = _solde_en_colonnes(l.solde_progressif)
            lignes.append(
                [compte.numero, compte.libelle, l.code_journal, l.date_ecriture, l.numero_piece or "",
                 l.libelle, l.debit, l.credit, sd, sc, l.code_lettrage or ""]
            )
        sd, sc = _solde_en_colonnes(compte.solde_final)
        lignes.append(
            ["", f"Total compte {compte.numero}", "", "", "", "", compte.total_debit, compte.total_credit, sd, sc, ""]
        )
        indices_totaux.append(len(lignes))

    ecrire_feuille(feuille, colonnes=ENTETES_EXPORT, lignes=lignes, titre=titre)
    for indice in indices_totaux:  # mise en gras des lignes « Total compte »
        ecrire_ligne_totaux(feuille, ligne=3 + indice, valeurs=lignes[indice - 1])
    ecrire_ligne_totaux(
        feuille,
        ligne=3 + len(lignes) + 2,
        valeurs=["", "Total général", "", "", "", "", grand_livre.total_debit, grand_livre.total_credit],
    )
    feuille.column_dimensions["B"].width = 38
    feuille.column_dimensions["F"].width = 40
    return classeur_vers_bytes(classeur)