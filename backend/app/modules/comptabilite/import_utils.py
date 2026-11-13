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
commence toujours par sa classe (1 à 9). Pour le CSV, le séparateur
(virgule, point-virgule ou tabulation) est détecté automatiquement avec
`csv.Sniffer`, avec un repli simple si l'échantillon est trop ambigu pour
lui.
"""

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime

import openpyxl

from app.core.exceptions import ValidationMetier


# --- Aides communes -----------------------------------------------------------


def _texte_cellule(valeur) -> str:
    """Une cellule Excel en texte exploitable : une date devient AAAA-MM-JJ
    (et non « 2026-01-05 00:00:00 »), un nombre entier n'a pas de « .0 »
    (compte 601100 et non « 601100.0 »), un décimal est arrondi pour
    éviter les artefacts flottants (1234.5600000000001)."""
    if valeur is None:
        return ""
    if isinstance(valeur, datetime):
        return valeur.date().isoformat()
    if isinstance(valeur, date):
        return valeur.isoformat()
    if isinstance(valeur, bool):
        return str(valeur)
    if isinstance(valeur, int):
        return str(valeur)
    if isinstance(valeur, float):
        if valeur == int(valeur):
            return str(int(valeur))
        return format(round(valeur, 4), "f").rstrip("0").rstrip(".")
    return str(valeur).strip()


def normaliser_date(texte: str) -> str | None:
    """Accepte AAAA-MM-JJ, AAAA/MM/JJ, JJ/MM/AAAA, JJ-MM-AAAA et JJ.MM.AAAA
    (sans heure éventuelle) ; renvoie AAAA-MM-JJ, ou None si illisible."""
    brut = (texte or "").strip().split(" ")[0].split("T")[0]
    if not brut:
        return None
    for separateur in ("-", "/", "."):
        parties = brut.split(separateur)
        if len(parties) != 3 or not all(p.isdigit() for p in parties):
            continue
        try:
            if len(parties[0]) == 4:
                return date(int(parties[0]), int(parties[1]), int(parties[2])).isoformat()
            if len(parties[2]) == 4:
                return date(int(parties[2]), int(parties[1]), int(parties[0])).isoformat()
        except ValueError:
            return None
    return None


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
        valeurs = [_texte_cellule(c) for c in ligne]
        if len(valeurs) < 2 or not any(valeurs):
            continue
        lignes.append(LigneBrute(numero=valeurs[0], libelle=valeurs[1]))
    return lignes


# --- Import des écritures (saisie en masse, section 8.2) --------------------
#
# Format attendu, sept colonnes par ligne (une ligne de débit/crédit, pas
# une écriture entière) :
#
#   journal | date | pièce | compte | libellé | débit | crédit
#
# Date : AAAA-MM-JJ, JJ/MM/AAAA, JJ-MM-AAAA ou JJ.MM.AAAA (ou vraie date Excel).
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
    """Une ligne d'en-tête se reconnaît à ses libellés (« Journal », « Date »,
    ...). Une première ligne de données à la date illisible n'est PAS prise
    pour un en-tête : elle sera signalée comme ignorée, au lieu de
    disparaître silencieusement."""
    j = ligne.journal.strip().lower()
    d = ligne.date.strip().lower()
    return d.startswith("date") or j in ("journal", "jnl", "code journal", "code")


def _ligne_ecriture_depuis_valeurs(valeurs: list[str]) -> LigneEcritureBrute | None:
    if len(valeurs) < 7 or not any(valeurs):
        return None
    return LigneEcritureBrute(
        journal=valeurs[0],
        # Date normalisée en AAAA-MM-JJ quand elle est lisible ; sinon la
        # valeur brute est conservée pour le message d'erreur.
        date=normaliser_date(valeurs[1]) or valeurs[1],
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
        valeurs = [_texte_cellule(c) for c in ligne]
        ligne_brute = _ligne_ecriture_depuis_valeurs(valeurs)
        if ligne_brute is not None:
            lignes.append(ligne_brute)
    return lignes