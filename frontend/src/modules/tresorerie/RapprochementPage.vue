<script setup lang="ts">
/**
 * Rapprochement bancaire : on sélectionne des lignes de relevé non
 * rapprochées d'un côté et des lignes d'écriture candidates de l'autre
 * (même mécanisme de lettrage que comptabilite/tiers — un même
 * code_lettrage écrit sur les deux), puis on envoie la sélection à
 * POST .../rapprocher. L'annulation ne dispose pas d'un endpoint qui liste
 * les groupes déjà lettrés : on demande le code de lettrage directement
 * (affiché après chaque rapprochement réussi, donc disponible à l'écran).
 */
import { computed, ref } from "vue";
import { useRoute } from "vue-router";

import { useAuth } from "@/core/auth/useAuth";
import { messageErreur } from "@/core/api/erreurs";
import { formaterMontant } from "@/core/ui/formatage";
import {
  useEcrituresCandidates,
  useLignesNonRapprochees,
  useMutationsRapprochement,
} from "./api";

const route = useRoute();
const { contexteActif } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);
const compteBancaireId = computed(() => route.params.id as string);

const { data: lignesReleve, isLoading: chargementReleve } = useLignesNonRapprochees(
  entrepriseId,
  compteBancaireId,
);
const { data: ecritures, isLoading: chargementEcritures } = useEcrituresCandidates(
  entrepriseId,
  compteBancaireId,
);
const { rapprocher, annuler } = useMutationsRapprochement(entrepriseId);

const lignesSelectionnees = ref<Set<string>>(new Set());
const ecrituresSelectionnees = ref<Set<string>>(new Set());

function basculer(ensemble: Set<string>, id: string): void {
  if (ensemble.has(id)) ensemble.delete(id);
  else ensemble.add(id);
}

const totalLignes = computed(() =>
  (lignesReleve.value ?? [])
    .filter((l) => lignesSelectionnees.value.has(l.id))
    .reduce((s, l) => s + Number(l.credit) - Number(l.debit), 0),
);
const totalEcritures = computed(() =>
  (ecritures.value ?? [])
    .filter((l) => ecrituresSelectionnees.value.has(l.id))
    .reduce((s, l) => s + Number(l.debit) - Number(l.credit), 0),
);
const equilibre = computed(
  () =>
    lignesSelectionnees.value.size > 0 &&
    ecrituresSelectionnees.value.size > 0 &&
    Math.abs(totalLignes.value - totalEcritures.value) < 0.005,
);

const erreur = ref<string | null>(null);
const dernierCodeLettrage = ref<string | null>(null);

async function soumettreRapprochement(): Promise<void> {
  erreur.value = null;
  try {
    const reponse = await rapprocher.mutateAsync({
      compteBancaireId: compteBancaireId.value,
      donnees: {
        ligne_releve_ids: [...lignesSelectionnees.value],
        ligne_ecriture_ids: [...ecrituresSelectionnees.value],
      },
    });
    dernierCodeLettrage.value = reponse.code_lettrage;
    lignesSelectionnees.value = new Set();
    ecrituresSelectionnees.value = new Set();
  } catch (e) {
    erreur.value = messageErreur(e);
  }
}

const codeLettrageAAnnuler = ref("");
const erreurAnnulation = ref<string | null>(null);

async function soumettreAnnulation(): Promise<void> {
  erreurAnnulation.value = null;
  try {
    await annuler.mutateAsync({ code_lettrage: codeLettrageAAnnuler.value });
    codeLettrageAAnnuler.value = "";
  } catch (e) {
    erreurAnnulation.value = messageErreur(e);
  }
}
</script>

<template>
  <div class="space-y-6">
    <h1 class="text-lg font-semibold text-text">Rapprochement bancaire</h1>

    <p v-if="dernierCodeLettrage" class="rounded-md border border-success bg-success-bg p-3 text-sm text-text">
      Rapprochement effectué — code de lettrage : <strong>{{ dernierCodeLettrage }}</strong>
    </p>

    <div class="grid grid-cols-2 gap-6">
      <div class="space-y-2">
        <h2 class="text-sm font-semibold text-text">Lignes de relevé non rapprochées</h2>
        <div class="max-h-96 overflow-y-auto rounded-lg border border-border bg-surface">
          <table class="w-full text-sm">
            <tbody class="divide-y divide-border">
              <tr v-if="chargementReleve">
                <td class="px-4 py-6 text-center text-text-muted">Chargement...</td>
              </tr>
              <tr v-else-if="!lignesReleve || lignesReleve.length === 0">
                <td class="px-4 py-6 text-center text-text-muted">Rien à rapprocher.</td>
              </tr>
              <tr
                v-for="l in lignesReleve"
                v-else
                :key="l.id"
                class="cursor-pointer hover:bg-surface-muted"
                @click="basculer(lignesSelectionnees, l.id)"
              >
                <td class="px-3 py-2">
                  <input type="checkbox" :checked="lignesSelectionnees.has(l.id)" @click.stop="basculer(lignesSelectionnees, l.id)" />
                </td>
                <td class="px-2 py-2 text-text">{{ l.date_operation }}</td>
                <td class="px-2 py-2 text-text">{{ l.libelle }}</td>
                <td class="px-2 py-2 text-right text-text">
                  {{ Number(l.credit) > 0 ? `+${formaterMontant(l.credit)}` : `-${formaterMontant(l.debit)}` }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="text-xs text-text-muted">Total sélectionné : {{ formaterMontant(totalLignes) }}</p>
      </div>

      <div class="space-y-2">
        <h2 class="text-sm font-semibold text-text">Écritures candidates</h2>
        <div class="max-h-96 overflow-y-auto rounded-lg border border-border bg-surface">
          <table class="w-full text-sm">
            <tbody class="divide-y divide-border">
              <tr v-if="chargementEcritures">
                <td class="px-4 py-6 text-center text-text-muted">Chargement...</td>
              </tr>
              <tr v-else-if="!ecritures || ecritures.length === 0">
                <td class="px-4 py-6 text-center text-text-muted">Rien à rapprocher.</td>
              </tr>
              <tr
                v-for="l in ecritures"
                v-else
                :key="l.id"
                class="cursor-pointer hover:bg-surface-muted"
                @click="basculer(ecrituresSelectionnees, l.id)"
              >
                <td class="px-3 py-2">
                  <input type="checkbox" :checked="ecrituresSelectionnees.has(l.id)" @click.stop="basculer(ecrituresSelectionnees, l.id)" />
                </td>
                <td class="px-2 py-2 text-text">{{ l.libelle ?? "—" }}</td>
                <td class="px-2 py-2 text-right text-text">
                  {{ Number(l.debit) > 0 ? `+${formaterMontant(l.debit)}` : `-${formaterMontant(l.credit)}` }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="text-xs text-text-muted">Total sélectionné : {{ formaterMontant(totalEcritures) }}</p>
      </div>
    </div>

    <div class="rounded-lg border border-border bg-surface p-4">
      <p v-if="erreur" class="mb-2 text-sm text-danger">{{ erreur }}</p>
      <p v-else-if="lignesSelectionnees.size > 0 && ecrituresSelectionnees.size > 0 && !equilibre" class="mb-2 text-sm text-warning">
        Les totaux sélectionnés ne s'équilibrent pas ({{ formaterMontant(totalLignes) }} ≠ {{ formaterMontant(totalEcritures) }}).
      </p>
      <button
        type="button"
        :disabled="rapprocher.isPending.value || lignesSelectionnees.size === 0 || ecrituresSelectionnees.size === 0"
        class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60"
        @click="soumettreRapprochement"
      >
        {{ rapprocher.isPending.value ? "Rapprochement..." : "Rapprocher la sélection" }}
      </button>
    </div>

    <div class="rounded-lg border border-border bg-surface p-4">
      <h2 class="mb-2 text-sm font-semibold text-text">Annuler un rapprochement</h2>
      <div class="flex items-end gap-2">
        <div class="flex-1">
          <label class="mb-1 block text-xs font-medium text-text-muted">Code de lettrage</label>
          <input
            v-model="codeLettrageAAnnuler"
            class="w-full rounded-md border border-border px-3 py-2 text-sm text-text"
          />
        </div>
        <button
          type="button"
          :disabled="annuler.isPending.value || !codeLettrageAAnnuler"
          class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted disabled:opacity-60"
          @click="soumettreAnnulation"
        >
          Annuler
        </button>
      </div>
      <p v-if="erreurAnnulation" class="mt-2 text-sm text-danger">{{ erreurAnnulation }}</p>
    </div>
  </div>
</template>
