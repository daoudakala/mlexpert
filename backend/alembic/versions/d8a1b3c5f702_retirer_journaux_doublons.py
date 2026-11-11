"""Retire les journaux par défaut créés en doublon par la migration c7d4f1a9e260.

Cette migration avait créé CA « Journal caisse », AC « Journal achat » et VT
« Journal vente » même quand l'entreprise avait déjà un journal du même type
sous un autre code (CS, ACH, VENT…). Sont supprimés UNIQUEMENT les journaux :
- portant l'un de ces trois codes ET le libellé par défaut exact ;
- pour lesquels l'entreprise a un autre journal du même type ;
- et que RIEN ne référence (aucune écriture, aucun modèle d'écriture,
  aucune écriture récurrente).
Un journal déjà utilisé est conservé : à désactiver à la main si besoin.

Revision ID: d8a1b3c5f702
Revises: c7d4f1a9e260
"""

from alembic import op

revision = "d8a1b3c5f702"
down_revision = "c7d4f1a9e260"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM journaux j
        WHERE (
              (j.code = 'CA' AND j.libelle = 'Journal caisse')
           OR (j.code = 'AC' AND j.libelle = 'Journal achat')
           OR (j.code = 'VT' AND j.libelle = 'Journal vente')
        )
        AND EXISTS (
            SELECT 1 FROM journaux o
            WHERE o.entreprise_id = j.entreprise_id
              AND o.type_journal = j.type_journal
              AND o.id <> j.id
        )
        AND NOT EXISTS (SELECT 1 FROM ecritures e WHERE e.journal_id = j.id)
        AND NOT EXISTS (SELECT 1 FROM modeles_ecriture m WHERE m.journal_id = j.id)
        AND NOT EXISTS (SELECT 1 FROM ecritures_recurrentes r WHERE r.journal_id = j.id)
        """
    )


def downgrade() -> None:
    pass