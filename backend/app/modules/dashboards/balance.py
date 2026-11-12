"""Balance générale à colonnes : à-nouveaux, mouvements, solde.

Présentation attendue (PDF « Point sur MLexpert », VI) : pour chaque compte,
les à-nouveaux (débit/crédit), les mouvements (débit/crédit) et le solde à la
date choisie (débit/crédit), puis les totaux des comptes de BILAN (classes
1 à 5), des comptes de GESTION (classes 6 à 8) et de la BALANCE entière
(total débit = total crédit). Filtrable par période et par classe de comptes,
exportable en Excel.

La classe 9 (engagements hors bilan, comptabilité analytique) est listée
avec les autres comptes mais exclue des trois totaux : ses écritures ne
s'équilibrent pas avec le reste de la comptabilité.
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
CLASSES_BILAN = (1, 2, 3, 4, 5)
CLASSES_GESTION = (6, 7, 8)


@dataclass
class LigneBalanceDetaillee:
    compte_id: uuid.UUID
    numero: str
    libelle: str
    classe: int
    a_nouveau_debit: Decimal
    a_nouveau_credit: Decimal
    mouvement_debit: Decimal
    mouvement_credit: Decimal
    solde_debit: Decimal
    solde_credit: Decimal


@dataclass
class TotauxBalance:
    a_nouveau_debit: Decimal = ZERO
    a_nouveau_credit: Decimal = ZERO
    mouvement_debit: Decimal = ZERO
    mouvement_credit: Decimal = ZERO
    solde_debit: Decimal = ZERO
    solde_credit: Decimal = ZERO


@dataclass
class BalanceDetaillee:
    exercice_id: uuid.UUID
    date_debut: date
    date_fin: date
    lignes: list[LigneBalanceDetaillee] = field(default_factory=list)
    totaux_bilan: TotauxBalance = field(default_factory=TotauxBalance)
    totaux_gestion: TotauxBalance = field(default_factory=TotauxBalance)
    totaux_balance: TotauxBalance = field(default_factory=TotauxBalance)
    equilibree: bool = True


# --- Fonctions pures ---------------------------------------------------------

LigneBrute = tuple[uuid.UUID, str, str, int, Decimal, Decimal, Decimal, Decimal]


def _ajouter(totaux: TotauxBalance, ligne: LigneBalanceDetaillee) -> None:
    totaux.a_nouveau_debit += ligne.a_nouveau_debit
    totaux.a_nouveau_credit += ligne.a_nouveau_credit
    totaux.mouvement_debit += ligne.mouvement_debit
    totaux.mouvement_credit += ligne.mouvement_credit
    totaux.solde_debit += ligne.solde_debit
    totaux.solde_credit += ligne.solde_credit


def construire_balance(
    lignes_brutes: list[LigneBrute],
    *,
    exercice_id: uuid.UUID,
    date_debut: date,
    date_fin: date,
    classes: set[int] | None = None,
) -> BalanceDetaillee:
    """Calcule soldes et totaux à partir des lignes brutes du repository.
    Un compte sans aucun montant (tout à zéro) est omis. `classes`
    restreint les comptes affichés ET les totaux."""
    balance = BalanceDetaillee(exercice_id=exercice_id, date_debut=date_debut, date_fin=date_fin)

    for compte_id, numero, libelle, classe, an_d, an_c, mv_d, mv_c in lignes_brutes:
        if classes and classe not in classes:
            continue
        net = (an_d - an_c) + (mv_d - mv_c)
        if an_d == an_c == mv_d == mv_c == ZERO:
            continue
        ligne = LigneBalanceDetaillee(
            compte_id=compte_id,
            numero=numero,
            libelle=libelle,
            classe=classe,
            a_nouveau_debit=an_d,
            a_nouveau_credit=an_c,
            mouvement_debit=mv_d,
            mouvement_credit=mv_c,
            solde_debit=net if net > 0 else ZERO,
            solde_credit=-net if net < 0 else ZERO,
        )
        balance.lignes.append(ligne)
        if classe in CLASSES_BILAN:
            _ajouter(balance.totaux_bilan, ligne)
        if classe in CLASSES_GESTION:
            _ajouter(balance.totaux_gestion, ligne)
        if classe in CLASSES_BILAN or classe in CLASSES_GESTION:
            _ajouter(balance.totaux_balance, ligne)

    t = balance.totaux_balance
    balance.equilibree = (
        t.a_nouveau_debit == t.a_nouveau_credit
        and t.mouvement_debit == t.mouvement_credit
        and t.solde_debit == t.solde_credit
    )
    return balance


# --- Service -----------------------------------------------------------------


class ServiceBalance:
    def __init__(self, db: Session, entreprise_id: uuid.UUID) -> None:
        self.reporting = RepositoryReporting(db, entreprise_id)
        self.exercices = RepositoryExercice(db, entreprise_id)

    def balance_detaillee(
        self,
        exercice_id: uuid.UUID,
        *,
        date_debut: date | None = None,
        date_fin: date | None = None,
        classes: set[int] | None = None,
    ) -> BalanceDetaillee:
        exercice = self.exercices.obtenir(exercice_id)
        if exercice is None:
            raise RessourceIntrouvable("Exercice introuvable.")
        debut = max(date_debut, exercice.date_debut) if date_debut else exercice.date_debut
        fin = min(date_fin, exercice.date_fin) if date_fin else exercice.date_fin
        if debut > fin:
            raise ValidationMetier("La période demandée est en dehors de l'exercice ou inversée.")
        if classes and not classes <= set(range(1, 10)):
            raise ValidationMetier("Les classes de comptes doivent être comprises entre 1 et 9.")

        brutes = self.reporting.totaux_balance_detaillee(exercice_id, date_debut=debut, date_fin=fin)
        return construire_balance(
            brutes, exercice_id=exercice_id, date_debut=debut, date_fin=fin, classes=classes
        )


# --- Export Excel ------------------------------------------------------------

ENTETES_EXPORT = [
    "N° de compte",
    "Intitulé",
    "À nouveau débit",
    "À nouveau crédit",
    "Mouvements débit",
    "Mouvements crédit",
    "Solde débit",
    "Solde crédit",
]


def _valeurs(t: TotauxBalance) -> list[Decimal]:
    return [
        t.a_nouveau_debit,
        t.a_nouveau_credit,
        t.mouvement_debit,
        t.mouvement_credit,
        t.solde_debit,
        t.solde_credit,
    ]


def exporter_balance(*, entreprise: Entreprise, exercice: Exercice, balance: BalanceDetaillee) -> bytes:
    classeur = nouveau_classeur()
    feuille = classeur.create_sheet("Balance générale")
    titre = (
        f"{entreprise.raison_sociale} — Balance générale du {balance.date_debut:%d/%m/%Y} "
        f"au {balance.date_fin:%d/%m/%Y} (exercice {exercice.date_debut:%Y}-{exercice.date_fin:%Y})"
    )
    lignes = [
        [l.numero, l.libelle, l.a_nouveau_debit, l.a_nouveau_credit, l.mouvement_debit,
         l.mouvement_credit, l.solde_debit, l.solde_credit]
        for l in balance.lignes
    ]
    ecrire_feuille(feuille, colonnes=ENTETES_EXPORT, lignes=lignes, titre=titre)

    ligne = 3 + len(lignes) + 2
    ecrire_ligne_totaux(feuille, ligne=ligne, valeurs=["", "Totaux comptes de bilan", *_valeurs(balance.totaux_bilan)])
    ecrire_ligne_totaux(feuille, ligne=ligne + 1, valeurs=["", "Totaux comptes de gestion", *_valeurs(balance.totaux_gestion)])
    ecrire_ligne_totaux(feuille, ligne=ligne + 2, valeurs=["", "Totaux de la balance", *_valeurs(balance.totaux_balance)])
    feuille.column_dimensions["B"].width = 45
    return classeur_vers_bytes(classeur)