/**
 * Types alignés à la main sur app/modules/entreprises/schemas.py.
 */

export interface Entreprise {
  id: string;
  raison_sociale: string;
  sigle: string | null;
  forme_juridique: string | null;
  activite: string | null;
  adresse: string | null;
  email_contact: string | null;
  telephone_contact: string | null;
  referentiel_comptable: string;
  devise: string;
  secteur: string | null;
  taille: string | null;
  niveau_risque: string | null;
  priorite: string | null;
  statut: string;
  blocage_ecritures_cloture: boolean;
  cree_le: string;
}

export interface EntrepriseCreation {
  raison_sociale: string;
  sigle?: string | null;
  forme_juridique?: string | null;
  activite?: string | null;
  adresse?: string | null;
  email_contact?: string | null;
  telephone_contact?: string | null;
  referentiel_comptable?: string;
  devise?: string;
  secteur?: string | null;
  taille?: string | null;
  niveau_risque?: string | null;
  priorite?: string | null;
  blocage_ecritures_cloture?: boolean;
}

export type EntrepriseMiseAJour = Partial<EntrepriseCreation>;
