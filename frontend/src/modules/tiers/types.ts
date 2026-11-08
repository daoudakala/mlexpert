/**
 * Types alignés à la main sur app/modules/tiers/schemas.py.
 */

export interface Tiers {
  id: string;
  entreprise_id: string;
  code: string;
  raison_sociale: string;
  nif: string | null;
  rccm: string | null;
  adresse: string | null;
  email: string | null;
  telephone: string | null;
  delai_paiement_jours: number | null;
  plafond_credit: string | null; // Decimal sérialisé en chaîne par Pydantic
  actif: boolean;
  compte_collectif_client_id: string | null;
  compte_collectif_fournisseur_id: string | null;
  est_client: boolean;
  est_fournisseur: boolean;
  cree_le: string;
}

export interface TiersCreation {
  code: string;
  raison_sociale: string;
  nif?: string | null;
  rccm?: string | null;
  adresse?: string | null;
  email?: string | null;
  telephone?: string | null;
  delai_paiement_jours?: number | null;
  plafond_credit?: number | null;
  compte_collectif_client_id?: string | null;
  compte_collectif_fournisseur_id?: string | null;
  confirmer_malgre_doublon?: boolean;
}

export interface TiersMiseAJour {
  raison_sociale?: string | null;
  nif?: string | null;
  rccm?: string | null;
  adresse?: string | null;
  email?: string | null;
  telephone?: string | null;
  delai_paiement_jours?: number | null;
  plafond_credit?: number | null;
}

export interface TiersComptesCollectifs {
  compte_collectif_client_id: string | null;
  compte_collectif_fournisseur_id: string | null;
}

/** Forme du détail renvoyé par le backend quand un NIF est déjà vu
 * (409 Conflit, voir ServiceTiers.creer_tiers). */
export interface DoublonNif {
  tiers_existants: { id: string; code: string; raison_sociale: string }[];
}
