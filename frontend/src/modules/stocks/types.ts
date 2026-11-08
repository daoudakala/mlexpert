/**
 * Types alignés à la main sur app/modules/stocks/schemas.py.
 */

export type MethodeValorisation = "cmup" | "fifo";

export type TypeMouvement = "entree" | "sortie";

export interface Article {
  id: string;
  entreprise_id: string;
  code: string;
  libelle: string;
  unite: string;
  methode_valorisation: MethodeValorisation;
  compte_stock_id: string;
  actif: boolean;
  quantite_en_stock: string; // Decimal sérialisé en chaîne par Pydantic
  cout_unitaire_moyen: string;
  valeur_stock: string;
  cree_le: string;
}

export interface ArticleCreation {
  code: string;
  libelle: string;
  unite: string;
  methode_valorisation: MethodeValorisation;
  compte_stock_id: string;
}

export interface ArticleMiseAJour {
  libelle?: string | null;
  unite?: string | null;
}

export interface MouvementEntreeCreation {
  article_id: string;
  date_mouvement: string;
  quantite: string;
  cout_unitaire: string;
  reference?: string | null;
  libelle?: string | null;
  tiers_id?: string | null;
}

export interface MouvementSortieCreation {
  article_id: string;
  date_mouvement: string;
  quantite: string;
  reference?: string | null;
  libelle?: string | null;
  tiers_id?: string | null;
}

export interface MouvementStock {
  id: string;
  entreprise_id: string;
  article_id: string;
  type_mouvement: TypeMouvement;
  date_mouvement: string;
  quantite: string;
  cout_unitaire: string;
  cout_total: string;
  reference: string | null;
  libelle: string | null;
  tiers_id: string | null;
  ecriture_id: string | null;
  cree_le: string;
}

export interface LigneConsommationLot {
  id: string;
  mouvement_sortie_id: string;
  lot_id: string;
  quantite_consommee: string;
  cout_unitaire: string;
}

export interface GenerationEcritureMouvementDemande {
  journal_id: string;
  compte_contrepartie_id: string;
}

export interface InventairePhysiqueCreation {
  article_id: string;
  exercice_id: string;
  date_inventaire: string;
  quantite_physique: string;
  journal_id?: string | null;
  compte_contrepartie_id?: string | null;
}

export interface InventairePhysique {
  id: string;
  entreprise_id: string;
  article_id: string;
  exercice_id: string;
  date_inventaire: string;
  quantite_theorique: string;
  quantite_physique: string;
  ecart: string;
  mouvement_ajustement_id: string | null;
  cree_le: string;
}