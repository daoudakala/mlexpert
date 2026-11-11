"""Tableau de bord de la page d'accueil : soldes intermédiaires de gestion
(SIG), CAF, fonds de roulement, BFR, trésorerie, bilan fonctionnel.

Tout est calculé à partir des soldes par compte des écritures VALIDÉES
(`RepositoryReporting.totaux_par_compte`) — aucune table supplémentaire, et
surtout aucune dépendance à un compte bancaire enregistré ou à un tiers
rattaché : un compte qui a un solde est toujours pris en compte (c'est ce
qui manquait à l'ancien tableau de direction, qui ne lisait que les comptes
bancaires déclarés et les lignes liées à un tiers).

Deux jeux de données par appel :
- les FLUX de la période (CA, marge, VA, EBE, résultat, CAF) : écritures
  entre `date_debut` et `date_fin` ;
- les SOLDES cumulés (trésorerie, actif/passif circulant, FR, BFR) :
  écritures de l'exercice jusqu'à `date_fin` (à-nouveaux compris).
Sans filtre, la période est l'exercice entier.

Les regroupements de comptes suivent le plan SYSCOHADA révisé ; les
hypothèses retenues sont listées dans `calculer_resultats`.
"""

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import RessourceIntrouvable, ValidationMetier
from app.modules.dashboards.repository import RepositoryReporting
from app.modules.exercices.models import Exercice
from app.modules.exercices.repository import RepositoryExercice

ZERO = Decimal("0")

# (numero, classe, total_debit, total_credit) — format réduit de
# `RepositoryReporting.totaux_par_compte`.
LigneSolde = tuple[str, int, Decimal, Decimal]


# --- Résultats de calcul (dataclasses lues par les schémas Pydantic) --------


@dataclass
class IndicateurComparatif:
    valeur: Decimal
    valeur_n1: Decimal | None
    variation_pourcentage: float | None


@dataclass
class ActifCirculant:
    total: Decimal
    creances_clients: Decimal
    autres_creances: Decimal
    stocks: Decimal


@dataclass
class PassifCirculant:
    total: Decimal
    dettes_fournisseurs: Decimal
    dettes_fiscales: Decimal
    dettes_sociales: Decimal
    autres_dettes: Decimal


@dataclass
class BilanFonctionnel:
    immobilisations: Decimal
    actif_circulant: Decimal
    tresorerie_actif: Decimal
    ressources_durables: Decimal
    passif_circulant: Decimal
    tresorerie_passif: Decimal


@dataclass
class TableauBord:
    exercice_id: uuid.UUID
    annee: int
    annee_precedente: int | None
    date_debut: date
    date_fin: date
    chiffre_affaires: IndicateurComparatif
    marge_commerciale: IndicateurComparatif
    valeur_ajoutee: IndicateurComparatif
    excedent_brut_exploitation: IndicateurComparatif
    resultat_exploitation: Decimal
    resultat_net: Decimal
    capacite_autofinancement: Decimal
    tresorerie: Decimal
    actif_circulant: ActifCirculant
    passif_circulant: PassifCirculant
    fonds_roulement: Decimal
    besoin_fonds_roulement: Decimal
    bilan_fonctionnel: BilanFonctionnel


@dataclass
class Resultats:
    """Flux d'une période (voir `calculer_resultats`)."""

    chiffre_affaires: Decimal
    marge_commerciale: Decimal
    valeur_ajoutee: Decimal
    excedent_brut_exploitation: Decimal
    resultat_exploitation: Decimal
    resultat_net: Decimal
    capacite_autofinancement: Decimal


@dataclass
class Structure:
    """Soldes cumulés à une date (voir `calculer_structure`)."""

    tresorerie: Decimal
    actif_circulant: ActifCirculant
    passif_circulant: PassifCirculant
    immobilisations: Decimal
    ressources_durables: Decimal
    tresorerie_actif: Decimal
    tresorerie_passif: Decimal
    fonds_roulement: Decimal
    besoin_fonds_roulement: Decimal


# --- Fonctions pures (testables sans base de données) ------------------------


def _charge(lignes: list[LigneSolde], *prefixes: str) -> Decimal:
    """Solde net DÉBITEUR (charge) des comptes dont le numéro commence par
    l'un des préfixes."""
    return sum(
        (d - c for numero, _classe, d, c in lignes if numero.startswith(prefixes)),
        start=ZERO,
    )


def _produit(lignes: list[LigneSolde], *prefixes: str) -> Decimal:
    """Solde net CRÉDITEUR (produit) des comptes dont le numéro commence par
    l'un des préfixes."""
    return sum(
        (c - d for numero, _classe, d, c in lignes if numero.startswith(prefixes)),
        start=ZERO,
    )


def calculer_resultats(lignes: list[LigneSolde]) -> Resultats:
    """SIG et CAF d'une période, SYSCOHADA révisé.

    Hypothèses (à ajuster ici si le cabinet utilise d'autres regroupements) :
    - CA = comptes 70 ;
    - marge commerciale = 701 − 601 − 6031 (+ 6091 rabais sur achats de
      marchandises) ;
    - production = 702 à 707 + 72 (immobilisée) + 73 (variation de stocks) ;
    - consommations intermédiaires = 602, 604, 605, 608, 6032, 6033, 61, 62,
      63 (− rabais 6092/6094/6095/6098) ;
    - VA = marge commerciale + production − consommations ;
    - EBE = VA + subventions d'exploitation (71) − impôts et taxes (64) −
      charges de personnel (66) ;
    - résultat d'exploitation / résultat net : même logique que
      `ServiceReporting.compte_resultat_detaille` (67/77 = financier, classe
      8 classée par le signe du solde de chaque compte) ;
    - CAF = résultat net + dotations (68, 69, 85) + valeur comptable des
      cessions (81) − reprises (79, 86) − produits de cessions (82).
    """
    chiffre_affaires = _produit(lignes, "70")

    marge = (
        _produit(lignes, "701")
        - _charge(lignes, "601", "6031")
        + _produit(lignes, "6091")
    )
    production = _produit(lignes, "702", "703", "704", "705", "706", "707", "72", "73")
    consommations = _charge(
        lignes, "602", "604", "605", "608", "6032", "6033", "61", "62", "63"
    ) - _produit(lignes, "6092", "6094", "6095", "6098")
    valeur_ajoutee = marge + production - consommations
    ebe = valeur_ajoutee + _produit(lignes, "71") - _charge(lignes, "64") - _charge(lignes, "66")

    produits_exploitation = ZERO
    charges_exploitation = ZERO
    produits_financiers = ZERO
    charges_financieres = ZERO
    resultat_hao = ZERO
    for numero, classe, debit, credit in lignes:
        if classe == 6:
            if numero.startswith("67"):
                charges_financieres += debit - credit
            else:
                charges_exploitation += debit - credit
        elif classe == 7:
            if numero.startswith("77"):
                produits_financiers += credit - debit
            else:
                produits_exploitation += credit - debit
        elif classe == 8:
            resultat_hao += credit - debit

    resultat_exploitation = produits_exploitation - charges_exploitation
    resultat_net = resultat_exploitation + (produits_financiers - charges_financieres) + resultat_hao

    caf = (
        resultat_net
        + _charge(lignes, "68", "69", "81", "85")
        - _produit(lignes, "79", "82", "86")
    )

    return Resultats(
        chiffre_affaires=chiffre_affaires,
        marge_commerciale=marge,
        valeur_ajoutee=valeur_ajoutee,
        excedent_brut_exploitation=ebe,
        resultat_exploitation=resultat_exploitation,
        resultat_net=resultat_net,
        capacite_autofinancement=caf,
    )


def calculer_structure(lignes: list[LigneSolde]) -> Structure:
    """Structure financière fonctionnelle à partir des soldes cumulés.

    Même règle que `ServiceReporting.bilan` : les classes 4 et 5 sont
    réparties par le SIGNE du solde de chaque compte (débiteur → actif,
    créditeur → passif). Dans la classe 4, le préfixe du compte précise la
    nature : 41 clients ; 40 fournisseurs ; 42/43 dettes sociales ; 44
    dettes fiscales ; le reste → « autres ». Les ressources durables
    incluent le résultat de la période (pas encore viré en classe 1)."""
    immobilisations = ZERO
    stocks = ZERO
    creances_clients = ZERO
    autres_creances = ZERO
    dettes_fournisseurs = ZERO
    dettes_fiscales = ZERO
    dettes_sociales = ZERO
    autres_dettes = ZERO
    tresorerie_actif = ZERO
    tresorerie_passif = ZERO
    ressources_durables = ZERO

    for numero, classe, debit, credit in lignes:
        solde = debit - credit
        if classe == 1:
            ressources_durables += -solde
        elif classe == 2:
            immobilisations += solde
        elif classe == 3:
            stocks += solde
        elif classe == 4:
            if solde > 0:
                if numero.startswith("41"):
                    creances_clients += solde
                else:
                    autres_creances += solde
            elif solde < 0:
                dette = -solde
                if numero.startswith("40"):
                    dettes_fournisseurs += dette
                elif numero.startswith(("42", "43")):
                    dettes_sociales += dette
                elif numero.startswith("44"):
                    dettes_fiscales += dette
                else:
                    autres_dettes += dette
        elif classe == 5:
            if solde > 0:
                tresorerie_actif += solde
            else:
                tresorerie_passif += -solde

    ressources_durables += calculer_resultats(lignes).resultat_net

    total_actif_circulant = stocks + creances_clients + autres_creances
    total_passif_circulant = dettes_fournisseurs + dettes_fiscales + dettes_sociales + autres_dettes
    fonds_roulement = ressources_durables - immobilisations
    besoin_fonds_roulement = total_actif_circulant - total_passif_circulant

    return Structure(
        tresorerie=tresorerie_actif - tresorerie_passif,
        actif_circulant=ActifCirculant(
            total=total_actif_circulant,
            creances_clients=creances_clients,
            autres_creances=autres_creances,
            stocks=stocks,
        ),
        passif_circulant=PassifCirculant(
            total=total_passif_circulant,
            dettes_fournisseurs=dettes_fournisseurs,
            dettes_fiscales=dettes_fiscales,
            dettes_sociales=dettes_sociales,
            autres_dettes=autres_dettes,
        ),
        immobilisations=immobilisations,
        ressources_durables=ressources_durables,
        tresorerie_actif=tresorerie_actif,
        tresorerie_passif=tresorerie_passif,
        fonds_roulement=fonds_roulement,
        besoin_fonds_roulement=besoin_fonds_roulement,
    )


def _comparer(valeur: Decimal, valeur_n1: Decimal | None) -> IndicateurComparatif:
    variation = None
    if valeur_n1 is not None and valeur_n1 != 0:
        variation = float((valeur - valeur_n1) / abs(valeur_n1) * 100)
    return IndicateurComparatif(valeur=valeur, valeur_n1=valeur_n1, variation_pourcentage=variation)


def _un_an_avant(jour: date) -> date:
    try:
        return jour.replace(year=jour.year - 1)
    except ValueError:  # 29 février
        return jour.replace(year=jour.year - 1, day=28)


# --- Service ----------------------------------------------------------------


class ServiceTableauBord:
    def __init__(self, db: Session, entreprise_id: uuid.UUID) -> None:
        self.entreprise_id = entreprise_id
        self.reporting = RepositoryReporting(db, entreprise_id)
        self.exercices = RepositoryExercice(db, entreprise_id)

    def tableau_bord(
        self,
        *,
        exercice_id: uuid.UUID | None = None,
        date_debut: date | None = None,
        date_fin: date | None = None,
        aujourd_hui: date | None = None,
    ) -> TableauBord:
        exercice = self._choisir_exercice(exercice_id, aujourd_hui or date.today())

        debut = max(date_debut, exercice.date_debut) if date_debut else exercice.date_debut
        fin = min(date_fin, exercice.date_fin) if date_fin else exercice.date_fin
        if debut > fin:
            raise ValidationMetier("La période demandée est en dehors de l'exercice ou inversée.")
        periode_complete = debut == exercice.date_debut

        flux = self._lignes(exercice.id, date_debut=debut, date_fin=fin)
        cumul = (
            flux
            if periode_complete
            else self._lignes(exercice.id, date_fin=fin)
        )
        resultats = calculer_resultats(flux)
        structure = calculer_structure(cumul)

        resultats_n1: Resultats | None = None
        annee_precedente: int | None = None
        precedent_id = exercice.exercice_precedent_id
        if precedent_id is not None:
            precedent = self.exercices.obtenir(precedent_id)
            if precedent is not None:
                annee_precedente = precedent.date_fin.year
                debut_n1 = precedent.date_debut if periode_complete else _un_an_avant(debut)
                fin_n1 = _un_an_avant(fin) if fin != exercice.date_fin else precedent.date_fin
                resultats_n1 = calculer_resultats(
                    self._lignes(precedent.id, date_debut=debut_n1, date_fin=fin_n1)
                )

        def comparatif(nom: str) -> IndicateurComparatif:
            return _comparer(
                getattr(resultats, nom),
                getattr(resultats_n1, nom) if resultats_n1 is not None else None,
            )

        return TableauBord(
            exercice_id=exercice.id,
            annee=exercice.date_fin.year,
            annee_precedente=annee_precedente,
            date_debut=debut,
            date_fin=fin,
            chiffre_affaires=comparatif("chiffre_affaires"),
            marge_commerciale=comparatif("marge_commerciale"),
            valeur_ajoutee=comparatif("valeur_ajoutee"),
            excedent_brut_exploitation=comparatif("excedent_brut_exploitation"),
            resultat_exploitation=resultats.resultat_exploitation,
            resultat_net=resultats.resultat_net,
            capacite_autofinancement=resultats.capacite_autofinancement,
            tresorerie=structure.tresorerie,
            actif_circulant=structure.actif_circulant,
            passif_circulant=structure.passif_circulant,
            fonds_roulement=structure.fonds_roulement,
            besoin_fonds_roulement=structure.besoin_fonds_roulement,
            bilan_fonctionnel=BilanFonctionnel(
                immobilisations=structure.immobilisations,
                actif_circulant=structure.actif_circulant.total,
                tresorerie_actif=structure.tresorerie_actif,
                ressources_durables=structure.ressources_durables,
                passif_circulant=structure.passif_circulant.total,
                tresorerie_passif=structure.tresorerie_passif,
            ),
        )

    def _lignes(
        self,
        exercice_id: uuid.UUID,
        *,
        date_debut: date | None = None,
        date_fin: date | None = None,
    ) -> list[LigneSolde]:
        return [
            (numero, classe, debit, credit)
            for _id, numero, _libelle, classe, debit, credit in self.reporting.totaux_par_compte(
                exercice_id, date_debut=date_debut, date_fin=date_fin
            )
        ]

    def _choisir_exercice(self, exercice_id: uuid.UUID | None, aujourd_hui: date) -> Exercice:
        if exercice_id is not None:
            exercice = self.exercices.obtenir(exercice_id)
            if exercice is None:
                raise RessourceIntrouvable("Exercice introuvable.")
            return exercice
        # Même règle que `ServiceReporting._exercice_courant`.
        exercice = self.exercices.obtenir_pour_date(aujourd_hui)
        if exercice is not None:
            return exercice
        ouverts = self.exercices.lister_ouverts()
        if not ouverts:
            raise RessourceIntrouvable("Aucun exercice disponible pour cette entreprise.")
        return max(ouverts, key=lambda e: e.date_debut)