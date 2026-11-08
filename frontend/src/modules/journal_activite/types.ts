/**
 * Types alignés à la main sur app/modules/journal_activite/schemas.py.
 * Le journal ne s'écrit jamais depuis le frontend (ni même ailleurs que
 * via ServiceJournalActivite.enregistrer() côté backend, appelé par les
 * autres services) : aucun type de création ici, uniquement la lecture.
 */

export interface EntreeJournalActivite {
  id: string;
  survenu_le: string;
  utilisateur_id: string | null;
  // Résolus côté backend (voir ServiceJournalActivite._enrichir) : nuls
  // pour un événement système, une connexion non résolue, ou si le
  // compte a depuis été supprimé (voir la note de tête de fichier de
  // models.py côté backend).
  utilisateur_nom: string | null;
  utilisateur_prenom: string | null;
  utilisateur_email: string | null;
  entreprise_id: string | null;
  module: string;
  type_action: string;
  type_objet: string | null;
  objet_id: string | null;
  description: string | null;
  valeurs_avant: Record<string, unknown> | null;
  valeurs_apres: Record<string, unknown> | null;
  adresse_ip: string | null;
}
