/**
 * Types alignés à la main sur app/modules/immobilisations/schemas.py.
 */

export type MethodeAmortissement = "lineaire" | "degressif";
export type StatutImmobilisation = "en_service" | "cedee" | "reformee";
export type StatutLigneAmortissement = "prevu" | "comptabilise";

export interface ImmobilisationCreation {
  libelle: string;
  categorie?: string | null;
  numero_inventaire?: string | null;
  date_acquisition: string;
  date_mise_en_service: string;
  valeur_origine: number;
  valeur_residuelle?: number;
  duree_amortissement_annees: number;
  methode_amortissement: MethodeAmortissement;
  taux_degressif?: number | null;
  compte_immobilisation_id: string;
  compte_amortissement_id: string;
  compte_dotation_id: string;
  fournisseur_id?: string | null;
}

export interface ImmobilisationMiseAJour {
  libelle?: string;
  categorie?: string | null;
  numero_inventaire?: string | null;
  fournisseur_id?: string | null;
}

export interface Immobilisation {
  id: string;
  entreprise_id: string;
  libelle: string;
  categorie: string | null;
  numero_inventaire: string | null;
  date_acquisition: string;
  date_mise_en_service: string;
  valeur_origine: string; // Decimal sérialisé en chaîne par Pydantic
  valeur_residuelle: string;
  duree_amortissement_annees: number;
  methode_amortissement: MethodeAmortissement;
  taux_degressif: string | null;
  statut: StatutImmobilisation;
  compte_immobilisation_id: string;
  compte_amortissement_id: string;
  compte_dotation_id: string;
  fournisseur_id: string | null;
  // Ligne d'écriture d'acquisition d'où la fiche a été reprise (null si saisie à la main).
  ligne_acquisition_id: string | null;
  date_sortie: string | null;
  prix_cession: string | null;
  valeur_nette_comptable_sortie: string | null;
  plus_ou_moins_value: string | null;
  ecriture_sortie_id: string | null;
  cree_le: string;
}

export interface LigneAmortissement {
  id: string;
  immobilisation_id: string;
  exercice_id: string;
  base_amortissable: string;
  taux_applique: string;
  dotation: string;
  cumul_amortissements: string;
  valeur_nette_comptable: string;
  statut: StatutLigneAmortissement;
  ecriture_id: string | null;
}

export interface GenerationEcritureDemande {
  journal_id: string;
}

export interface CessionDemande {
  date_sortie: string;
  prix_cession: number;
  journal_id: string;
  compte_tresorerie_id: string;
  compte_produit_cession_id: string;
  compte_valeur_comptable_sortie_id: string;
}

export interface ReformeDemande {
  date_sortie: string;
  journal_id: string;
  compte_valeur_comptable_sortie_id: string;
}

// --- Reprise automatique des acquisitions (comptes 21 à 27) ------------------

export interface AcquisitionAConfirmer {
  ligne_ecriture_id: string;
  ecriture_id: string;
  date_acquisition: string;
  numero_ecriture: string | null;
  libelle: string;
  compte_id: string;
  compte_numero: string;
  compte_libelle: string;
  montant: string; // Decimal sérialisé en chaîne
  tiers_id: string | null;
  compte_amortissement_suggere_id: string | null;
  compte_dotation_suggere_id: string | null;
}

export interface ConfirmationAcquisition {
  libelle: string;
  categorie?: string | null;
  numero_inventaire?: string | null;
  date_mise_en_service?: string | null;
  valeur_residuelle?: number;
  duree_amortissement_annees: number;
  methode_amortissement: MethodeAmortissement;
  taux_degressif?: number | null;
  compte_amortissement_id: string;
  compte_dotation_id: string;
  fournisseur_id?: string | null;
  generer_plan: boolean;
}

export interface ConfirmationAcquisitionResultat {
  immobilisation: Immobilisation;
  lignes_generees: number;
  avertissement: string | null;
}