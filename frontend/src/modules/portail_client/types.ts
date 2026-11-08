/**
 * Types alignés à la main sur app/modules/portail_client/schemas.py. Pas
 * de type dédié pour les documents visibles : le backend réutilise
 * `DocumentLecture` du module documents, donc le frontend réutilise son
 * type `Document` (voir ./api.ts).
 */

export type StatutDemandeDocument = "en_attente" | "traitee" | "refusee";

export interface DemandeDocument {
  id: string;
  entreprise_id: string;
  libelle: string;
  description: string | null;
  statut: StatutDemandeDocument;
  reponse: string | null;
  demandeur_id: string;
  document_id: string | null;
  traitee_par_id: string | null;
  traitee_le: string | null;
  cree_le: string;
}

export interface DemandeDocumentCreation {
  libelle: string;
  description?: string | null;
}
