/**
 * Types alignés à la main sur app/modules/paie/schemas.py.
 */

export type StatutEmploye = "actif" | "inactif";

export interface Employe {
  id: string;
  entreprise_id: string;
  matricule: string;
  nom: string;
  prenom: string;
  poste: string | null;
  date_embauche: string;
  date_sortie: string | null;
  salaire_base: string; // Decimal sérialisé en chaîne par Pydantic
  statut: StatutEmploye;
  cree_le: string;
}

export interface EmployeCreation {
  matricule: string;
  nom: string;
  prenom: string;
  poste?: string | null;
  date_embauche: string;
  salaire_base: number;
}

export interface EmployeMiseAJour {
  nom?: string;
  prenom?: string;
  poste?: string | null;
  salaire_base?: number;
}

export type TypeRubriquePaie = "gain" | "retenue";

export interface RubriquePaie {
  id: string;
  entreprise_id: string;
  code: string;
  libelle: string;
  type_rubrique: TypeRubriquePaie;
  actif: boolean;
  compte_comptable_id: string | null;
}

export interface RubriquePaieCreation {
  code: string;
  libelle: string;
  type_rubrique: TypeRubriquePaie;
  compte_comptable_id?: string | null;
}

export type StatutBulletin = "brouillon" | "valide";

export interface LigneBulletinSaisie {
  rubrique_id: string;
  montant: number;
  libelle?: string | null;
}

export interface LigneBulletin {
  id: string;
  bulletin_id: string;
  rubrique_id: string;
  libelle: string | null;
  montant: string;
}

export interface Bulletin {
  id: string;
  entreprise_id: string;
  employe_id: string;
  exercice_id: string;
  periode_debut: string;
  periode_fin: string;
  statut: StatutBulletin;
  salaire_brut: string;
  total_retenues: string;
  net_a_payer: string;
  ecriture_id: string | null;
  cree_le: string;
}

export interface BulletinCreation {
  employe_id: string;
  exercice_id: string;
  periode_debut: string;
  periode_fin: string;
  lignes: LigneBulletinSaisie[];
}

export interface BulletinMiseAJourLignes {
  lignes: LigneBulletinSaisie[];
}

export interface GenerationEcritureBulletinDemande {
  journal_id: string;
  compte_net_a_payer_id: string;
}
