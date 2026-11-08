"""Utilitaires communs pour générer des exports Excel (.xlsx).

Premier module d'export du projet (cahier des charges, section 9 "États
financiers" / section 25 "Export et interopérabilité") : les librairies
(`openpyxl`) étaient déjà présentes dans le projet mais uniquement
utilisées pour l'IMPORT (voir `comptabilite/import_utils.py`), jamais pour
générer un fichier à télécharger.

Volontairement minimal — un tableau simple (titre optionnel + en-têtes +
lignes), pas de moteur de template générique : chaque export (un fichier
par module, voir `dashboards/export.py` pour le premier) compose ses
propres feuilles à partir de ce helper plutôt que de passer par une
abstraction commune plus lourde qu'il n'y a de rapports à exporter pour
l'instant.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

LARGEUR_COLONNE_PAR_DEFAUT = 22


def ecrire_feuille(
    feuille: Worksheet,
    *,
    colonnes: Sequence[str],
    lignes: Sequence[Sequence[object]],
    titre: str | None = None,
) -> None:
    """Écrit un tableau (en-têtes en gras + lignes de données) à partir de
    la première cellule de `feuille`. `titre`, si fourni, occupe la ligne
    du dessus, fusionnée sur la largeur du tableau — une ligne vide sépare
    le titre des en-têtes pour la lisibilité.

    Les valeurs sont converties via `_valeur_exportable` (`Decimal` non
    géré nativement par openpyxl, booléens affichés en clair) : chaque
    appelant peut donc passer directement les montants `Decimal` des
    dataclasses de `service.py` sans conversion préalable.
    """
    ligne_entetes = 1
    if titre:
        cellule_titre = feuille.cell(row=1, column=1, value=titre)
        cellule_titre.font = Font(bold=True, size=13)
        feuille.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max(len(colonnes), 1))
        ligne_entetes = 3

    for index_colonne, libelle in enumerate(colonnes, start=1):
        cellule = feuille.cell(row=ligne_entetes, column=index_colonne, value=libelle)
        cellule.font = Font(bold=True)

    for decalage_ligne, ligne in enumerate(lignes, start=1):
        for index_colonne, valeur in enumerate(ligne, start=1):
            feuille.cell(
                row=ligne_entetes + decalage_ligne,
                column=index_colonne,
                value=_valeur_exportable(valeur),
            )

    for index_colonne in range(1, len(colonnes) + 1):
        feuille.column_dimensions[get_column_letter(index_colonne)].width = LARGEUR_COLONNE_PAR_DEFAUT


def ecrire_ligne_totaux(
    feuille: Worksheet,
    *,
    ligne: int,
    valeurs: Sequence[object],
) -> None:
    """Écrit une ligne en gras (typiquement un total ou un sous-total) à
    la ligne donnée, à partir de la colonne A. Séparé de `ecrire_feuille`
    car un état financier (bilan, compte de résultat) a plusieurs lignes
    de total à des positions arbitraires, pas un unique total final comme
    une simple liste."""
    for index_colonne, valeur in enumerate(valeurs, start=1):
        cellule = feuille.cell(row=ligne, column=index_colonne, value=_valeur_exportable(valeur))
        cellule.font = Font(bold=True)


def ecrire_titre_section(feuille: Worksheet, *, ligne: int, libelle: str) -> None:
    """Sous-titre de section à l'intérieur d'une feuille (ex. "Actif" /
    "Passif" dans la feuille Bilan) — distinct du titre principal de
    `ecrire_feuille`, qui occupe toujours la ligne 1."""
    cellule = feuille.cell(row=ligne, column=1, value=libelle)
    cellule.font = Font(bold=True, italic=True)
    cellule.alignment = Alignment(horizontal="left")


def _valeur_exportable(valeur: object) -> object:
    """openpyxl n'accepte pas `Decimal` nativement : conversion en
    `float` pour les montants. Les autres types déjà supportés (date,
    datetime, int, float, str, bool, None) passent tels quels ; tout
    objet non reconnu (ex. `uuid.UUID`) est converti en texte plutôt que
    de faire échouer l'écriture du fichier."""
    if isinstance(valeur, Decimal):
        return float(valeur)
    if isinstance(valeur, (date, datetime, int, float, str, bool)) or valeur is None:
        return valeur
    return str(valeur)


def nouveau_classeur() -> Workbook:
    """Classeur vierge avec sa feuille par défaut retirée — chaque
    appelant ajoute ses propres feuilles nommées dans l'ordre voulu
    (`classeur.create_sheet("Bilan")`, etc.)."""
    classeur = Workbook()
    feuille_par_defaut = classeur.active
    classeur.remove(feuille_par_defaut)
    return classeur


def classeur_vers_bytes(classeur: Workbook) -> bytes:
    tampon = BytesIO()
    classeur.save(tampon)
    return tampon.getvalue()