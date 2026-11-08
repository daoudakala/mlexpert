/**
 * Types alignés à la main sur app/modules/exercices/schemas.py.
 */

export interface Exercice {
  id: string;
  entreprise_id: string;
  date_debut: string;
  date_fin: string;
  statut: "ouvert" | "cloture";
  exercice_precedent_id: string | null;
  cree_le: string;
}

export interface ExerciceCreation {
  date_debut: string;
  date_fin: string;
  exercice_precedent_id?: string | null;
}

export interface Periode {
  id: string;
  entreprise_id: string;
  exercice_id: string;
  libelle: string | null;
  date_debut: string;
  date_fin: string;
  statut: "ouverte" | "cloturee";
  cree_le: string;
}

export interface PeriodeCreation {
  date_debut: string;
  date_fin: string;
  libelle?: string | null;
}
