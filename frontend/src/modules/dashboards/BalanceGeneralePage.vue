<script setup lang="ts">
/**
 * Balance générale à colonnes : pour chaque compte, les à-nouveaux, les
 * mouvements et le solde à la date choisie, puis les totaux des comptes de
 * bilan, des comptes de gestion et de la balance. Filtres : exercice,
 * période, classe de comptes ; export Excel avec les mêmes filtres.
 * Écritures validées uniquement.
 */
import { computed, ref, watch } from "vue";

import { messageErreur } from "@/core/api/erreurs";
import { useAuth } from "@/core/auth/useAuth";
import { formaterMontant } from "@/core/ui/formatage";
import { useExercices } from "@/modules/exercices/api";
import { exporterBalanceDetaillee, useBalanceDetaillee } from "./api";
import type { TotauxBalance } from "./types";

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
const classe = ref<string | null>(null);

// Changer d'exercice remet la période à l'exercice entier.
function surChangementExercice(): void {
  dateDebut.value = null;
  dateFin.value = null;
}

function reinitialiser(): void {
  dateDebut.value = null;
  dateFin.value = null;
  classe.value = null;
}

const { data: balance, isLoading, isError, error } = useBalanceDetaillee(
  entrepriseId,
  exerciceId,
  dateDebut,
  dateFin,
  classe,
);

const CLASSES: { valeur: string; libelle: string }[] = [
  { valeur: "1", libelle: "Classe 1 — Ressources durables" },
  { valeur: "2", libelle: "Classe 2 — Actif immobilisé" },
  { valeur: "3", libelle: "Classe 3 — Stocks" },
  { valeur: "4", libelle: "Classe 4 — Tiers" },
  { valeur: "5", libelle: "Classe 5 — Trésorerie" },
  { valeur: "6", libelle: "Classe 6 — Charges" },
  { valeur: "7", libelle: "Classe 7 — Produits" },
  { valeur: "8", libelle: "Classe 8 — Autres charges et produits (HAO)" },
  { valeur: "9", libelle: "Classe 9 — Engagements hors bilan et analytique" },
];

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

const totaux = computed<{ libelle: string; valeurs: TotauxBalance; avecSolde: boolean }[]>(() => {
  if (!balance.value) return [];
  return [
    { libelle: "Totaux comptes de bilan", valeurs: balance.value.totaux_bilan, avecSolde: true },
    { libelle: "Totaux comptes de gestion", valeurs: balance.value.totaux_gestion, avecSolde: true },
    // Comme dans le modèle : la ligne de la balance ne reprend que les
    // à-nouveaux et les mouvements (les soldes sont déjà dans les 2 lignes
    // ci-dessus).
    { libelle: "Totaux de la balance", valeurs: balance.value.totaux_balance, avecSolde: false },
  ];
});

const exportEnCours = ref(false);
const erreurExport = ref<string | null>(null);

async function exporter(): Promise<void> {
  if (!exerciceId.value) return;
  exportEnCours.value = true;
  erreurExport.value = null;
  try {
    await exporterBalanceDetaillee(
      entrepriseId,
      exerciceId.value,
      dateDebut.value,
      dateFin.value,
      classe.value,
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
        <h1 class="text-lg font-semibold text-text">Balance générale</h1>
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

    <!-- Filtres -->
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
        <label class="mb-1 block text-xs text-text-muted">Classe de comptes</label>
        <select v-model="classe" class="rounded-md border border-border px-3 py-1.5 text-sm text-text">
          <option :value="null">Toutes les classes</option>
          <option v-for="c in CLASSES" :key="c.valeur" :value="c.valeur">{{ c.libelle }}</option>
        </select>
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
      <p
        class="rounded-md px-3 py-2 text-sm"
        :class="balance.equilibree ? 'bg-success-bg text-success' : 'bg-danger-bg text-danger'"
      >
        {{
          balance.equilibree
            ? "Balance équilibrée : total débit = total crédit."
            : classe
              ? "Une seule classe est affichée : l'équilibre se contrôle toutes classes confondues."
              : "Balance déséquilibrée : total débit ≠ total crédit."
        }}
      </p>

      <div class="overflow-x-auto rounded-lg border border-border bg-surface">
        <table class="w-full min-w-[900px] text-sm">
          <thead class="bg-surface-muted text-xs font-medium uppercase text-text-muted">
            <tr>
              <th rowspan="2" class="px-3 py-2 text-left">N° de compte</th>
              <th rowspan="2" class="px-3 py-2 text-left">Intitulé des comptes</th>
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
          <tbody class="divide-y divide-border text-text">
            <tr v-if="balance.lignes.length === 0">
              <td colspan="8" class="px-3 py-6 text-center text-text-muted">
                Aucun mouvement sur cette période.
              </td>
            </tr>
            <tr v-for="l in balance.lignes" :key="l.compte_id">
              <td class="px-3 py-1.5 font-mono text-xs">{{ l.numero }}</td>
              <td class="px-3 py-1.5">{{ l.libelle }}</td>
              <td class="border-l border-border px-3 py-1.5 text-right tabular-nums">{{ montant(l.a_nouveau_debit) }}</td>
              <td class="px-3 py-1.5 text-right tabular-nums">{{ montant(l.a_nouveau_credit) }}</td>
              <td class="border-l border-border px-3 py-1.5 text-right tabular-nums">{{ montant(l.mouvement_debit) }}</td>
              <td class="px-3 py-1.5 text-right tabular-nums">{{ montant(l.mouvement_credit) }}</td>
              <td class="border-l border-border px-3 py-1.5 text-right tabular-nums">{{ montant(l.solde_debit) }}</td>
              <td class="px-3 py-1.5 text-right tabular-nums">{{ montant(l.solde_credit) }}</td>
            </tr>
          </tbody>
          <tfoot class="bg-surface-muted font-semibold text-text">
            <tr v-for="t in totaux" :key="t.libelle" class="border-t border-border">
              <td class="px-3 py-2" />
              <td class="px-3 py-2">{{ t.libelle }}</td>
              <td class="border-l border-border px-3 py-2 text-right tabular-nums">{{ montant(t.valeurs.a_nouveau_debit) }}</td>
              <td class="px-3 py-2 text-right tabular-nums">{{ montant(t.valeurs.a_nouveau_credit) }}</td>
              <td class="border-l border-border px-3 py-2 text-right tabular-nums">{{ montant(t.valeurs.mouvement_debit) }}</td>
              <td class="px-3 py-2 text-right tabular-nums">{{ montant(t.valeurs.mouvement_credit) }}</td>
              <td class="border-l border-border px-3 py-2 text-right tabular-nums">
                {{ t.avecSolde ? montant(t.valeurs.solde_debit) : "" }}
              </td>
              <td class="px-3 py-2 text-right tabular-nums">
                {{ t.avecSolde ? montant(t.valeurs.solde_credit) : "" }}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </template>
  </div>
</template>