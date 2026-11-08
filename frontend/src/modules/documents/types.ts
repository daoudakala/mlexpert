/**
 * Types alignés à la main sur app/modules/documents/schemas.py. Pas de
 * type "DocumentDepot" ici : le dépôt est un upload multipart construit
 * directement en FormData dans api.ts, pas un objet JSON (voir la note de
 * tête de fichier du schemas.py backend).
 */

export type CategorieDocument =
  | "statuts"
  | "juridique"
  | "attestation"
  | "fiscal"
  | "comptable"
  | "social"
  | "autre";

export const CATEGORIES_DOCUMENT: { valeur: CategorieDocument; libelle: string }[] = [
  { valeur: "statuts", libelle: "Statuts" },
  { valeur: "juridique", libelle: "Document juridique" },
  { valeur: "attestation", libelle: "Attestation" },
  { valeur: "fiscal", libelle: "Fiscal" },
  { valeur: "comptable", libelle: "Comptable" },
  { valeur: "social", libelle: "Social" },
  { valeur: "autre", libelle: "Autre" },
];

export interface Document {
  id: string;
  entreprise_id: string;
  categorie: string;
  nom_fichier: string;
  type_mime: string;
  taille_octets: number;
  description: string | null;
  date_document: string | null;
  date_expiration: string | null;
  exercice_id: string | null;
  depose_par_id: string;
  visible_client: boolean;
  // Pièce justificative rattachée à une écriture (section 8.2) — nul si ce
  // document n'est rattaché à aucune écriture.
  ecriture_id: string | null;
  cree_le: string;
}

export interface DocumentMiseAJour {
  categorie?: CategorieDocument;
  description?: string | null;
  date_document?: string | null;
  date_expiration?: string | null;
}