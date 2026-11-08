<script setup lang="ts">
/**
 * Lettrage manuel (cahier des charges, section 8.2) : rapproche entre
 * elles des lignes d'un même compte lettrable qui s'annulent — typiquement
 * une facture et son règlement. S'applique aussi bien à un compte général
 * lettrable qu'à un compte collectif de tiers (411/401) ; dans ce second
 * cas, on exige de choisir un tiers précis AVANT d'afficher quoi que ce
 * soit, sans quoi la liste mélangerait les factures/règlements de tous les
 * clients ou fournisseurs de l'entreprise (le backend refuserait de toute
 * façon de lettrer des lignes de tiers différents — voir
 * ServiceComptabilite.lettrer côté backend).
 *
 * Deux onglets : les lignes NON lettrées (candidates, à cocher pour former
 * un lettrage dont le solde doit tomber à zéro) et les lignes déjà
 * lettrées (regroupées par code, avec un bouton pour annuler un groupe).
 *
 * Rapprochement des tiers (section 8.3) : au-dessus de la liste des
 * candidates, un bandeau de suggestions propose des regroupements dont le
 * solde tombe déjà à zéro (voir proposerGroupesLettrage.ts) — un clic
 * préremplit juste la sélection, la validation reste manuelle via le
 * bouton "Lettrer" habituel et tous ses contrôles.
 */
import { computed, reactive, ref } from "vue";

import { useAuth } from "@/core/auth/useAuth";
import { messageErreur } from "@/core/api/erreurs";
import { formaterMontant } from "@/core/ui/formatage";
import { useComptesEntreprise, useLignesLettrage, useMutationsLettrage } from "./api";
import { useListeTiers } from "@/modules/tiers/api";
import { proposerGroupesLettrage } from "./proposerGroupesLettrage";
import type { LigneLettrage } from "./types";

const { contexteActif, aPermission } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const { data: comptes } = useComptesEntreprise(entrepriseId);
const comptesLettrables = computed(() => (comptes.value ?? []).filter((c) => c.lettrable));

const compteId = ref<string | null>(null);
const compteActif = computed(() => comptesLettrables.value.find((c) => c.id === compteId.value) ?? null);

const { data: tiersListe } = useListeTiers(entrepriseId, computed(() => ({ actifsSeulement: true })));
const tiersId = ref<string | null>(null);

// Un compte collectif exige un tiers choisi pour afficher quoi que ce soit
// (voir la note de tête de fichier) ; un compte lettrable ordinaire n'en a
// pas besoin.
const pretAAfficher = computed(() => !!compteId.value && (!compteActif.value?.est_collectif || !!tiersId.value));

function surChangementCompte(): void {
  tiersId.value = null;
  selection.clear();
}

const onglet = ref<"non-lettrees" | "lettrees">("non-lettrees");

const filtresNonLettrees = computed(() => ({
  tiersId: tiersId.value,
  lettrees: false as const,
}));
const { data: lignesNonLettrees, isLoading: chargementNonLettrees } = useLignesLettrage(
  entrepriseId,
  computed(() => (pretAAfficher.value ? compteId.value : null)),
  filtresNonLettrees,
);

const filtresLettrees = computed(() => ({
  tiersId: tiersId.value,
  lettrees: true as const,
}));
const { data: lignesLettrees, isLoading: chargementLettrees } = useLignesLettrage(
  entrepriseId,
  computed(() => (pretAAfficher.value && onglet.value === "lettrees" ? compteId.value : null)),
  filtresLettrees,
);

const groupesLettres = computed(() => {
  const groupes = new Map<string, LigneLettrage[]>();
  for (const ligne of lignesLettrees.value ?? []) {
    const code = ligne.code_lettrage!;
    if (!groupes.has(code)) groupes.set(code, []);
    groupes.get(code)!.push(ligne);
  }
  return Array.from(groupes.entries());
});

// --- Sélection pour un nouveau lettrage -------------------------------------

const selection = reactive(new Set<string>());

function basculerSelection(ligne: LigneLettrage): void {
  if (selection.has(ligne.id)) selection.delete(ligne.id);
  else selection.add(ligne.id);
}

const lignesSelectionnees = computed(() =>
  (lignesNonLettrees.value ?? []).filter((l) => selection.has(l.id)),
);
const solde = computed(() =>
  lignesSelectionnees.value.reduce((s, l) => s + (Number(l.debit) - Number(l.credit)), 0),
);
const equilibre = computed(() => Math.abs(solde.value) < 0.005);
const peutLettrer = computed(() => lignesSelectionnees.value.length >= 2 && equilibre.value);

// --- Rapprochement des tiers : suggestions automatiques ---------------------

const propositions = computed(() => proposerGroupesLettrage(lignesNonLettrees.value ?? []));

function selectionnerProposition(lignes: LigneLettrage[]): void {
  selection.clear();
  for (const l of lignes) selection.add(l.id);
}

const { lettrer, delettrer } = useMutationsLettrage(entrepriseId);
const erreurLettrage = ref<string | null>(null);

async function soumettreLettrage(): Promise<void> {
  erreurLettrage.value = null;
  try {
    await lettrer.mutateAsync({ ligne_ecriture_ids: Array.from(selection) });
    selection.clear();
  } catch (e) {
    erreurLettrage.value = messageErreur(e);
  }
}

async function delettrerGroupe(code: string): Promise<void> {
  await delettrer.mutateAsync(code);
}
</script>

<template>
  <div class="space-y-4">
    <h1 class="text-lg font-semibold text-text">Lettrage manuel</h1>

    <div class="flex flex-wrap items-end gap-4 rounded-lg border border-border bg-surface p-4">
      <div>
        <label class="mb-1 block text-sm font-medium text-text">Compte lettrable</label>
        <select
          v-model="compteId"
          class="w-64 rounded-md border border-border px-3 py-2 text-sm text-text"
          @change="surChangementCompte"
        >
          <option :value="null" disabled>— Choisir —</option>
          <option v-for="c in comptesLettrables" :key="c.id" :value="c.id">{{ c.numero }} — {{ c.libelle }}</option>
        </select>
      </div>
      <div v-if="compteActif?.est_collectif">
        <label class="mb-1 block text-sm font-medium text-text">Tiers (obligatoire — compte collectif)</label>
        <select v-model="tiersId" class="w-64 rounded-md border border-border px-3 py-2 text-sm text-text">
          <option :value="null" disabled>— Choisir —</option>
          <option v-for="t in tiersListe" :key="t.id" :value="t.id">{{ t.code }} — {{ t.raison_sociale }}</option>
        </select>
      </div>
    </div>

    <p v-if="compteId && !pretAAfficher" class="text-sm text-text-muted">
      Choisis un tiers pour afficher ses lignes — ce compte collectif porte les comptes de plusieurs
      tiers à la fois.
    </p>

    <template v-if="pretAAfficher">
      <div class="flex gap-2 border-b border-border">
        <button
          type="button"
          class="px-3 py-2 text-sm"
          :class="onglet === 'non-lettrees' ? 'border-b-2 border-primary font-medium text-text' : 'text-text-muted'"
          @click="onglet = 'non-lettrees'"
        >
          Non lettrées
        </button>
        <button
          type="button"
          class="px-3 py-2 text-sm"
          :class="onglet === 'lettrees' ? 'border-b-2 border-primary font-medium text-text' : 'text-text-muted'"
          @click="onglet = 'lettrees'"
        >
          Lettrées
        </button>
      </div>

      <div v-if="onglet === 'non-lettrees'" class="space-y-3">
        <div v-if="propositions.length > 0" class="space-y-2 rounded-lg border border-border bg-surface p-4">
          <h2 class="text-sm font-semibold text-text">Suggestions de rapprochement</h2>
          <p class="text-xs text-text-muted">
            Ces regroupements se soldent déjà à zéro — vérifie-les puis clique pour préremplir la
            sélection ci-dessous (la validation reste manuelle).
          </p>
          <ul class="divide-y divide-border text-sm">
            <li
              v-for="(p, index) in propositions"
              :key="index"
              class="flex items-center justify-between py-2"
            >
              <span class="text-text">
                {{ p.lignes.map((l) => l.reference_piece || l.numero || "—").join(" + ") }}
                <span class="text-text-muted">— {{ formaterMontant(p.montant) }}</span>
              </span>
              <button
                type="button"
                class="text-sm text-primary hover:underline"
                @click="selectionnerProposition(p.lignes)"
              >
                Sélectionner
              </button>
            </li>
          </ul>
        </div>

        <div class="overflow-hidden rounded-lg border border-border">
          <table class="w-full text-sm">
            <thead class="bg-surface-muted text-left text-xs font-medium uppercase text-text-muted">
              <tr>
                <th class="px-3 py-2"></th>
                <th class="px-3 py-2">Date</th>
                <th class="px-3 py-2">N°</th>
                <th class="px-3 py-2">Référence</th>
                <th class="px-3 py-2">Libellé</th>
                <th class="px-3 py-2 text-right">Débit</th>
                <th class="px-3 py-2 text-right">Crédit</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-border">
              <tr v-if="chargementNonLettrees"><td colspan="7" class="px-3 py-4 text-center text-text-muted">Chargement…</td></tr>
              <tr v-else-if="(lignesNonLettrees ?? []).length === 0">
                <td colspan="7" class="px-3 py-4 text-center text-text-muted">Aucune ligne non lettrée.</td>
              </tr>
              <tr
                v-for="l in lignesNonLettrees"
                :key="l.id"
                class="cursor-pointer hover:bg-surface-muted"
                :class="{ 'bg-primary/5': selection.has(l.id) }"
                @click="basculerSelection(l)"
              >
                <td class="px-3 py-2">
                  <input type="checkbox" :checked="selection.has(l.id)" @click.stop="basculerSelection(l)" />
                </td>
                <td class="px-3 py-2 text-text">{{ l.date_ecriture }}</td>
                <td class="px-3 py-2 text-text">{{ l.numero ?? "—" }}</td>
                <td class="px-3 py-2 text-text">{{ l.reference_piece ?? "—" }}</td>
                <td class="px-3 py-2 text-text">{{ l.libelle_ligne ?? l.libelle_ecriture }}</td>
                <td class="px-3 py-2 text-right text-text">{{ Number(l.debit) > 0 ? formaterMontant(l.debit) : "" }}</td>
                <td class="px-3 py-2 text-right text-text">{{ Number(l.credit) > 0 ? formaterMontant(l.credit) : "" }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div
          v-if="aPermission('lettrage.creer')"
          class="flex items-center justify-between rounded-lg border border-border bg-surface p-4"
        >
          <div class="text-sm">
            <span class="text-text-muted">{{ lignesSelectionnees.length }} ligne(s) sélectionnée(s) — solde : </span>
            <span :class="equilibre ? 'text-success' : 'text-danger'">{{ formaterMontant(solde) }}</span>
            <p v-if="erreurLettrage" class="mt-1 text-danger">{{ erreurLettrage }}</p>
          </div>
          <button
            type="button"
            :disabled="!peutLettrer || lettrer.isPending.value"
            class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-40"
            @click="soumettreLettrage"
          >
            Lettrer
          </button>
        </div>
      </div>

      <div v-else class="space-y-3">
        <p v-if="chargementLettrees" class="text-sm text-text-muted">Chargement…</p>
        <p v-else-if="groupesLettres.length === 0" class="text-sm text-text-muted">Aucun lettrage pour le moment.</p>
        <div v-for="[code, lignes] in groupesLettres" :key="code" class="overflow-hidden rounded-lg border border-border">
          <div class="flex items-center justify-between bg-surface-muted px-3 py-2">
            <span class="text-sm font-medium text-text">Lettrage {{ code }}</span>
            <button
              v-if="aPermission('lettrage.annuler')"
              type="button"
              class="text-sm text-danger hover:underline"
              @click="delettrerGroupe(code)"
            >
              Annuler ce lettrage
            </button>
          </div>
          <table class="w-full text-sm">
            <tbody class="divide-y divide-border">
              <tr v-for="l in lignes" :key="l.id">
                <td class="px-3 py-2 text-text">{{ l.date_ecriture }}</td>
                <td class="px-3 py-2 text-text">{{ l.numero ?? "—" }}</td>
                <td class="px-3 py-2 text-text">{{ l.reference_piece ?? "—" }}</td>
                <td class="px-3 py-2 text-text">{{ l.libelle_ligne ?? l.libelle_ecriture }}</td>
                <td class="px-3 py-2 text-right text-text">{{ Number(l.debit) > 0 ? formaterMontant(l.debit) : "" }}</td>
                <td class="px-3 py-2 text-right text-text">{{ Number(l.credit) > 0 ? formaterMontant(l.credit) : "" }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>