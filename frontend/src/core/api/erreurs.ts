/**
 * Toutes les erreurs métier du backend arrivent au même format (voir
 * app/core/exceptions.py::enregistrer_gestionnaires_erreurs) :
 *   {"erreur": {"code": "...", "message": "...", "details": {...} | null}}
 * sauf les 422 de validation Pydantic natifs (corps malformé), qui ont
 * leur propre forme ({"detail": [...]}) — gérés ici aussi pour ne pas
 * laisser échapper un message "[object Object]" dans un formulaire.
 */
import { isAxiosError } from "axios";

export interface ErreurApi {
  code: string;
  message: string;
  details?: Record<string, unknown> | null;
}

export function erreurApi(erreur: unknown): ErreurApi | null {
  if (!isAxiosError(erreur)) return null;
  const corps = erreur.response?.data as { erreur?: ErreurApi } | undefined;
  return corps?.erreur ?? null;
}

/** Message lisible à afficher dans un formulaire, quelle que soit la forme
 * de l'erreur (métier, validation Pydantic, réseau). */
export function messageErreur(erreur: unknown): string {
  const erreurMetier = erreurApi(erreur);
  if (erreurMetier) return erreurMetier.message;

  if (isAxiosError(erreur)) {
    const detail = (erreur.response?.data as { detail?: unknown } | undefined)?.detail;
    if (Array.isArray(detail) && detail.length > 0) {
      // Erreur de validation Pydantic native : [{loc, msg, ...}, ...]
      return detail.map((d) => (typeof d?.msg === "string" ? d.msg : JSON.stringify(d))).join(" ");
    }
    if (erreur.response === undefined) {
      return "Impossible de joindre le serveur.";
    }
  }
  return "Une erreur inattendue est survenue.";
}
