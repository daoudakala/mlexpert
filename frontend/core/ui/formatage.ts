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
