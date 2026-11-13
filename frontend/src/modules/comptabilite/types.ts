/**
 * Types alignés à la main sur app/modules/comptabilite/schemas.py.
 * `Journal` et `LigneEcritureLecture` sont repris en plus de `Compte` car
 * le module trésorerie en a besoin (journal/compte d'un compte bancaire,
 * écritures candidates au rapprochement) — le reste du module comptabilité
 * (saisie d'écritures) arrivera quand ce sera son tour.
 */

export interface Compte {
  id: string;
  numero: string;
  libelle: string;
  classe: number;
  lettrable: boolean;
  est_collectif: boolean;
  actif: boolean;
  entreprise_id: string | null;
  // Sous-compte (hiérarchie parent/enfant) : nul si ce compte n'a pas de
  // parent explicite — orthogonal à `entreprise_id` (voir models.py côté
  // backend).
  compte_parent_id: string | null;
  cree_le: string;
}

export type TypeJournal = "achats" | "ventes" | "banque" | "caisse" | "operations_diverses" | "a_nouveaux";

export interface Journal {
  id: string;
  entreprise_id: string;
  code: string;
  libelle: string;
  type_journal: TypeJournal;
  actif: boolean;
  cree_le: string;
}

export interface LigneEcritureLecture {
  id: string;
  compte_id: string;
  tiers_id: string | null;
  libelle: string | null;
  debit: string; // Decimal sérialisé en chaîne par Pydantic
  credit: string;
  code_lettrage: string | null;
}

export interface LigneEcritureSaisie {
  compte_id: string;
  debit?: number;
  credit?: number;
  tiers_id?: string | null;
  libelle?: string | null;
}

export interface CompteCreation {
  numero: string;
  libelle: string;
  classe: number;
  lettrable?: boolean;
  est_collectif?: boolean;
  compte_parent_id?: string | null;
}

export interface CompteImportIgnore {
  numero: string;
  libelle: string;
  raison: string;
}

export interface CompteImportResultat {
  comptes_crees: Compte[];
  ignores: CompteImportIgnore[];
}

export interface JournalCreation {
  code: string;
  libelle: string;
  type_journal: TypeJournal;
}

export type StatutEcriture = "brouillon" | "validee";

export interface EcritureCreation {
  journal_id: string;
  // Facultatif : le backend retrouve l'exercice à partir de la date.
  exercice_id?: string | null;
  date_ecriture: string;
  libelle: string;
  reference_piece?: string | null;
  lignes: LigneEcritureSaisie[];
}

export interface EcritureMiseAJour {
  date_ecriture?: string;
  libelle?: string;
  reference_piece?: string | null;
  lignes?: LigneEcritureSaisie[] | null;
}

export interface EcritureExtourne {
  date_ecriture: string;
  libelle?: string | null;
}

export interface EcritureDuplication {
  date_ecriture: string;
  exercice_id?: string | null;
  libelle?: string | null;
}

// --- Import d'écritures (CSV/Excel) -----------------------------------------
// Format : journal, date (AAAA-MM-JJ), pièce, compte, libellé, débit,
// crédit par ligne — les lignes qui partagent journal+date+pièce forment
// une seule écriture (voir ServiceComptabilite.importer_ecritures côté
// backend).

export interface EcritureImportIgnoree {
  journal: string;
  date: string;
  piece: string;
  raison: string;
}

export interface EcritureImportResultat {
  ecritures_creees: EcritureAvecLignes[];
  ignorees: EcritureImportIgnoree[];
}

export interface EcritureLecture {
  id: string;
  entreprise_id: string;
  journal_id: string;
  exercice_id: string;
  date_ecriture: string;
  libelle: string;
  reference_piece: string | null;
  statut: StatutEcriture;
  numero: string | null;
  ecriture_extournee_id: string | null;
  cree_le: string;
}

export interface EcritureAvecLignes extends EcritureLecture {
  lignes: LigneEcritureLecture[];
}

// --- Modèles d'écriture (saisie par modèle) ---------------------------------
// Un modèle fige le compte et le sens de chaque ligne, jamais le montant :
// celui-ci est toujours saisi au moment d'appliquer le modèle (voir
// ServiceComptabilite.appliquer_modele côté backend).

export type SensLigne = "debit" | "credit";

export interface LigneModeleSaisie {
  compte_id: string;
  sens: SensLigne;
  libelle?: string | null;
}

export interface LigneModeleLecture {
  id: string;
  compte_id: string;
  sens: SensLigne;
  libelle: string | null;
}

export interface ModeleEcritureCreation {
  code: string;
  libelle: string;
  journal_id: string;
  lignes: LigneModeleSaisie[];
}

export interface ModeleEcritureMiseAJour {
  code?: string;
  libelle?: string;
  journal_id?: string;
  actif?: boolean;
  lignes?: LigneModeleSaisie[] | null;
}

export interface ModeleEcritureLecture {
  id: string;
  entreprise_id: string;
  code: string;
  libelle: string;
  journal_id: string;
  actif: boolean;
  cree_le: string;
}

export interface ModeleEcritureAvecLignes extends ModeleEcritureLecture {
  lignes: LigneModeleLecture[];
}

export interface MontantLigneModele {
  ligne_modele_id: string;
  montant: number;
}

export interface AppliquerModeleDonnees {
  exercice_id: string;
  date_ecriture: string;
  libelle?: string | null;
  reference_piece?: string | null;
  lignes: MontantLigneModele[];
}
// --- Mois de travail (périodes d'un exercice) -------------------------------

export interface PeriodeMois {
  id: string;
  exercice_id: string;
  libelle: string | null;
  date_debut: string;
  date_fin: string;
  statut: "ouverte" | "cloturee";
}

// --- Récapitulatif d'un journal de caisse / banque --------------------------
// Montants Decimal sérialisés en chaîne ; solde = débit − crédit.

export interface MouvementJournalTresorerie {
  ecriture_id: string;
  date_ecriture: string;
  numero: string | null;
  libelle: string;
  compte_numero: string;
  debit: string;
  credit: string;
  solde_cumule: string;
}

export interface ResumeJournalTresorerie {
  journal_id: string;
  date_debut: string;
  date_fin: string;
  solde_initial: string;
  total_debit: string;
  total_credit: string;
  solde_final: string;
  mouvements: MouvementJournalTresorerie[];
}