<script setup lang="ts">
/**
 * Exercices de l'entreprise active — permissions `exercice.*` (convention
 * cahier section 6 : `valider` = clôturer, `annuler` = rouvrir).
 */
import { computed, reactive, ref } from "vue";
import { useRouter } from "vue-router";

import { useAuth } from "@/core/auth/useAuth";
import { messageErreur } from "@/core/api/erreurs";
import BaseDataTable, { type ColonneTable } from "@/core/ui/BaseDataTable.vue";
import BaseFormulaire from "@/core/ui/BaseFormulaire.vue";
import ConfirmDialog from "@/core/ui/ConfirmDialog.vue";
import StatutBadge from "@/core/ui/StatutBadge.vue";
import { useMutationGenererANouveaux } from "@/modules/comptabilite/api";
import { useExercices, useMutationsExercices } from "./api";
import type { Exercice } from "./types";

const router = useRouter();
const { contexteActif, aPermission } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const { data: exercices, isLoading } = useExercices(entrepriseId);
const { creer, cloturer, reouvrir } = useMutationsExercices(entrepriseId);
const genererANouveaux = useMutationGenererANouveaux(entrepriseId);
const erreurANouveaux = ref<string | null>(null);

async function genererANouveauxPour(e: Exercice): Promise<void> {
  erreurANouveaux.value = null;
  try {
    await genererANouveaux.mutateAsync(e.id);
  } catch (err) {
    erreurANouveaux.value = messageErreur(err);
  }
}

const colonnes: ColonneTable<Exercice>[] = [
  { cle: "date_debut", libelle: "Début" },
  { cle: "date_fin", libelle: "Fin" },
  { cle: "statut", libelle: "Statut" },
];

const afficherFormulaireCreation = ref(false);
const formulaire = reactive({ date_debut: "", date_fin: "" });
const erreurCreation = ref<string | null>(null);

async function soumettreCreation(): Promise<void> {
  erreurCreation.value = null;
  try {
    const dernierExercice = (exercices.value ?? [])[0];
    await creer.mutateAsync({
      date_debut: formulaire.date_debut,
      date_fin: formulaire.date_fin,
      exercice_precedent_id: dernierExercice?.id ?? null,
    });
    formulaire.date_debut = "";
    formulaire.date_fin = "";
    afficherFormulaireCreation.value = false;
  } catch (e) {
    erreurCreation.value = messageErreur(e);
  }
}

const exerciceCible = ref<Exercice | null>(null);
const confirmationCloture = ref(false);

function demanderCloture(e: Exercice): void {
  exerciceCible.value = e;
  confirmationCloture.value = true;
}

async function confirmerCloture(): Promise<void> {
  if (exerciceCible.value) await cloturer.mutateAsync(exerciceCible.value.id);
}

async function reouvrirExercice(e: Exercice): Promise<void> {
  await reouvrir.mutateAsync(e.id);
}

function ouvrirPeriodes(e: Exercice): void {
  router.push({ name: "exercices.detail", params: { id: e.id } });
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-lg font-semibold text-text">Exercices</h1>
      <button
        v-if="aPermission('exercice.creer')"
        type="button"
        class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover"
        @click="afficherFormulaireCreation = !afficherFormulaireCreation"
      >
        Nouvel exercice
      </button>
    </div>

    <BaseFormulaire
      v-if="afficherFormulaireCreation"
      titre="Créer un exercice"
      libelle-enregistrer="Créer"
      :erreur="erreurCreation"
      :en-envoi="creer.isPending.value"
      @soumettre="soumettreCreation"
      @annuler="afficherFormulaireCreation = false"
    >
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

    <p v-if="erreurANouveaux" class="text-sm text-danger">{{ erreurANouveaux }}</p>

    <BaseDataTable
      :colonnes="colonnes"
      :lignes="exercices ?? []"
      :chargement="isLoading"
      message-vide="Aucun exercice pour le moment."
      @ligne-cliquee="ouvrirPeriodes"
    >
      <template #cell-statut="{ ligne, valeur }">
        <div class="flex items-center justify-between gap-2">
          <StatutBadge
            :libelle="valeur === 'ouvert' ? 'Ouvert' : 'Clôturé'"
            :tonalite="valeur === 'ouvert' ? 'succes' : 'neutre'"
          />
          <div v-if="aPermission('exercice.valider') || aPermission('exercice.annuler')" class="flex gap-2">
            <button
              v-if="ligne.statut === 'ouvert' && aPermission('exercice.valider')"
              type="button"
              class="text-xs text-danger hover:underline"
              @click.stop="demanderCloture(ligne)"
            >
              Clôturer
            </button>
            <button
              v-if="ligne.statut === 'cloture' && aPermission('exercice.annuler')"
              type="button"
              class="text-xs text-primary hover:underline"
              @click.stop="reouvrirExercice(ligne)"
            >
              Rouvrir
            </button>
            <button
              v-if="ligne.statut === 'ouvert' && ligne.exercice_precedent_id && aPermission('ecriture.creer')"
              type="button"
              class="text-xs text-primary hover:underline"
              @click.stop="genererANouveauxPour(ligne)"
            >
              Générer les à-nouveaux
            </button>
          </div>
        </div>
      </template>
    </BaseDataTable>

    <ConfirmDialog
      v-model:ouvert="confirmationCloture"
      titre="Clôturer cet exercice ?"
      message="Plus aucune écriture ne pourra y être enregistrée tant qu'il n'est pas rouvert."
      libelle-confirmer="Clôturer"
      dangereux
      @confirmer="confirmerCloture"
    />
  </div>
</template>
