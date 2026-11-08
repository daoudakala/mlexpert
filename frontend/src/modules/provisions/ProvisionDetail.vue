<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { useRoute } from "vue-router";

import { useAuth } from "@/core/auth/useAuth";
import { useComptesEntreprise, useJournaux } from "@/modules/comptabilite/api";
import { useExercices } from "@/modules/exercices/api";
import { useListeTiers } from "@/modules/tiers/api";
import { messageErreur } from "@/core/api/erreurs";
import BaseFormulaire from "@/core/ui/BaseFormulaire.vue";
import { formaterMontant } from "@/core/ui/formatage";
import MontantInput from "@/core/ui/MontantInput.vue";
import StatutBadge from "@/core/ui/StatutBadge.vue";
import { useMouvementsProvision, useMutationsProvisions, useProvision } from "./api";

const route = useRoute();
const { contexteActif, aPermission } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);
const provisionId = computed(() => route.params.id as string);

const { data: provision } = useProvision(entrepriseId, provisionId);
const { data: mouvements } = useMouvementsProvision(entrepriseId, provisionId);
const { data: comptes } = useComptesEntreprise(entrepriseId);
const { data: exercices } = useExercices(entrepriseId);
const { data: journaux } = useJournaux(entrepriseId);
const { data: clients } = useListeTiers(
  entrepriseId,
  computed(() => ({ actifsSeulement: true, clientSeulement: true })),
);

const { modifier, doter, reprendre } = useMutationsProvisions(entrepriseId);

function libelleCompte(id: string | null): string {
  if (!id) return "—";
  const c = comptes.value?.find((c) => c.id === id);
  return c ? `${c.numero} — ${c.libelle}` : id;
}

// --- Édition des champs descriptifs ---

const formulaireEdition = reactive({ libelle: "", tiers_id: "" });
const editionOuverte = ref(false);
watch(
  provision,
  (p) => {
    if (!p) return;
    formulaireEdition.libelle = p.libelle;
    formulaireEdition.tiers_id = p.tiers_id ?? "";
  },
  { immediate: true },
);
const erreurEdition = ref<string | null>(null);
async function enregistrerEdition(): Promise<void> {
  erreurEdition.value = null;
  try {
    await modifier.mutateAsync({
      id: provisionId.value,
      donnees: {
        libelle: formulaireEdition.libelle,
        tiers_id: formulaireEdition.tiers_id || null,
      },
    });
    editionOuverte.value = false;
  } catch (e) {
    erreurEdition.value = messageErreur(e);
  }
}

// --- Dotation ---

const dotationOuverte = ref(false);
const dotation = reactive({ exercice_id: "", journal_id: "", date_mouvement: "", montant: 0 as number });
const erreurDotation = ref<string | null>(null);
async function soumettreDotation(): Promise<void> {
  erreurDotation.value = null;
  try {
    await doter.mutateAsync({ id: provisionId.value, donnees: { ...dotation } });
    dotationOuverte.value = false;
    dotation.exercice_id = "";
    dotation.journal_id = "";
    dotation.date_mouvement = "";
    dotation.montant = 0;
  } catch (e) {
    erreurDotation.value = messageErreur(e);
  }
}

// --- Reprise ---

const repriseOuverte = ref(false);
const reprise = reactive({ exercice_id: "", journal_id: "", date_mouvement: "", montant: 0 as number });
const erreurReprise = ref<string | null>(null);
async function soumettreReprise(): Promise<void> {
  erreurReprise.value = null;
  try {
    await reprendre.mutateAsync({ id: provisionId.value, donnees: { ...reprise } });
    repriseOuverte.value = false;
    reprise.exercice_id = "";
    reprise.journal_id = "";
    reprise.date_mouvement = "";
    reprise.montant = 0;
  } catch (e) {
    erreurReprise.value = messageErreur(e);
  }
}

const libellesType: Record<string, string> = {
  depreciation_creance: "Dépréciation de créance",
  depreciation_stock: "Dépréciation de stock",
  risque_charge: "Risques et charges",
};
const libellesStatut: Record<string, string> = {
  active: "Active",
  soldee: "Soldée",
};
const tonalitesStatut: Record<string, "succes" | "neutre"> = {
  active: "succes",
  soldee: "neutre",
};
</script>

<template>
  <div v-if="provision" class="max-w-4xl space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-lg font-semibold text-text">{{ provision.libelle }}</h1>
      <StatutBadge :libelle="libellesStatut[provision.statut]" :tonalite="tonalitesStatut[provision.statut]" />
    </div>

    <div class="space-y-4 rounded-lg border border-border bg-surface p-6">
      <div class="flex items-center justify-between">
        <h2 class="text-base font-semibold text-text">Informations</h2>
        <button
          v-if="aPermission('provision.modifier') && !editionOuverte"
          type="button"
          class="text-sm text-primary hover:underline"
          @click="editionOuverte = true"
        >
          Modifier
        </button>
      </div>

      <form v-if="editionOuverte" class="space-y-4" @submit.prevent="enregistrerEdition">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Libellé</label>
          <input v-model="formulaireEdition.libelle" required minlength="2" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div v-if="provision.type_provision === 'depreciation_creance'">
          <label class="mb-1 block text-sm font-medium text-text">Client concerné</label>
          <select v-model="formulaireEdition.tiers_id" class="w-full rounded-md border border-border px-3 py-2 text-text">
            <option value="">— Aucun —</option>
            <option v-for="t in clients" :key="t.id" :value="t.id">{{ t.code }} — {{ t.raison_sociale }}</option>
          </select>
        </div>
        <p v-if="erreurEdition" class="text-sm text-danger">{{ erreurEdition }}</p>
        <div class="flex justify-end gap-2">
          <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted" @click="editionOuverte = false">
            Annuler
          </button>
          <button type="submit" :disabled="modifier.isPending.value" class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60">
            Enregistrer
          </button>
        </div>
      </form>

      <div v-else class="grid grid-cols-2 gap-4 text-sm">
        <div><p class="text-text-muted">Type</p><p class="text-text">{{ libellesType[provision.type_provision] }}</p></div>
        <div><p class="text-text-muted">Montant actuel</p><p class="text-text">{{ formaterMontant(provision.montant_actuel) }}</p></div>
        <div v-if="provision.tiers_id"><p class="text-text-muted">Client concerné</p><p class="text-text">{{ clients?.find((t) => t.id === provision.tiers_id)?.raison_sociale ?? "—" }}</p></div>
        <div><p class="text-text-muted">Compte de dotation</p><p class="text-text">{{ libelleCompte(provision.compte_dotation_id) }}</p></div>
        <div><p class="text-text-muted">Compte de provision</p><p class="text-text">{{ libelleCompte(provision.compte_provision_id) }}</p></div>
        <div><p class="text-text-muted">Compte de reprise</p><p class="text-text">{{ libelleCompte(provision.compte_reprise_id) }}</p></div>
      </div>
    </div>

    <div v-if="aPermission('provision.valider')" class="flex gap-2">
      <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted" @click="dotationOuverte = !dotationOuverte">
        Doter
      </button>
      <button
        type="button"
        :disabled="Number(provision.montant_actuel) <= 0"
        class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted disabled:opacity-60"
        @click="repriseOuverte = !repriseOuverte"
      >
        Reprendre
      </button>
    </div>

    <form v-if="dotationOuverte" class="space-y-4 rounded-lg border border-border bg-surface p-6" @submit.prevent="soumettreDotation">
      <h2 class="text-base font-semibold text-text">Constituer une dotation</h2>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Exercice</label>
          <select v-model="dotation.exercice_id" required class="w-full rounded-md border border-border px-3 py-2 text-text">
            <option value="" disabled>— Choisir —</option>
            <option v-for="e in exercices" :key="e.id" :value="e.id">{{ e.date_debut }} → {{ e.date_fin }}</option>
          </select>
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Journal</label>
          <select v-model="dotation.journal_id" required class="w-full rounded-md border border-border px-3 py-2 text-text">
            <option value="" disabled>— Choisir —</option>
            <option v-for="j in journaux" :key="j.id" :value="j.id">{{ j.code }} — {{ j.libelle }}</option>
          </select>
        </div>
      </div>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Date</label>
          <input v-model="dotation.date_mouvement" type="date" required class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Montant</label>
          <MontantInput v-model="dotation.montant" required />
        </div>
      </div>
      <p v-if="erreurDotation" class="text-sm text-danger">{{ erreurDotation }}</p>
      <div class="flex justify-end gap-2">
        <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted" @click="dotationOuverte = false">Annuler</button>
        <button type="submit" :disabled="doter.isPending.value" class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60">Doter</button>
      </div>
    </form>

    <form v-if="repriseOuverte" class="space-y-4 rounded-lg border border-border bg-surface p-6" @submit.prevent="soumettreReprise">
      <h2 class="text-base font-semibold text-text">Reprendre la provision</h2>
      <p class="text-sm text-text-muted">Montant actuel disponible : {{ formaterMontant(provision.montant_actuel) }}</p>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Exercice</label>
          <select v-model="reprise.exercice_id" required class="w-full rounded-md border border-border px-3 py-2 text-text">
            <option value="" disabled>— Choisir —</option>
            <option v-for="e in exercices" :key="e.id" :value="e.id">{{ e.date_debut }} → {{ e.date_fin }}</option>
          </select>
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Journal</label>
          <select v-model="reprise.journal_id" required class="w-full rounded-md border border-border px-3 py-2 text-text">
            <option value="" disabled>— Choisir —</option>
            <option v-for="j in journaux" :key="j.id" :value="j.id">{{ j.code }} — {{ j.libelle }}</option>
          </select>
        </div>
      </div>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Date</label>
          <input v-model="reprise.date_mouvement" type="date" required class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Montant</label>
          <MontantInput v-model="reprise.montant" required />
        </div>
      </div>
      <p v-if="erreurReprise" class="text-sm text-danger">{{ erreurReprise }}</p>
      <div class="flex justify-end gap-2">
        <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted" @click="repriseOuverte = false">Annuler</button>
        <button type="submit" :disabled="reprendre.isPending.value" class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60">Reprendre</button>
      </div>
    </form>

    <div class="space-y-3">
      <h2 class="text-base font-semibold text-text">Historique des mouvements</h2>
      <div class="overflow-hidden rounded-lg border border-border bg-surface">
        <table class="w-full text-sm">
          <thead class="bg-surface-muted text-left text-xs font-medium uppercase text-text-muted">
            <tr>
              <th class="px-3 py-2">Date</th>
              <th class="px-3 py-2">Exercice</th>
              <th class="px-3 py-2">Type</th>
              <th class="px-3 py-2 text-right">Montant</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            <tr v-if="!mouvements || mouvements.length === 0">
              <td colspan="4" class="px-3 py-6 text-center text-text-muted">Aucun mouvement pour le moment.</td>
            </tr>
            <tr v-for="m in mouvements" v-else :key="m.id">
              <td class="px-3 py-2 text-text">{{ m.date_mouvement }}</td>
              <td class="px-3 py-2 text-text">{{ exercices?.find((e) => e.id === m.exercice_id)?.date_debut }}</td>
              <td class="px-3 py-2">
                <StatutBadge
                  :libelle="m.type_mouvement === 'dotation' ? 'Dotation' : 'Reprise'"
                  :tonalite="m.type_mouvement === 'dotation' ? 'avertissement' : 'info'"
                />
              </td>
              <td class="px-3 py-2 text-right text-text">{{ formaterMontant(m.montant) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>