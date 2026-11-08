/**
 * Formatage des montants pour l'affichage : séparateur de milliers,
 * convention française/OHADA (espace entre les groupes de 3 chiffres,
 * virgule décimale). Les montants viennent du backend en `Decimal`
 * sérialisé en chaîne par Pydantic — cette fonction accepte les deux.
 */
export function formaterMontant(valeur: number | string | null | undefined): string {
  if (valeur === null || valeur === undefined || valeur === "") return "";
  const nombre = typeof valeur === "string" ? Number(valeur) : valeur;
  if (Number.isNaN(nombre)) return String(valeur);
  return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 }).format(nombre);
}

/**
 * Formatage d'un horodatage (date + heure) pour l'affichage. Le backend
 * sérialise ses `datetime` en ISO 8601 (ex. "2026-10-09T13:20:01.727207") ;
 * affiché brut, ce format est illisible — cette fonction le rend en
 * "09/10/2026 13:20" (fr-FR). Reprend le motif déjà utilisé localement dans
 * journal_activite/FilCommentaires, centralisé ici pour les nouveaux usages.
 */
export function formaterDate(valeur: string | null | undefined): string {
  if (!valeur) return "";
  const date = new Date(valeur);
  if (Number.isNaN(date.getTime())) return valeur;
  return date.toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" });
}