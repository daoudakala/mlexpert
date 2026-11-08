/**
 * Types alignés à la main sur app/modules/tresorerie/schemas.py.
 */

export interface CompteBancaire {
  id: string;
  entreprise_id: string;
  libelle: string;
  banque: string | null;
  numero_compte: string | null;
  iban: string | null;
  journal_id: string;
  compte_comptable_id: string;
  solde_initial: string; // Decimal sérialisé en chaîne par Pydantic
  actif: boolean;
  cree_le: string;
}

export interface CompteBancaireCreation {
  libelle: string;
  banque?: string | null;
  numero_compte?: string | null;
  iban?: string | null;
  journal_id: string;
  compte_comptable_id: string;
  solde_initial?: number;
}

export interface LigneReleveSaisie {
  date_operation: string; // date ISO (yyyy-mm-dd)
  libelle: string;
  reference?: string | null;
  debit?: number;
  credit?: number;
}

export interface LigneReleveLecture {
  id: string;
  date_operation: string;
  libelle: string;
  reference: string | null;
  debit: string;
  credit: string;
  code_lettrage: string | null;
}

export interface ReleveCreation {
  date_debut: string;
  date_fin: string;
  solde_debut: number;
  solde_fin: number;
  reference?: string | null;
  lignes: LigneReleveSaisie[];
}

export interface ReleveMiseAJour {
  solde_debut?: number;
  solde_fin?: number;
  reference?: string | null;
  lignes?: LigneReleveSaisie[] | null;
}

export interface ReleveLecture {
  id: string;
  compte_bancaire_id: string;
  date_debut: string;
  date_fin: string;
  solde_debut: string;
  solde_fin: string;
  reference: string | null;
  cree_le: string;
}

export interface ReleveAvecLignes extends ReleveLecture {
  lignes: LigneReleveLecture[];
}

export interface RapprochementDemande {
  ligne_releve_ids: string[];
  ligne_ecriture_ids: string[];
}

export interface RapprochementReponse {
  code_lettrage: string;
}

export interface AnnulationRapprochementDemande {
  code_lettrage: string;
}
