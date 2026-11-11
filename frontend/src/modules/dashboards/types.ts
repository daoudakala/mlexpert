/**
 * Types alignés à la main sur app/modules/dashboards/schemas.py. Module
 * en lecture seule (pas de modèles SQLAlchemy, voir models absent côté
 * backend) : balance générale, grand livre d'un compte, résultat
 * sommaire — toujours calculés sur les écritures VALIDÉES uniquement.
 */

export interface LigneBalance {
  compte_id: string;
  numero: string;
  libelle: string;
  total_debit: string; // Decimal sérialisé en chaîne par Pydantic
  total_credit: string;
  solde: string;
}

export interface LigneGrandLivre {
  ligne_ecriture_id: string;
  date_ecriture: string;
  ecriture_id: string;
  numero_ecriture: string | null;
  libelle: string;
  debit: string;
  credit: string;
  solde_progressif: string;
}

export interface LigneBalanceComparee {
  compte_id: string;
  numero: string;
  libelle: string;
  solde_n: string;
  solde_n1: string | null; // null si l'exercice n'a pas d'exercice précédent renseigné
  variation_montant: string | null;
  variation_pourcentage: number | null; // null si solde_n1 est nul ou absent (division par zéro évitée)
}

export interface CompteResultatSommaire {
  exercice_id: string;
  total_charges: string;
  total_produits: string;
  resultat_net: string;
}

export type TypeTiersEcheancier = "client" | "fournisseur";

export interface LigneEcheance {
  ligne_ecriture_id: string;
  ecriture_id: string;
  numero_ecriture: string | null;
  date_ecriture: string;
  tiers_id: string;
  code_tiers: string;
  raison_sociale_tiers: string;
  libelle: string;
  montant: string; // signé : toujours "montant restant dû" dans le sens naturel du rôle (voir service.py)
  date_echeance: string | null;
  jours_retard: number | null; // null si échéance inconnue ; négatif si pas encore échue
}

export interface TrancheAgee {
  tiers_id: string;
  code_tiers: string;
  raison_sociale_tiers: string;
  non_echu: string;
  jours_0_30: string;
  jours_31_60: string;
  jours_61_90: string;
  jours_plus_90: string;
  echeance_inconnue: string;
  total: string;
}

export interface Bilan {
  exercice_id: string;
  immobilisations: string;
  stocks: string;
  creances: string;
  tresorerie_actif: string;
  total_actif: string;
  ressources_durables: string;
  dettes_circulantes: string;
  tresorerie_passif: string;
  total_passif: string;
  equilibre: boolean;
}

export interface CompteResultatDetaille {
  exercice_id: string;
  total_charges_exploitation: string;
  total_produits_exploitation: string;
  resultat_exploitation: string;
  total_charges_financieres: string;
  total_produits_financiers: string;
  resultat_financier: string;
  resultat_activites_ordinaires: string;
  total_charges_hao: string;
  total_produits_hao: string;
  resultat_hao: string;
  resultat_net: string;
}

/**
 * Tableaux de bord Direction/Comptabilité (cahier des charges, section 22,
 * Étape 5) : pure agrégation de données déjà exposées ailleurs dans ce
 * module (échéancier, balance générale, compte de résultat) — aucun champ
 * "anomalies" (aucune notion équivalente dans ce projet, omis plutôt que
 * fabriqué) ; `exercice_id` null = aucun exercice ouvert ni passé couvrant
 * aujourd'hui pour cette entreprise.
 */
export interface TableauDirection {
  exercice_id: string | null;
  tresorerie_disponible: string;
  creances_clients_ouvertes: string;
  dettes_fournisseurs_ouvertes: string;
  echeances_clients_en_retard: number;
  echeances_fournisseurs_en_retard: number;
  resultat_net_exercice: string | null;
}

/**
 * `lignes_bancaires_non_lettrees` sert de proxy à "rapprochements en
 * attente" (aucune notion de rapprochement distincte du lettrage dans ce
 * projet, voir tresorerie/models.py).
 */
export interface TableauComptabilite {
  ecritures_brouillon: number;
  lignes_bancaires_non_lettrees: number;
  clotures_a_venir: number;
  demandes_non_traitees: number;
}

export interface ResultatDetectionAlertes {
  notifications_creees: Record<string, number>;
}

/**
 * Prévision de trésorerie (cahier, section "module trésorerie") :
 * projection du solde bancaire actuel sur un horizon glissant, à partir
 * des échéances clients/fournisseurs connues (voir `echeancier` côté
 * backend). `montant` signé comme dans `LigneEcheance` : positif =
 * encaissement attendu, négatif = décaissement attendu.
 */
export interface LignePrevisionTresorerie {
  date_echeance: string;
  libelle: string;
  montant: string;
  solde_cumule: string;
}

export interface PrevisionTresorerie {
  solde_actuel: string;
  horizon_jours: number;
  lignes: LignePrevisionTresorerie[];
  solde_final_projete: string;
  montant_sans_echeance_clients: string;
  montant_sans_echeance_fournisseurs: string;
}

// --- Tableau de bord (page d'accueil) --------------------------------------
// Alignés sur TableauBordLecture (schemas.py). Les montants sont des
// Decimal sérialisés en chaîne ; `variation_pourcentage` est un nombre.

export interface IndicateurComparatif {
  valeur: string;
  valeur_n1: string | null;
  variation_pourcentage: number | null;
}

export interface ActifCirculant {
  total: string;
  creances_clients: string;
  autres_creances: string;
  stocks: string;
}

export interface PassifCirculant {
  total: string;
  dettes_fournisseurs: string;
  dettes_fiscales: string;
  dettes_sociales: string;
  autres_dettes: string;
}

export interface BilanFonctionnel {
  immobilisations: string;
  actif_circulant: string;
  tresorerie_actif: string;
  ressources_durables: string;
  passif_circulant: string;
  tresorerie_passif: string;
}

export interface TableauBord {
  exercice_id: string;
  annee: number;
  annee_precedente: number | null;
  date_debut: string;
  date_fin: string;
  chiffre_affaires: IndicateurComparatif;
  marge_commerciale: IndicateurComparatif;
  valeur_ajoutee: IndicateurComparatif;
  excedent_brut_exploitation: IndicateurComparatif;
  resultat_exploitation: string;
  resultat_net: string;
  capacite_autofinancement: string;
  tresorerie: string;
  actif_circulant: ActifCirculant;
  passif_circulant: PassifCirculant;
  fonds_roulement: string;
  besoin_fonds_roulement: string;
  bilan_fonctionnel: BilanFonctionnel;
}