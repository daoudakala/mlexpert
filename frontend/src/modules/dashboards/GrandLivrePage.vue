<script setup lang="ts">
/**
 * Grand livre : pour chaque compte, les écritures classées par date avec
 * journal, numéro de pièce, libellé, débit, crédit et solde cumulé.
 * Filtres : exercice, période, plage de comptes, journal ; export Excel avec
 * les mêmes filtres. Écritures validées uniquement, report à nouveau compris.
 */
import { computed, reactive, ref, watch } from "vue";

import { messageErreur } from "@/core/api/erreurs";
import { useAuth } from "@/core/auth/useAuth";
import { formaterMontant } from "@/core/ui/formatage";
import { useJournaux } from "@/modules/comptabilite/api";
import { useExercices } from "@/modules/exercices/api";
import { exporterGrandLivreGeneral, useGrandLivreGeneral, type FiltresGrandLivre } from "./api";

const { contexteActif, aPermission } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const { data: exercices } = useExercices(entrepriseId);
const exerciceId = ref<string | null>(null);
watch(exercices, (liste) => {
  if (exerciceId.value || !liste || liste.length === 0) return;
  exerciceId.value = liste[liste.length - 1].id;
});

// Liste des journaux pour le filtre (réservée à qui peut les consulter).
const { data: journaux } = useJournaux(
  computed(() => (aPermission("journal.consulter") ? entrepriseId.value : null)),
  computed(() => false),
);

// Les filtres saisis ne partent qu'au clic sur « Appliquer » (évite une
// requête à chaque frappe dans les champs de compte).
const saisie = reactive<FiltresGrandLivre>({
  dateDebut: null,
  dateFin: null,
  compteDebut: "",
  compteFin: "",
  journalId: null,
});
const filtres = ref<FiltresGrandLivre>({ ...saisie });

function appliquer(): void {
  filtres.value = { ...saisie };
}

function reinitialiser(): void {
  saisie.dateDebut = null;
  saisie.dateFin = null;
  saisie.compteDebut = "";
  saisie.compteFin = "";
  saisie.journalId = null;
  appliquer();
}

function surChangementExercice(): void {
  saisie.dateDebut = null;
  saisie.dateFin = null;
  appliquer();
}

const { data: grandLivre, isLoading, isError, error } = useGrandLivreGeneral(
  entrepriseId,
  exerciceId,
  filtres,
);

function montant(valeur: string | number): string {
  return Number(valeur) === 0 ? "" : formaterMontant(valeur);
}

// Solde cumulé (débit − crédit) en deux colonnes, comme dans le modèle.
function soldeDebit(solde: string): string {
  return Number(solde) > 0 ? formaterMontant(solde) : "";
}
function soldeCredit(solde: string): string {
  return Number(solde) < 0 ? formaterMontant(-Number(solde)) : "";
}

function dateAffichee(iso: string): string {
  const [a, m, j] = iso.split("-");
  return `${j}/${m}/${a}`;
}

const exportEnCours = ref(false);
const erreurExport = ref<string | null>(null);

async function exporter(): Promise<void> {
  if (!exerciceId.value) return;
  exportEnCours.value = true;
  erreurExport.value = null;
  try {
    await exporterGrandLivreGeneral(entrepriseId, exerciceId.value, filtres.value);
  } catch (e) {
    erreurExport.value = messageErreur(e);
  } finally {
    exportEnCours.value = false;
  }
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 class="text-lg font-semibold text-text">Grand livre</h1>
        <p v-if="grandLivre" class="text-xs text-text-muted">
          Du {{ dateAffichee(grandLivre.date_debut) }} au {{ dateAffichee(grandLivre.date_fin) }} — écritures
          validées uniquement
        </p>
      </div>
      <button
        type="button"
        class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60"
        :disabled="!grandLivre || exportEnCours"
        @click="exporter"
      >
        {{ exportEnCours ? "Export en cours…" : "Exporter (Excel)" }}
      </button>
    </div>

    <!-- Filtres -->
    <form
      class="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-surface p-4"
      @submit.prevent="appliquer"
    >
      <div>
        <label class="mb-1 block text-xs text-text-muted">Exercice</label>
        <select
          v-model="exerciceId"
          class="rounded-md border border-border px-3 py-1.5 text-sm text-text"
          @change="surChangementExercice"
        >
          <option v-for="e in exercices" :key="e.id" :value="e.id">
            {{ dateAffichee(e.date_debut) }} → {{ dateAffichee(e.date_fin) }}
          </option>
        </select>
      </div>
      <div>
        <label class="mb-1 block text-xs text-text-muted">Du compte</label>
        <input
          v-model="saisie.compteDebut"
          placeholder="ex. 411"
          class="w-28 rounded-md border border-border px-3 py-1.5 text-sm text-text"
        />
      </div>
      <div>
        <label class="mb-1 block text-xs text-text-muted">Au compte</label>
        <input
          v-model="saisie.compteFin"
          placeholder="ex. 411"
          class="w-28 rounded-md border border-border px-3 py-1.5 text-sm text-text"
        />
      </div>
      <div v-if="aPermission('journal.consulter')">
        <label class="mb-1 block text-xs text-text-muted">Journal</label>
        <select v-model="saisie.journalId" class="rounded-md border border-border px-3 py-1.5 text-sm text-text">
          <option :value="null">Tous les journaux</option>
          <option v-for="j in journaux" :key="j.id" :value="j.id">{{ j.code }} — {{ j.libelle }}</option>
        </select>
      </div>
      <div>
        <label class="mb-1 block text-xs text-text-muted">Du</label>
        <input v-model="saisie.dateDebut" type="date" class="rounded-md border border-border px-3 py-1.5 text-sm text-text" />
      </div>
      <div>
        <label class="mb-1 block text-xs text-text-muted">Au</label>
        <input v-model="saisie.dateFin" type="date" class="rounded-md border border-border px-3 py-1.5 text-sm text-text" />
      </div>
      <button
        type="submit"
        class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover"
      >
        Appliquer
      </button>
      <button
        type="button"
        class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted"
        @click="reinitialiser"
      >
        Réinitialiser
      </button>
    </form>

    <p v-if="erreurExport" class="text-sm text-danger">{{ erreurExport }}</p>
    <p v-if="isLoading" class="text-sm text-text-muted">Chargement…</p>
    <p v-else-if="isError" class="text-sm text-danger">{{ messageErreur(error) }}</p>

    <template v-else-if="grandLivre">
      <p
        v-if="grandLivre.comptes.length === 0"
        class="rounded-lg border border-border bg-surface p-6 text-center text-sm text-text-muted"
      >
        Aucune écriture pour ces filtres.
      </p>

      <div
        v-for="c in grandLivre.comptes"
        :key="c.compte_id"
        class="overflow-x-auto rounded-lg border border-border bg-surface"
      >
        <div class="border-b border-border bg-surface-muted px-3 py-2 text-sm font-semibold text-text">
          Compte {{ c.numero }} — {{ c.libelle }}
        </div>
        <table class="w-full min-w-[900px] text-sm">
          <thead class="text-xs font-medium uppercase text-text-muted">
            <tr class="border-b border-border">
              <th class="px-3 py-2 text-left">Journal</th>
              <th class="px-3 py-2 text-left">Date</th>
              <th class="px-3 py-2 text-left">N° de pièce</th>
              <th class="px-3 py-2 text-left">Libellé</th>
              <th class="px-3 py-2 text-right">Débit</th>
              <th class="px-3 py-2 text-right">Crédit</th>
              <th class="px-3 py-2 text-right">Solde débit</th>
              <th class="px-3 py-2 text-right">Solde crédit</th>
              <th class="px-3 py-2 text-left">Lettrage</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border text-text">
            <tr v-if="Number(c.solde_anterieur) !== 0" class="italic text-text-muted">
              <td class="px-3 py-1.5" colspan="6">Solde antérieur à la période</td>
              <td class="px-3 py-1.5 text-right tabular-nums">{{ soldeDebit(c.solde_anterieur) }}</td>
              <td class="px-3 py-1.5 text-right tabular-nums">{{ soldeCredit(c.solde_anterieur) }}</td>
              <td />
            </tr>
            <tr v-for="l in c.lignes" :key="l.ligne_ecriture_id">
              <td class="px-3 py-1.5">{{ l.code_journal }}</td>
              <td class="px-3 py-1.5 whitespace-nowrap">{{ dateAffichee(l.date_ecriture) }}</td>
              <td class="px-3 py-1.5 whitespace-nowrap">
                <router-link
                  v-if="aPermission('ecriture.consulter')"
                  :to="{ name: 'comptabilite.ecriture', params: { id: l.ecriture_id } }"
                  class="text-primary hover:underline"
                >
                  {{ l.numero_piece ?? "—" }}
                </router-link>
                <span v-else>{{ l.numero_piece ?? "—" }}</span>
              </td>
              <td class="px-3 py-1.5">{{ l.libelle }}</td>
              <td class="px-3 py-1.5 text-right tabular-nums">{{ montant(l.debit) }}</td>
              <td class="px-3 py-1.5 text-right tabular-nums">{{ montant(l.credit) }}</td>
              <td class="px-3 py-1.5 text-right tabular-nums">{{ soldeDebit(l.solde_progressif) }}</td>
              <td class="px-3 py-1.5 text-right tabular-nums">{{ soldeCredit(l.solde_progressif) }}</td>
              <td class="px-3 py-1.5">{{ l.code_lettrage ?? "" }}</td>
            </tr>
          </tbody>
          <tfoot class="bg-surface-muted font-semibold text-text">
            <tr class="border-t border-border">
              <td class="px-3 py-2" colspan="4">Total compte {{ c.numero }}</td>
              <td class="px-3 py-2 text-right tabular-nums">{{ montant(c.total_debit) }}</td>
              <td class="px-3 py-2 text-right tabular-nums">{{ montant(c.total_credit) }}</td>
              <td class="px-3 py-2 text-right tabular-nums">{{ soldeDebit(c.solde_final) }}</td>
              <td class="px-3 py-2 text-right tabular-nums">{{ soldeCredit(c.solde_final) }}</td>
              <td />
            </tr>
          </tfoot>
        </table>
      </div>

      <div
        v-if="grandLivre.comptes.length > 0"
        class="flex justify-end gap-6 rounded-lg border border-border bg-surface px-4 py-3 text-sm font-semibold text-text"
      >
        <span>Total général</span>
        <span class="tabular-nums">Débit : {{ formaterMontant(grandLivre.total_debit) }}</span>
        <span class="tabular-nums">Crédit : {{ formaterMontant(grandLivre.total_credit) }}</span>
      </div>
    </template>
  </div>
</template>