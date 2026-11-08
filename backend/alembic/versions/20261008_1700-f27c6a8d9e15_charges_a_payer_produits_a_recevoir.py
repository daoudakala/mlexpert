"""charges a payer produits a recevoir

Revision ID: f27c6a8d9e15
Revises: e1b5c9f3a284
Create Date: 2026-10-08 17:00:00.000000

Cahier, section 8, point 4 "Charges à payer / produits à recevoir" :
aucune nouvelle table — ce sont le miroir exact des CCA/PCA (point 3) et
réutilisent donc `regularisations_cca_pca`, voir la docstring de tête de
fichier de `app/modules/regularisations/models.py`. Seul le `CHECK
constraint` sur `type_regularisation` doit être élargi pour accepter les
deux nouvelles valeurs `charge_a_payer` et `produit_a_recevoir`. Aucun
nouveau code de permission : `regularisation.creer`/`regularisation.consulter`
couvrent déjà tout le module.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f27c6a8d9e15'
down_revision: Union[str, Sequence[str], None] = 'e1b5c9f3a284'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ANCIENNE_CONTRAINTE = (
    "type_regularisation IN ('charge_constatee_avance', 'produit_constate_avance')"
)
NOUVELLE_CONTRAINTE = (
    "type_regularisation IN ("
    "'charge_constatee_avance', 'produit_constate_avance', "
    "'charge_a_payer', 'produit_a_recevoir'"
    ")"
)


def upgrade() -> None:
    op.drop_constraint(
        op.f('ck_regularisations_cca_pca_type_regularisation_valide'),
        'regularisations_cca_pca',
        type_='check',
    )
    op.create_check_constraint(
        op.f('ck_regularisations_cca_pca_type_regularisation_valide'),
        'regularisations_cca_pca',
        NOUVELLE_CONTRAINTE,
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f('ck_regularisations_cca_pca_type_regularisation_valide'),
        'regularisations_cca_pca',
        type_='check',
    )
    op.create_check_constraint(
        op.f('ck_regularisations_cca_pca_type_regularisation_valide'),
        'regularisations_cca_pca',
        ANCIENNE_CONTRAINTE,
    )