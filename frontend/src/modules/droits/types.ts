/**
 * Types alignés à la main sur app/modules/droits/schemas.py.
 */
import type { Entreprise } from "@/modules/entreprises/types";

export interface Permission {
  id: string;
  code: string;
  libelle: string;
}

export interface Role {
  id: string;
  code: string;
  libelle: string;
  est_role_plateforme: boolean;
  cree_le: string;
}

export interface Affectation {
  id: string;
  utilisateur_id: string;
  entreprise_id: string;
  role_id: string;
  module_restreint: string | null;
  exercice_id_restreint: string | null;
  actif: boolean;
  date_debut: string | null;
  date_fin: string | null;
  cree_le: string;
}

/**
 * Une entrée du portefeuille d'accès de l'utilisateur connecté — voir
 * ContexteAccesUtilisateurLecture / GET /droits/moi/contextes.
 * C'est la source de vérité du frontend pour les entreprises accessibles,
 * le rôle exercé dans chacune et les permissions qui en découlent (plus de
 * lecture de payload JWT depuis le passage aux cookies HttpOnly).
 */
export interface ContexteAccesUtilisateur {
  affectation_id: string;
  entreprise: Entreprise;
  role: Role;
  module_restreint: string | null;
  exercice_id_restreint: string | null;
  codes_permissions: string[];
}

export interface RoleCreation {
  code: string;
  libelle: string;
  est_role_plateforme?: boolean;
  codes_permissions?: string[] | null;
}

export interface RoleAvecPermissions extends Role {
  permissions: Permission[];
}

export interface RoleMiseAJour {
  code?: string;
  libelle?: string;
  // Remplace l'intégralité des permissions du rôle ; une liste vide les
  // retire toutes (voir ServiceDroits.modifier_role côté backend).
  codes_permissions?: string[] | null;
}

export interface AffectationCreation {
  utilisateur_id: string;
  role_id: string;
  module_restreint?: string | null;
  exercice_id_restreint?: string | null;
  date_debut?: string | null;
  date_fin?: string | null;
}

export interface AttributionRoleGlobalCreation {
  utilisateur_id: string;
  role_id: string;
}

/**
 * Invitation self-service (Étape 6) — voir InvitationCreation côté
 * backend. Si `email` correspond à un compte existant, il est réutilisé
 * tel quel (les autres champs sont alors ignorés côté backend) ; sinon un
 * nouveau compte est créé avec un mot de passe temporaire généré par le
 * serveur. `tiers_id` rattache le compte à un dossier client précis
 * (compte portail), à laisser vide pour un collaborateur interne.
 */
export interface InvitationCreation {
  email: string;
  nom: string;
  prenom: string;
  telephone?: string | null;
  role_id: string;
  tiers_id?: string | null;
}

export interface InvitationResultat {
  utilisateur_id: string;
  email: string;
  compte_existant: boolean;
  // Présent UNE SEULE FOIS si un nouveau compte a été créé — jamais
  // récupérable ensuite, à transmettre hors-bande par qui invite.
  mot_de_passe_temporaire: string | null;
  affectation: Affectation;
}

export interface AttributionRoleGlobal {
  id: string;
  utilisateur_id: string;
  role_id: string;
  actif: boolean;
}