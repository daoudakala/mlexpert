<script setup lang="ts">
/**
 * Journaux de l'entreprise : création et désactivation seulement (pas de
 * modification côté backend), même limitation que ComptesListe.vue et le
 * module trésorerie.
 */
import { computed, reactive, ref } from "vue";

import { useAuth } from "@/core/auth/useAuth";
import { messageErreur } from "@/core/api/erreurs";
import BaseDataTable, { type ColonneTable } from "@/core/ui/BaseDataTable.vue";
import ConfirmDialog from "@/core/ui/ConfirmDialog.vue";
import StatutBadge from "@/core/ui/StatutBadge.vue";
import { useJournaux, useMutationsJournaux } from "./api";
import type { Journal, TypeJournal } from "./types";

const { contexteActif, aPermission } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const actifsSeulement = ref(false);
const { data: journaux, isLoading } = useJournaux(entrepriseId, actifsSeulement);
const { creer, desactiver } = useMutationsJournaux(entrepriseId);

const colonnes: ColonneTable<Journal>[] = [
  { cle: "code", libelle: "Code" },
  { cle: "libelle", libelle: "Libellé" },
  { cle: "type_journal", libelle: "Type" },
  { cle: "actif", libelle: "Statut" },
];

const typesJournal: { valeur: TypeJournal; libelle: string }[] = [
  { valeur: "achats", libelle: "Achats" },
  { valeur: "ventes", libelle: "Ventes" },
  { valeur: "banque", libelle: "Banque" },
  { valeur: "caisse", libelle: "Caisse" },
  { valeur: "operations_diverses", libelle: "Opérations diverses" },
];

const formulaireOuvert = ref(false);
const formulaire = reactive({ code: "", libelle: "", type_journal: "ventes" as TypeJournal });
const erreur = ref<string | null>(null);

async function soumettre(): Promise<void> {
  erreur.value = null;
  try {
    await creer.mutateAsync({ ...formulaire });
    formulaireOuvert.value = false;
    formulaire.code = "";
    formulaire.libelle = "";
    formulaire.type_journal = "ventes";
  } catch (e) {
    erreur.value = messageErreur(e);
  }
}

// Voir le commentaire équivalent dans ComptesListe.vue : deux refs
// distincts pour ne pas perdre la cible avant que "confirmer" ne soit émis.
const journalADesactiver = ref<Journal | null>(null);
const confirmationOuverte = ref(false);
function demanderDesactivation(journal: Journal): void {
  journalADesactiver.value = journal;
  confirmationOuverte.value = true;
}

async function confirmerDesactivation(): Promise<void> {
  if (!journalADesactiver.value) return;
  await desactiver.mutateAsync(journalADesactiver.value.id);
  journalADesactiver.value = null;
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-lg font-semibold text-text">Journaux</h1>
      <button
        v-if="aPermission('journal.creer')"
        type="button"
        class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover"
        @click="formulaireOuvert = !formulaireOuvert"
      >
        Nouveau journal
      </button>
    </div>

    <label class="flex items-center gap-2 text-sm text-text-muted">
      <input v-model="actifsSeulement" type="checkbox" />
      Actifs seulement
    </label>

    <form
      v-if="formulaireOuvert"
      class="space-y-4 rounded-lg border border-border bg-surface p-6"
      @submit.prevent="soumettre"
    >
      <div class="grid grid-cols-3 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Code</label>
          <input v-model="formulaire.code" required maxlength="20" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Libellé</label>
          <input v-model="formulaire.libelle" required minlength="2" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Type</label>
          <select v-model="formulaire.type_journal" class="w-full rounded-md border border-border px-3 py-2 text-text">
            <option v-for="t in typesJournal" :key="t.valeur" :value="t.valeur">{{ t.libelle }}</option>
          </select>
        </div>
      </div>
      <p v-if="erreur" class="text-sm text-danger">{{ erreur }}</p>
      <div class="flex justify-end gap-2">
        <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted" @click="formulaireOuvert = false">
          Annuler
        </button>
        <button type="submit" :disabled="creer.isPending.value" class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60">
          Créer
        </button>
      </div>
    </form>

    <BaseDataTable :colonnes="colonnes" :lignes="journaux ?? []" :chargement="isLoading" message-vide="Aucun journal.">
      <template #cell-actif="{ ligne }">
        <div class="flex items-center gap-2">
          <StatutBadge :libelle="ligne.actif ? 'Actif' : 'Désactivé'" :tonalite="ligne.actif ? 'succes' : 'neutre'" />
          <button
            v-if="ligne.actif && aPermission('journal.archiver')"
            type="button"
            class="text-xs text-danger hover:underline"
            @click="demanderDesactivation(ligne)"
          >
            Désactiver
          </button>
        </div>
      </template>
    </BaseDataTable>

    <ConfirmDialog
      v-model:ouvert="confirmationOuverte"
      titre="Désactiver ce journal ?"
      :message="`Le journal ${journalADesactiver?.code} n'apparaîtra plus dans les listes actives.`"
      libelle-confirmer="Désactiver"
      dangereux
      @confirmer="confirmerDesactivation"
    />
  </div>
</template>
