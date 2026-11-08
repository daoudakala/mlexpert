/**
 * Types alignés à la main sur app/modules/provisions/schemas.py.
 */

export type TypeProvision = "depreciation_creance" | "depreciation_stock" | "risque_charge";
export type StatutProvision = "active" | "soldee";
export type TypeMouvementProvision = "dotation" | "reprise";

export interface ProvisionCreation {
  libelle: string;
  type_provision: TypeProvision;
  tiers_id?: string | null;
  compte_dotation_id: string;
  compte_provision_id: string;
  compte_reprise_id: string;
}

export interface ProvisionMiseAJour {
  libelle?: string;
  tiers_id?: string | null;
}

export interface Provision {
  id: string;
  entreprise_id: string;
  libelle: string;
  type_provision: TypeProvision;
  tiers_id: string | null;
  compte_dotation_id: string;
  compte_provision_id: string;
  compte_reprise_id: string;
  montant_actuel: string; // Decimal sérialisé en chaîne par Pydantic
  statut: StatutProvision;
}

export interface MouvementProvision {
  id: string;
  provision_id: string;
  exercice_id: string;
  type_mouvement: TypeMouvementProvision;
  montant: string;
  date_mouvement: string;
  ecriture_id: string;
}

export interface DotationDemande {
  exercice_id: string;
  journal_id: string;
  date_mouvement: string;
  montant: number;
}

export interface RepriseDemande {
  exercice_id: string;
  journal_id: string;
  date_mouvement: string;
  montant: number;
}