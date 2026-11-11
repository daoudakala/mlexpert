"""Journaux créés automatiquement pour chaque entreprise.

Utilisé à la création d'une entreprise (`ServiceEntreprises.creer_entreprise`)
et par la migration qui rattrape les entreprises existantes. L'opération est
IDEMPOTENTE : un journal dont le code existe déjà n'est jamais recréé ni
modifié, et le journal de report à nouveau n'est pas dupliqué si l'entreprise
en a déjà un sous un autre code.

Seuls les types prévus par `TypeJournal` (et la contrainte CHECK de la table
`journaux`) peuvent être créés ici ; un nouveau type de journal (paie,
immobilisations…) demanderait d'abord une migration sur cette contrainte.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.comptabilite.models import Journal, TypeJournal

# (code, libellé, type)
JOURNAUX_PAR_DEFAUT: tuple[tuple[str, str, TypeJournal], ...] = (
    ("BQ", "Journal banque", TypeJournal.BANQUE),
    ("CA", "Journal caisse", TypeJournal.CAISSE),
    ("AC", "Journal achat", TypeJournal.ACHATS),
    ("VT", "Journal vente", TypeJournal.VENTES),
    ("OD", "Opérations diverses", TypeJournal.OPERATIONS_DIVERSES),
    ("RAN", "Report à nouveau", TypeJournal.A_NOUVEAUX),
)


def creer_journaux_par_defaut(db: Session, entreprise_id: uuid.UUID) -> list[Journal]:
    """Crée les journaux par défaut manquants ; retourne ceux créés."""
    existants = db.execute(
        select(Journal.code, Journal.type_journal).where(Journal.entreprise_id == entreprise_id)
    ).all()
    codes_existants = {code for code, _type in existants}
    a_deja_un_report = any(t == TypeJournal.A_NOUVEAUX.value for _code, t in existants)

    crees: list[Journal] = []
    for code, libelle, type_journal in JOURNAUX_PAR_DEFAUT:
        if code in codes_existants:
            continue
        if type_journal == TypeJournal.A_NOUVEAUX and a_deja_un_report:
            continue
        journal = Journal(
            entreprise_id=entreprise_id,
            code=code,
            libelle=libelle,
            type_journal=type_journal.value,
            actif=True,
        )
        db.add(journal)
        crees.append(journal)
    db.flush()
    return crees