"""Export Excel des états financiers (cahier des charges, section 9 :
"Exports PDF et Excel selon formats définis").

Premier export du projet (voir `shared/export_excel.py`) : un classeur à
trois feuilles — Bilan, Compte de résultat, Comparaison N/N-1 — couvrant
les trois rapports du module `dashboards` qui composent les "états
financiers" au sens du cahier. La balance générale et le grand livre
restent hors périmètre de cette première étape (export PDF des états
financiers validé avec l'utilisateur avant le reste).

Ne recalcule rien : prend en entrée les dataclasses déjà produites par
`ServiceReporting` (`Bilan`, `CompteResultatDetaille`,
`list[LigneBalanceComparee]`) — ce module ne fait que les mettre en page.
"""

from __future__ import annotations

from app.modules.dashboards.service import Bilan, CompteResultatDetaille, LigneBalanceComparee
from app.modules.entreprises.models import Entreprise
from app.modules.exercices.models import Exercice
from app.shared.export_excel import (
    classeur_vers_bytes,
    ecrire_feuille,
    ecrire_ligne_totaux,
    ecrire_titre_section,
    nouveau_classeur,
)


def exporter_etats_financiers(
    *,
    entreprise: Entreprise,
    exercice: Exercice,
    bilan: Bilan,
    resultat: CompteResultatDetaille,
    comparaison: list[LigneBalanceComparee],
) -> bytes:
    classeur = nouveau_classeur()
    titre_exercice = f"{entreprise.raison_sociale} — exercice {exercice.date_debut:%d/%m/%Y} au {exercice.date_fin:%d/%m/%Y}"

    _ecrire_feuille_bilan(classeur.create_sheet("Bilan"), bilan, titre_exercice)
    _ecrire_feuille_resultat(classeur.create_sheet("Compte de résultat"), resultat, titre_exercice)
    _ecrire_feuille_comparaison(classeur.create_sheet("Comparaison N-N-1"), comparaison, titre_exercice)

    return classeur_vers_bytes(classeur)


def _ecrire_feuille_bilan(feuille, bilan: Bilan, titre: str) -> None:
    ecrire_feuille(feuille, colonnes=["Rubrique", "Montant"], lignes=[], titre=titre)

    ecrire_titre_section(feuille, ligne=4, libelle="Actif")
    lignes_actif = [
        ("Immobilisations", bilan.immobilisations),
        ("Stocks", bilan.stocks),
        ("Créances", bilan.creances),
        ("Trésorerie", bilan.tresorerie_actif),
    ]
    ligne = 5
    for libelle, montant in lignes_actif:
        feuille.cell(row=ligne, column=1, value=libelle)
        feuille.cell(row=ligne, column=2, value=float(montant))
        ligne += 1
    ecrire_ligne_totaux(feuille, ligne=ligne, valeurs=["Total actif", float(bilan.total_actif)])

    ligne += 2
    ecrire_titre_section(feuille, ligne=ligne, libelle="Passif")
    ligne += 1
    lignes_passif = [
        ("Ressources durables", bilan.ressources_durables),
        ("Dettes circulantes", bilan.dettes_circulantes),
        ("Trésorerie passif", bilan.tresorerie_passif),
    ]
    for libelle, montant in lignes_passif:
        feuille.cell(row=ligne, column=1, value=libelle)
        feuille.cell(row=ligne, column=2, value=float(montant))
        ligne += 1
    ecrire_ligne_totaux(feuille, ligne=ligne, valeurs=["Total passif", float(bilan.total_passif)])

    ligne += 2
    feuille.cell(
        row=ligne,
        column=1,
        value="Bilan équilibré (actif = passif)." if bilan.equilibre else "Bilan déséquilibré — vérifier les écritures de cet exercice.",
    )


def _ecrire_feuille_resultat(feuille, resultat: CompteResultatDetaille, titre: str) -> None:
    ecrire_feuille(feuille, colonnes=["Rubrique", "Montant"], lignes=[], titre=titre)

    sections = [
        ("Exploitation", [
            ("Charges d'exploitation", resultat.total_charges_exploitation),
            ("Produits d'exploitation", resultat.total_produits_exploitation),
        ], ("Résultat exploitation", resultat.resultat_exploitation)),
        ("Financier", [
            ("Charges financières", resultat.total_charges_financieres),
            ("Produits financiers", resultat.total_produits_financiers),
        ], ("Résultat financier", resultat.resultat_financier)),
    ]

    ligne = 4
    for titre_section, lignes_section, total_section in sections:
        ecrire_titre_section(feuille, ligne=ligne, libelle=titre_section)
        ligne += 1
        for libelle, montant in lignes_section:
            feuille.cell(row=ligne, column=1, value=libelle)
            feuille.cell(row=ligne, column=2, value=float(montant))
            ligne += 1
        ecrire_ligne_totaux(feuille, ligne=ligne, valeurs=[total_section[0], float(total_section[1])])
        ligne += 2

    ecrire_ligne_totaux(
        feuille,
        ligne=ligne,
        valeurs=["Résultat des activités ordinaires", float(resultat.resultat_activites_ordinaires)],
    )
    ligne += 2

    ecrire_titre_section(feuille, ligne=ligne, libelle="Hors activités ordinaires (HAO)")
    ligne += 1
    for libelle, montant in [
        ("Charges HAO", resultat.total_charges_hao),
        ("Produits HAO", resultat.total_produits_hao),
    ]:
        feuille.cell(row=ligne, column=1, value=libelle)
        feuille.cell(row=ligne, column=2, value=float(montant))
        ligne += 1
    ecrire_ligne_totaux(feuille, ligne=ligne, valeurs=["Résultat HAO", float(resultat.resultat_hao)])
    ligne += 2

    ecrire_ligne_totaux(feuille, ligne=ligne, valeurs=["Résultat net", float(resultat.resultat_net)])

    for colonne, largeur in {"A": 32, "B": 18}.items():
        feuille.column_dimensions[colonne].width = largeur


def _ecrire_feuille_comparaison(feuille, comparaison: list[LigneBalanceComparee], titre: str) -> None:
    lignes = [
        (
            ligne.numero,
            ligne.libelle,
            ligne.solde_n,
            ligne.solde_n1,
            ligne.variation_montant,
            ligne.variation_pourcentage,
        )
        for ligne in comparaison
    ]
    ecrire_feuille(
        feuille,
        colonnes=["Numéro", "Libellé", "Solde N", "Solde N-1", "Variation", "Variation %"],
        lignes=lignes,
        titre=titre,
    )