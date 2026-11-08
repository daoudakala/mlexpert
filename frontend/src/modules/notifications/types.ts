/**
 * Types alignés à la main sur app/modules/notifications/schemas.py.
 * Infrastructure seule (voir la docstring de models.py côté backend) :
 * ce module ne propose aucune route de création, seulement la lecture et
 * la gestion de SES PROPRES notifications et préférences.
 */

export type TypeNotification =
  | "echeance_client"
  | "echeance_fournisseur"
  | "document_manquant"
  | "demande_piece_non_traitee"
  | "validation_en_attente"
  | "cloture_comptable"
  | "alerte_securite"
  | "message_portail";

export type NiveauCriticite = "info" | "avertissement" | "critique";

// Libellés affichés pour chaque type connu — une valeur future non
// listée ici (ajoutée par un module qui n'existe pas encore) s'affiche
// simplement telle quelle (voir `libelleType` dans NotificationCloche.vue).
export const LIBELLES_TYPE_NOTIFICATION: Record<TypeNotification, string> = {
  echeance_client: "Échéance client",
  echeance_fournisseur: "Échéance fournisseur",
  document_manquant: "Document manquant",
  demande_piece_non_traitee: "Demande de pièce non traitée",
  validation_en_attente: "Validation en attente",
  cloture_comptable: "Clôture comptable",
  alerte_securite: "Alerte de sécurité",
  message_portail: "Message du portail client",
};

export interface Notification {
  id: string;
  type_notification: string;
  niveau_criticite: NiveauCriticite;
  canal: string;
  titre: string;
  message: string;
  type_objet: string | null;
  objet_id: string | null;
  lu: boolean;
  lu_le: string | null;
  cree_le: string;
}

export interface CompteurNotifications {
  non_lues: number;
}

export interface PreferenceNotification {
  type_notification: string;
  active: boolean;
  niveau_minimum: NiveauCriticite;
}

export interface PreferenceNotificationEcriture {
  active: boolean;
  niveau_minimum: NiveauCriticite;
}