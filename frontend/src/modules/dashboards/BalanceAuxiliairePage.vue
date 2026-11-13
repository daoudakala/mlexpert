<script setup lang="ts">
/**
 * Balance auxiliaire : pour chaque compte collectif de tiers (40 fournisseurs,
 * 41 clients), une ligne par tiers avec à-nouveaux, mouvements et solde, puis
 * un sous-total par compte et un total général. Filtres : exercice, période,
 * rôle (client / fournisseur / tous), recherche par code ou nom ; export Excel
 * avec les mêmes filtres. Écritures validées uniquement.
 */
import { computed, ref, watch } from "vue";

import { messageErreur } from "@/core/api/erreurs";
import { useAuth } from "@/core/auth/useAuth";
import { formaterMontant } from "@/core/ui/formatage";
import { useExercices } from "@/modules/exercices/api";
import { exporterBalanceAuxiliaire, useBalanceAuxiliaire, type RoleBalanceAuxiliaire } from "./api";

const { contexteActif } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const { data: exercices } = useExercices(entrepriseId);
const exerciceId = ref<string | null>(null);
watch(exercices, (liste) => {
  if (exerciceId.value || !liste || liste.length === 0) return;
  exerciceId.value = liste[liste.length - 1].id;
});

const dateDebut = ref<string | null>(null);
const dateFin = ref<string | null>(null);
const role = ref<RoleBalanceAuxiliaire>("tous");
const rechercheSaisie = ref("");
const recherche = ref("");

// La recherche n'interroge le serveur qu'après une courte pause de frappe.
let minuteur: ReturnType<typeof setTimeout> | undefined;
watch(rechercheSaisie, (valeur) => {
  clearTimeout(minuteur);
  minuteur = setTimeout(() => (recherche.value = valeur), 300);
});

function surChangementExercice(): void {
  dateDebut.value = null;
  dateFin.value = null;
}

function reinitialiser(): void {
  dateDebut.value = null;
  dateFin.value = null;
  role.value = "tous";
  rechercheSaisie.value = "";
  recherche.value = "";
}

const { data: balance, isLoading, isError, error } = useBalanceAuxiliaire(
  entrepriseId,
  exerciceId,
  dateDebut,
  dateFin,
  role,
  recherche,
);

function montant(valeur: string): string {
  return Number(valeur) === 0 ? "" : formaterMontant(valeur);
}

function dateAffichee(iso: string): string {
  const [a, m, j] = iso.split("-");
  return `${j}/${m}/${a}`;
}

function libelleExercice(debut: string, fin: string): string {
  return `${dateAffichee(debut)} → ${dateAffichee(fin)}`;
}

const exportEnCours = ref(false);
const erreurExport = ref<string | null>(null);

async function exporter(): Promise<void> {
  if (!exerciceId.value) return;
  exportEnCours.value = true;
  erreurExport.value = null;
  try {
    await exporterBalanceAuxiliaire(
      entrepriseId,
      exerciceId.value,
      dateDebut.value,
      dateFin.value,
      role.value,
      recherche.value,
    );
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
        <h1 class="text-lg font-semibold text-text">Balance auxiliaire</h1>
        <p v-if="balance" class="text-xs text-text-muted">
          Du {{ dateAffichee(balance.date_debut) }} au {{ dateAffichee(balance.date_fin) }} — écritures validées
          uniquement
        </p>
      </div>
      <button
        type="button"
        class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60"
        :disabled="!balance || exportEnCours"
        @click="exporter"
      >
        {{ exportEnCours ? "Export en cours…" : "Exporter (Excel)" }}
      </button>
    </div>

    <div class="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-surface p-4">
      <div>
        <label class="mb-1 block text-xs text-text-muted">Exercice</label>
        <select
          v-model="exerciceId"
          class="rounded-md border border-border px-3 py-1.5 text-sm text-text"
          @change="surChangementExercice"
        >
          <option v-for="e in exercices" :key="e.id" :value="e.id">
            {{ libelleExercice(e.date_debut, e.date_fin) }}
          </option>
        </select>
      </div>
      <div>
        <label class="mb-1 block text-xs text-text-muted">Du</label>
        <input v-model="dateDebut" type="date" class="rounded-md border border-border px-3 py-1.5 text-sm text-text" />
      </div>
      <div>
        <label class="mb-1 block text-xs text-text-muted">Au</label>
        <input v-model="dateFin" type="date" class="rounded-md border border-border px-3 py-1.5 text-sm text-text" />
      </div>
      <div>
        <label class="mb-1 block text-xs text-text-muted">Tiers</label>
        <select v-model="role" class="rounded-md border border-border px-3 py-1.5 text-sm text-text">
          <option value="tous">Clients et fournisseurs</option>
          <option value="client">Clients (41)</option>
          <option value="fournisseur">Fournisseurs (40)</option>
        </select>
      </div>
      <div>
        <label class="mb-1 block text-xs text-text-muted">Recherche</label>
        <input
          v-model="rechercheSaisie"
          type="search"
          placeholder="Code ou nom du tiers"
          class="rounded-md border border-border px-3 py-1.5 text-sm text-text"
        />
      </div>
      <button
        type="button"
        class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted"
        @click="reinitialiser"
      >
        Réinitialiser
      </button>
    </div>

    <p v-if="erreurExport" class="text-sm text-danger">{{ erreurExport }}</p>
    <p v-if="isLoading" class="text-sm text-text-muted">Chargement…</p>
    <p v-else-if="isError" class="text-sm text-danger">{{ messageErreur(error) }}</p>

    <template v-else-if="balance">
      <div class="overflow-x-auto rounded-lg border border-border bg-surface">
        <table class="w-full min-w-[900px] text-sm">
          <thead class="bg-surface-muted text-xs font-medium uppercase text-text-muted">
            <tr>
              <th rowspan="2" class="px-3 py-2 text-left">Code</th>
              <th rowspan="2" class="px-3 py-2 text-left">Tiers</th>
              <th colspan="2" class="border-l border-border px-3 py-2 text-center">À nouveau</th>
              <th colspan="2" class="border-l border-border px-3 py-2 text-center">Mouvements</th>
              <th colspan="2" class="border-l border-border px-3 py-2 text-center">
                Solde au {{ dateAffichee(balance.date_fin) }}
              </th>
            </tr>
            <tr>
              <th class="border-l border-border px-3 py-1 text-right">Débit</th>
              <th class="px-3 py-1 text-right">Crédit</th>
              <th class="border-l border-border px-3 py-1 text-right">Débit</th>
              <th class="px-3 py-1 text-right">Crédit</th>
              <th class="border-l border-border px-3 py-1 text-right">Débit</th>
              <th class="px-3 py-1 text-right">Crédit</th>
            </tr>
          </thead>
          <tbody v-if="balance.groupes.length === 0" class="text-text">
            <tr>
              <td colspan="8" class="px-3 py-6 text-center text-text-muted">
                Aucun mouvement de tiers sur cette période.
              </td>
            </tr>
          </tbody>
          <tbody v-for="g in balance.groupes" :key="g.compte_id" class="divide-y divide-border text-text">
            <tr class="bg-surface-muted">
              <td colspan="8" class="px-3 py-1.5 text-xs font-semibold">
                <span class="font-mono">{{ g.numero }}</span> — {{ g.libelle }}
              </td>
            </tr>
            <tr v-for="l in g.lignes" :key="l.tiers_id ?? 'sans-tiers'">
              <td class="px-3 py-1.5 font-mono text-xs">{{ l.code }}</td>
              <td class="px-3 py-1.5" :class="l.tiers_id ? '' : 'italic text-text-muted'">{{ l.nom }}</td>
              <td class="border-l border-border px-3 py-1.5 text-right tabular-nums">{{ montant(l.a_nouveau_debit) }}</td>
              <td class="px-3 py-1.5 text-right tabular-nums">{{ montant(l.a_nouveau_credit) }}</td>
              <td class="border-l border-border px-3 py-1.5 text-right tabular-nums">{{ montant(l.mouvement_debit) }}</td>
              <td class="px-3 py-1.5 text-right tabular-nums">{{ montant(l.mouvement_credit) }}</td>
              <td class="border-l border-border px-3 py-1.5 text-right tabular-nums">{{ montant(l.solde_debit) }}</td>
              <td class="px-3 py-1.5 text-right tabular-nums">{{ montant(l.solde_credit) }}</td>
            </tr>
            <tr class="font-semibold">
              <td class="px-3 py-1.5" />
              <td class="px-3 py-1.5">Total {{ g.numero }}</td>
              <td class="border-l border-border px-3 py-1.5 text-right tabular-nums">{{ montant(g.totaux.a_nouveau_debit) }}</td>
              <td class="px-3 py-1.5 text-right tabular-nums">{{ montant(g.totaux.a_nouveau_credit) }}</td>
              <td class="border-l border-border px-3 py-1.5 text-right tabular-nums">{{ montant(g.totaux.mouvement_debit) }}</td>
              <td class="px-3 py-1.5 text-right tabular-nums">{{ montant(g.totaux.mouvement_credit) }}</td>
              <td class="border-l border-border px-3 py-1.5 text-right tabular-nums">{{ montant(g.totaux.solde_debit) }}</td>
              <td class="px-3 py-1.5 text-right tabular-nums">{{ montant(g.totaux.solde_credit) }}</td>
            </tr>
          </tbody>
          <tfoot v-if="balance.groupes.length" class="bg-surface-muted font-semibold text-text">
            <tr class="border-t border-border">
              <td class="px-3 py-2" />
              <td class="px-3 py-2">Total général</td>
              <td class="border-l border-border px-3 py-2 text-right tabular-nums">{{ montant(balance.totaux.a_nouveau_debit) }}</td>
              <td class="px-3 py-2 text-right tabular-nums">{{ montant(balance.totaux.a_nouveau_credit) }}</td>
              <td class="border-l border-border px-3 py-2 text-right tabular-nums">{{ montant(balance.totaux.mouvement_debit) }}</td>
              <td class="px-3 py-2 text-right tabular-nums">{{ montant(balance.totaux.mouvement_credit) }}</td>
              <td class="border-l border-border px-3 py-2 text-right tabular-nums">{{ montant(balance.totaux.solde_debit) }}</td>
              <td class="px-3 py-2 text-right tabular-nums">{{ montant(balance.totaux.solde_credit) }}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </template>
  </div>
</template>