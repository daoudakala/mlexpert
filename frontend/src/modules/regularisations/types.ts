/**
 * Types alignés à la main sur app/modules/regularisations/schemas.py.
 */

export type TypeRegularisation =
  | "charge_constatee_avance"
  | "produit_constate_avance"
  | "charge_a_payer"
  | "produit_a_recevoir";

export interface RegularisationCreation {
  libelle: string;
  type_regularisation: TypeRegularisation;
  exercice_id: string;
  compte_origine_id: string;
  compte_regularisation_id: string;
  journal_id: string;
  date_regularisation: string;
  montant: number;
}

export interface Regularisation {
  id: string;
  entreprise_id: string;
  libelle: string;
  type_regularisation: TypeRegularisation;
  exercice_id: string;
  compte_origine_id: string;
  compte_regularisation_id: string;
  montant: string; // Decimal sérialisé en chaîne par Pydantic
  date_regularisation: string;
  ecriture_id: string;
  cree_le: string;
}