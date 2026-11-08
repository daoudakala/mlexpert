<script setup lang="ts">
/**
 * Périodes d'un exercice — permissions `periode.*`. Accessible depuis
 * ExercicesListe (clic sur une ligne).
 */
import { computed, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useAuth } from "@/core/auth/useAuth";
import { messageErreur } from "@/core/api/erreurs";
import BaseDataTable, { type ColonneTable } from "@/core/ui/BaseDataTable.vue";
import BaseFormulaire from "@/core/ui/BaseFormulaire.vue";
import StatutBadge from "@/core/ui/StatutBadge.vue";
import { useExercice, usePeriodes, useMutationsPeriodes } from "./api";
import type { Periode } from "./types";

const route = useRoute();
const router = useRouter();
const { contexteActif, aPermission } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);
const exerciceId = computed(() => route.params.id as string);

const { data: exercice } = useExercice(entrepriseId, exerciceId);
const { data: periodes, isLoading } = usePeriodes(entrepriseId, exerciceId);
const { creer, cloturer, reouvrir } = useMutationsPeriodes(entrepriseId, exerciceId);

const colonnes: ColonneTable<Periode>[] = [
  { cle: "libelle", libelle: "Libellé" },
  { cle: "date_debut", libelle: "Début" },
  { cle: "date_fin", libelle: "Fin" },
  { cle: "statut", libelle: "Statut" },
];

const afficherFormulaireCreation = ref(false);
const formulaire = reactive({ libelle: "", date_debut: "", date_fin: "" });
const erreurCreation = ref<string | null>(null);

async function soumettreCreation(): Promise<void> {
  erreurCreation.value = null;
  try {
    await creer.mutateAsync({
      libelle: formulaire.libelle || null,
      date_debut: formulaire.date_debut,
      date_fin: formulaire.date_fin,
    });
    formulaire.libelle = "";
    formulaire.date_debut = "";
    formulaire.date_fin = "";
    afficherFormulaireCreation.value = false;
  } catch (e) {
    erreurCreation.value = messageErreur(e);
  }
}

async function cloturerPeriode(p: Periode): Promise<void> {
  await cloturer.mutateAsync(p.id);
}

async function reouvrirPeriode(p: Periode): Promise<void> {
  await reouvrir.mutateAsync(p.id);
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <div>
        <button type="button" class="text-sm text-primary hover:underline" @click="router.push({ name: 'exercices.liste' })">
          ← Retour aux exercices
        </button>
        <h1 class="mt-1 text-lg font-semibold text-text">
          Périodes — exercice {{ exercice?.date_debut }} / {{ exercice?.date_fin }}
        </h1>
      </div>
      <button
        v-if="aPermission('periode.creer')"
        type="button"
        class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover"
        @click="afficherFormulaireCreation = !afficherFormulaireCreation"
      >
        Nouvelle période
      </button>
    </div>

    <BaseFormulaire
      v-if="afficherFormulaireCreation"
      titre="Créer une période"
      libelle-enregistrer="Créer"
      :erreur="erreurCreation"
      :en-envoi="creer.isPending.value"
      @soumettre="soumettreCreation"
      @annuler="afficherFormulaireCreation = false"
    >
      <div>
        <label class="mb-1 block text-sm font-medium text-text">Libellé</label>
        <input v-model="formulaire.libelle" maxlength="50" class="w-full rounded-md border border-border px-3 py-2 text-text" />
      </div>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Date de début</label>
          <input v-model="formulaire.date_debut" type="date" required class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Date de fin</label>
          <input v-model="formulaire.date_fin" type="date" required class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
      </div>
    </BaseFormulaire>

    <BaseDataTable :colonnes="colonnes" :lignes="periodes ?? []" :chargement="isLoading" message-vide="Aucune période pour le moment.">
      <template #cell-statut="{ ligne, valeur }">
        <div class="flex items-center justify-between gap-2">
          <StatutBadge
            :libelle="valeur === 'ouverte' ? 'Ouverte' : 'Clôturée'"
            :tonalite="valeur === 'ouverte' ? 'succes' : 'neutre'"
          />
          <div class="flex gap-2">
            <button
              v-if="ligne.statut === 'ouverte' && aPermission('periode.valider')"
              type="button"
              class="text-xs text-danger hover:underline"
              @click.stop="cloturerPeriode(ligne)"
            >
              Clôturer
            </button>
            <button
              v-if="ligne.statut === 'cloturee' && aPermission('periode.annuler')"
              type="button"
              class="text-xs text-primary hover:underline"
              @click.stop="reouvrirPeriode(ligne)"
            >
              Rouvrir
            </button>
          </div>
        </div>
      </template>
    </BaseDataTable>
  </div>
</template>
