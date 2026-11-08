/**
 * Types alignés à la main sur app/modules/utilisateurs/schemas.py.
 * Pas de génération automatique (choix assumé) : à mettre à jour
 * manuellement si le schéma backend change.
 */

export interface Utilisateur {
  id: string;
  email: string;
  nom: string;
  prenom: string;
  telephone: string | null;
  actif: boolean;
  mfa_active: boolean;
  derniere_connexion_le: string | null;
  cree_le: string;
}

/** Réponse de GET /utilisateurs/moi uniquement — `Utilisateur` + le
 * statut d'administrateur plateforme (mécanisme séparé des permissions
 * par entreprise, voir MonProfilLecture côté backend). */
export interface MonProfil extends Utilisateur {
  administrateur_plateforme: boolean;
}

export interface UtilisateurCreation {
  email: string;
  mot_de_passe: string;
  nom: string;
  prenom: string;
  telephone?: string | null;
}

export interface UtilisateurMiseAJourProfil {
  nom?: string;
  prenom?: string;
  telephone?: string | null;
}

export interface ChangementMotDePasse {
  ancien_mot_de_passe: string;
  nouveau_mot_de_passe: string;
}

export interface ReinitialisationMotDePasse {
  nouveau_mot_de_passe: string;
}

