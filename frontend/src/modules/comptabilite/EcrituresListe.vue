<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useAuth } from "@/core/auth/useAuth";
import BaseDataTable, { type ColonneTable } from "@/core/ui/BaseDataTable.vue";
import StatutBadge from "@/core/ui/StatutBadge.vue";
import { messageErreur } from "@/core/api/erreurs";
import { useJournaux, useListeEcritures, useMutationsEcritures, type FiltresEcritures } from "./api";
import { useExercices } from "@/modules/exercices/api";
import type { EcritureImportResultat, EcritureLecture } from "./types";

const router = useRouter();
const route = useRoute();
const { contexteActif, aPermission } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const { data: journaux } = useJournaux(entrepriseId);
const { data: exercices } = useExercices(entrepriseId);

const filtres = reactive<FiltresEcritures>({ journalId: null, exerciceId: null, statut: null });
const { data: ecritures, isLoading } = useListeEcritures(entrepriseId, computed(() => filtres));
const { importer } = useMutationsEcritures(entrepriseId);

// Le menu latéral filtre par journal via ?journal=<code> (ex. BQ, VT).
const codeJournalDemande = computed(() =>
  typeof route.query.journal === "string" ? route.query.journal : null,
);
const journalDemande = computed(
  () => journaux.value?.find((j) => j.code === codeJournalDemande.value) ?? null,
);
watch(
  [codeJournalDemande, journalDemande],
  () => {
    filtres.journalId = codeJournalDemande.value ? (journalDemande.value?.id ?? null) : null;
  },
  { immediate: true },
);

// --- Import d'écritures (CSV/Excel) -----------------------------------------

const importOuvert = ref(false);
const fichierImport = ref<File | null>(null);
const erreurImport = ref<string | null>(null);
const resultatImport = ref<EcritureImportResultat | null>(null);

function choisirFichier(e: Event): void {
  fichierImport.value = (e.target as HTMLInputElement).files?.[0] ?? null;
}

async function soumettreImport(): Promise<void> {
  if (!fichierImport.value) return;
  erreurImport.value = null;
  resultatImport.value = null;
  try {
    resultatImport.value = await importer.mutateAsync(fichierImport.value);
    fichierImport.value = null;
  } catch (e) {
    erreurImport.value = messageErreur(e);
  }
}

const colonnes: ColonneTable<EcritureLecture>[] = [
  { cle: "numero", libelle: "N°" },
  { cle: "date_ecriture", libelle: "Date" },
  { cle: "libelle", libelle: "Libellé" },
  { cle: "reference_piece", libelle: "Référence" },
  { cle: "statut", libelle: "Statut" },
];

function ouvrir(ligne: EcritureLecture): void {
  router.push({ name: "comptabilite.ecriture", params: { id: ligne.id } });
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-lg font-semibold text-text">Écritures</h1>
      <div class="flex gap-2">
        <button
          v-if="aPermission('ecriture.creer')"
          type="button"
          class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted"
          @click="importOuvert = !importOuvert"
        >
          Importer
        </button>
        <router-link
          v-if="aPermission('ecriture.creer')"
          :to="{ name: 'comptabilite.ecriture.nouvelle', query: codeJournalDemande ? { journal: codeJournalDemande } : {} }"
          class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover"
        >
          Nouvelle écriture
        </router-link>
      </div>
    </div>

    <form
      v-if="importOuvert"
      class="space-y-4 rounded-lg border border-border bg-surface p-6"
      @submit.prevent="soumettreImport"
    >
      <div>
        <label class="mb-1 block text-sm font-medium text-text">Fichier (CSV ou Excel)</label>
        <input
          type="file"
          accept=".csv,.xlsx,.xlsm,text/csv"
          required
          class="w-full rounded-md border border-border px-3 py-2 text-sm text-text"
          @change="choisirFichier"
        />
        <p class="mt-1 text-xs text-text-muted">
          Sept colonnes par ligne : journal, date (AAAA-MM-JJ), pièce, compte, libellé, débit, crédit.
          Les lignes qui partagent le même journal + la même date + la même pièce forment une seule
          écriture ; l'exercice se déduit automatiquement de la date.
        </p>
      </div>
      <p v-if="erreurImport" class="text-sm text-danger">{{ erreurImport }}</p>
      <div class="flex justify-end gap-2">
        <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted" @click="importOuvert = false">
          Fermer
        </button>
        <button
          type="submit"
          :disabled="importer.isPending.value || !fichierImport"
          class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60"
        >
          {{ importer.isPending.value ? "Import en cours…" : "Importer" }}
        </button>
      </div>

      <div v-if="resultatImport" class="space-y-2 rounded-md border border-border bg-surface-muted p-3 text-sm">
        <p class="font-medium text-text">
          {{ resultatImport.ecritures_creees.length }} écriture(s) créée(s), {{ resultatImport.ignorees.length }} ignorée(s).
        </p>
        <ul v-if="resultatImport.ignorees.length > 0" class="max-h-40 space-y-1 overflow-y-auto text-xs text-text-muted">
          <li v-for="(i, index) in resultatImport.ignorees" :key="index">
            {{ i.journal }} / {{ i.date }} / {{ i.piece || "(pièce vide)" }} — {{ i.raison }}
          </li>
        </ul>
      </div>
    </form>

    <div class="flex gap-4">
      <select v-model="filtres.journalId" class="rounded-md border border-border px-3 py-2 text-sm text-text">
        <option :value="null">Tous les journaux</option>
        <option v-for="j in journaux" :key="j.id" :value="j.id">{{ j.code }} — {{ j.libelle }}</option>
      </select>
      <select v-model="filtres.exerciceId" class="rounded-md border border-border px-3 py-2 text-sm text-text">
        <option :value="null">Tous les exercices</option>
        <option v-for="e in exercices" :key="e.id" :value="e.id">{{ e.date_debut }} → {{ e.date_fin }}</option>
      </select>
      <select v-model="filtres.statut" class="rounded-md border border-border px-3 py-2 text-sm text-text">
        <option :value="null">Tous les statuts</option>
        <option value="brouillon">Brouillon</option>
        <option value="validee">Validée</option>
      </select>
    </div>

    <BaseDataTable
      :colonnes="colonnes"
      :lignes="ecritures ?? []"
      :chargement="isLoading"
      message-vide="Aucune écriture pour le moment."
      @ligne-cliquee="ouvrir"
    >
      <template #cell-numero="{ valeur }">{{ valeur ?? "—" }}</template>
      <template #cell-reference_piece="{ valeur }">{{ valeur ?? "—" }}</template>
      <template #cell-statut="{ valeur }">
        <StatutBadge
          :libelle="valeur === 'validee' ? 'Validée' : 'Brouillon'"
          :tonalite="valeur === 'validee' ? 'succes' : 'avertissement'"
        />
      </template>
    </BaseDataTable>
  </div>
</template>