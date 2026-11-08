export type RoleInterlocuteur =
  | "dirigeant"
  | "associe"
  | "responsable_financier"
  | "comptable"
  | "contact";

export const ROLES_INTERLOCUTEUR: { valeur: RoleInterlocuteur; libelle: string }[] = [
  { valeur: "dirigeant", libelle: "Dirigeant" },
  { valeur: "associe", libelle: "Associé" },
  { valeur: "responsable_financier", libelle: "Responsable financier" },
  { valeur: "comptable", libelle: "Comptable" },
  { valeur: "contact", libelle: "Contact" },
];

export interface Interlocuteur {
  id: string;
  entreprise_id: string;
  nom: string;
  role: RoleInterlocuteur;
  fonction: string | null;
  email: string | null;
  telephone: string | null;
  pourcentage_detention: number | null;
  notes: string | null;
  actif: boolean;
  cree_le: string;
}

export interface InterlocuteurEcriture {
  nom: string;
  role: RoleInterlocuteur;
  fonction?: string | null;
  email?: string | null;
  telephone?: string | null;
  pourcentage_detention?: number | null;
  notes?: string | null;
}
