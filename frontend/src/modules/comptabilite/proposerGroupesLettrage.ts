/**
 * Rapprochement des tiers (cahier des charges, section 8.3) : propose
 * automatiquement des regroupements de lignes non lettrées dont le solde
 * tombe à zéro — pour qu'il ne reste qu'à vérifier et valider, plutôt que
 * de chercher la facture correspondant à un règlement ligne par ligne.
 *
 * Pas de nouvelle donnée externe (pas de relevé à importer) : l'algorithme
 * travaille uniquement sur les lignes non lettrées déjà chargées par
 * l'écran de lettrage manuel (voir LettrageManuel.vue). Il ne modifie
 * jamais rien lui-même — une proposition ne fait que préremplir la
 * sélection ; c'est toujours `POST .../lettrages` (et tous ses contrôles :
 * même tiers, même compte, écritures validées, solde à zéro) qui a le
 * dernier mot.
 *
 * Stratégie, par ordre de priorité :
 * 1. Paires exactes (1 débit + 1 crédit de même montant) — le cas le plus
 *    courant (une facture, son règlement).
 * 2. Une ligne contre plusieurs du côté opposé dont la somme égale son
 *    montant (un règlement qui solde 2 à 4 factures, ou l'inverse) —
 *    recherche combinatoire bornée (au plus 4 lignes par groupe, au plus
 *    `LIMITE_COMBINATOIRE` lignes disponibles du côté opposé) pour rester
 *    instantané même avec plusieurs dizaines de lignes en attente.
 *
 * Chaque ligne n'apparaît que dans une seule proposition (glouton : les
 * paires exactes sont formées en premier, les lignes restantes seulement
 * ensuite) — un algorithme optimal de partitionnement n'apporterait pas
 * grand-chose de plus pour ce que le cahier demande (une aide à la
 * sélection, pas une résolution automatique garantie).
 */

export interface LigneProposable {
  id: string;
  debit: string | number;
  credit: string | number;
}

export interface PropositionLettrage<T extends LigneProposable> {
  lignes: T[];
  montant: number;
}

const TOLERANCE = 0.005;
const TAILLE_GROUPE_MAX = 4;
const LIMITE_COMBINATOIRE = 12;

function combinaisons<T>(items: T[], taille: number): T[][] {
  const resultats: T[][] = [];
  const combo: T[] = [];
  function recurse(depart: number): void {
    if (combo.length === taille) {
      resultats.push([...combo]);
      return;
    }
    for (let i = depart; i < items.length; i++) {
      combo.push(items[i]);
      recurse(i + 1);
      combo.pop();
    }
  }
  recurse(0);
  return resultats;
}

export function proposerGroupesLettrage<T extends LigneProposable>(
  lignes: T[],
): PropositionLettrage<T>[] {
  const debits = lignes
    .map((l) => ({ ligne: l, montant: Number(l.debit) }))
    .filter((d) => d.montant > 0);
  const credits = lignes
    .map((l) => ({ ligne: l, montant: Number(l.credit) }))
    .filter((c) => c.montant > 0);

  const utilisesDebit = new Set<string>();
  const utilisesCredit = new Set<string>();
  const propositions: PropositionLettrage<T>[] = [];

  // 1. Paires exactes.
  for (const d of debits) {
    if (utilisesDebit.has(d.ligne.id)) continue;
    const c = credits.find(
      (c) => !utilisesCredit.has(c.ligne.id) && Math.abs(c.montant - d.montant) < TOLERANCE,
    );
    if (c) {
      utilisesDebit.add(d.ligne.id);
      utilisesCredit.add(c.ligne.id);
      propositions.push({ lignes: [d.ligne, c.ligne], montant: d.montant });
    }
  }

  // 2. Une ligne contre une combinaison de 2 à 4 lignes du côté opposé.
  function essayerUnContrePlusieurs(
    unCote: { ligne: T; montant: number }[],
    autreCote: { ligne: T; montant: number }[],
    utilisesUnCote: Set<string>,
    utilisesAutreCote: Set<string>,
  ): void {
    for (const u of unCote) {
      if (utilesDejaUtilise(u, utilisesUnCote)) continue;
      const disponibles = autreCote.filter((a) => !utilisesAutreCote.has(a.ligne.id));
      if (disponibles.length > LIMITE_COMBINATOIRE) continue;
      let trouve: { ligne: T; montant: number }[] | null = null;
      for (let taille = 2; taille <= Math.min(TAILLE_GROUPE_MAX, disponibles.length) && !trouve; taille++) {
        for (const combo of combinaisons(disponibles, taille)) {
          const somme = combo.reduce((s, x) => s + x.montant, 0);
          if (Math.abs(somme - u.montant) < TOLERANCE) {
            trouve = combo;
            break;
          }
        }
      }
      if (trouve) {
        utilisesUnCote.add(u.ligne.id);
        trouve.forEach((t) => utilisesAutreCote.add(t.ligne.id));
        propositions.push({ lignes: [u.ligne, ...trouve.map((t) => t.ligne)], montant: u.montant });
      }
    }
  }
  function utilesDejaUtilise(u: { ligne: T }, ensemble: Set<string>): boolean {
    return ensemble.has(u.ligne.id);
  }

  essayerUnContrePlusieurs(debits, credits, utilisesDebit, utilisesCredit);
  essayerUnContrePlusieurs(credits, debits, utilisesCredit, utilisesDebit);

  return propositions;
}