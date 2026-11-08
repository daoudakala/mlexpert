"""Analyse des fichiers d'import du plan comptable ET des écritures (CSV ou
Excel) — deux formats bien distincts, voir plus bas pour celui des
écritures (section "Import des écritures").

Plan comptable :

Format attendu, deux colonnes par ligne : numéro de compte, libellé — rien
d'autre (ni classe, ni lettrable, ni parent : ces informations sont soit
déduites — la classe, du premier chiffre du numéro, voir `service.py` —
soit absentes de ce format d'import volontairement minimal).

Une éventuelle ligne d'en-tête est détectée (et ignorée) si sa première
valeur ne commence pas par un chiffre — un vrai numéro de compte SYSCOHADA
commence toujours par sa classe (1 à 8). Pour le CSV, le séparateur
(virgule, point-virgule ou tabulation) est détecté automatiquement avec
`csv.Sniffer`, avec un repli simple si l'échantillon est trop ambigu pour
lui.
"""

import csv
import io
from dataclasses import dataclass
from datetime import date

import openpyxl

from app.core.exceptions import ValidationMetier


@dataclass
class LigneBrute:
    numero: str
    libelle: str


def analyser_fichier(contenu: bytes, nom_fichier: str) -> list[LigneBrute]:
    nom = (nom_fichier or "").lower()
    if nom.endswith(".xlsx") or nom.endswith(".xlsm"):
        lignes = _analyser_xlsx(contenu)
    else:
        lignes = _analyser_csv(contenu)

    if lignes and _ressemble_a_un_entete(lignes[0]):
        lignes = lignes[1:]

    if not lignes:
        raise ValidationMetier(
            "Le fichier ne contient aucune ligne exploitable (attendu : numéro de "
            "compte puis libellé, deux colonnes par ligne)."
        )
    return lignes


def _ressemble_a_un_entete(ligne: LigneBrute) -> bool:
    return not ligne.numero[:1].isdigit()


def _analyser_csv(contenu: bytes) -> list[LigneBrute]:
    try:
        texte = contenu.decode("utf-8-sig")
    except UnicodeDecodeError:
        texte = contenu.decode("latin-1")

    try:
        dialecte = csv.Sniffer().sniff(texte[:4096], delimiters=";,\t")
    except csv.Error:
        dialecte = csv.excel
        dialecte.delimiter = ";" if texte.count(";") >= texte.count(",") else ","

    lignes: list[LigneBrute] = []
    for ligne in csv.reader(io.StringIO(texte), dialect=dialecte):
        valeurs = [c.strip() for c in ligne]
        if len(valeurs) < 2 or not any(valeurs):
            continue
        lignes.append(LigneBrute(numero=valeurs[0], libelle=valeurs[1]))
    return lignes


def _analyser_xlsx(contenu: bytes) -> list[LigneBrute]:
    classeur = openpyxl.load_workbook(io.BytesIO(contenu), read_only=True, data_only=True)
    feuille = classeur.worksheets[0]
    lignes: list[LigneBrute] = []
    for ligne in feuille.iter_rows(values_only=True):
        valeurs = [str(c).strip() if c is not None else "" for c in ligne]
        if len(valeurs) < 2 or not any(valeurs):
            continue
        lignes.append(LigneBrute(numero=valeurs[0], libelle=valeurs[1]))
    return lignes


# --- Import des écritures (saisie en masse, section 8.2) --------------------
#
# Format attendu, sept colonnes par ligne (une ligne de débit/crédit, pas
# une écriture entière) :
#
#   journal | date (AAAA-MM-JJ) | pièce | compte | libellé | débit | crédit
#
# Les lignes qui partagent le même triplet (journal, date, pièce) forment
# UNE écriture : la "pièce" joue le rôle de clé de regroupement (et devient
# `reference_piece`), comme un numéro de facture ou de bordereau qui revient
# sur chaque ligne d'une même pièce dans un export comptable classique. Le
# libellé de l'écriture reprend celui de la PREMIÈRE ligne du groupe
# rencontrée dans le fichier ; chaque ligne garde aussi son propre libellé
# (le même champ sert aux deux, volontairement — pas de colonne séparée).
# Le regroupement ne demande pas que les lignes d'une même pièce soient
# contiguës dans le fichier.


@dataclass
class LigneEcritureBrute:
    journal: str
    date: str
    piece: str
    compte: str
    libelle: str
    debit: str
    credit: str


def analyser_fichier_ecritures(contenu: bytes, nom_fichier: str) -> list[LigneEcritureBrute]:
    nom = (nom_fichier or "").lower()
    if nom.endswith(".xlsx") or nom.endswith(".xlsm"):
        lignes = _analyser_xlsx_ecritures(contenu)
    else:
        lignes = _analyser_csv_ecritures(contenu)

    if lignes and _ressemble_a_un_entete_ecriture(lignes[0]):
        lignes = lignes[1:]

    if not lignes:
        raise ValidationMetier(
            "Le fichier ne contient aucune ligne exploitable (attendu : journal, "
            "date, pièce, compte, libellé, débit, crédit — sept colonnes par ligne)."
        )
    return lignes


def _ressemble_a_un_entete_ecriture(ligne: LigneEcritureBrute) -> bool:
    """Une vraie première ligne de données a toujours une date exploitable
    en deuxième colonne (AAAA-MM-JJ) ; une ligne d'en-tête ("Journal",
    "Date", ...) non."""
    try:
        date.fromisoformat(ligne.date.strip())
        return False
    except ValueError:
        return True


def _ligne_ecriture_depuis_valeurs(valeurs: list[str]) -> LigneEcritureBrute | None:
    if len(valeurs) < 7 or not any(valeurs):
        return None
    return LigneEcritureBrute(
        journal=valeurs[0],
        date=valeurs[1],
        piece=valeurs[2],
        compte=valeurs[3],
        libelle=valeurs[4],
        debit=valeurs[5],
        credit=valeurs[6],
    )


def _analyser_csv_ecritures(contenu: bytes) -> list[LigneEcritureBrute]:
    try:
        texte = contenu.decode("utf-8-sig")
    except UnicodeDecodeError:
        texte = contenu.decode("latin-1")

    try:
        dialecte = csv.Sniffer().sniff(texte[:4096], delimiters=";,\t")
    except csv.Error:
        dialecte = csv.excel
        dialecte.delimiter = ";" if texte.count(";") >= texte.count(",") else ","

    lignes: list[LigneEcritureBrute] = []
    for ligne in csv.reader(io.StringIO(texte), dialect=dialecte):
        valeurs = [c.strip() for c in ligne]
        ligne_brute = _ligne_ecriture_depuis_valeurs(valeurs)
        if ligne_brute is not None:
            lignes.append(ligne_brute)
    return lignes


def _analyser_xlsx_ecritures(contenu: bytes) -> list[LigneEcritureBrute]:
    classeur = openpyxl.load_workbook(io.BytesIO(contenu), read_only=True, data_only=True)
    feuille = classeur.worksheets[0]
    lignes: list[LigneEcritureBrute] = []
    for ligne in feuille.iter_rows(values_only=True):
        valeurs = [str(c).strip() if c is not None else "" for c in ligne]
        ligne_brute = _ligne_ecriture_depuis_valeurs(valeurs)
        if ligne_brute is not None:
            lignes.append(ligne_brute)
    return lignes
