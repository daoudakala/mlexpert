<script setup lang="ts">
import { computed, ref } from "vue";
import { useRouter } from "vue-router";

import { useAuth } from "@/core/auth/useAuth";
import BaseDataTable, { type ColonneTable } from "@/core/ui/BaseDataTable.vue";
import { formaterMontant } from "@/core/ui/formatage";
import StatutBadge from "@/core/ui/StatutBadge.vue";
import { useAcquisitionsAConfirmer, useListeImmobilisations } from "./api";
import type { Immobilisation } from "./types";

const router = useRouter();
const { contexteActif, aPermission } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const statut = ref<string | null>(null);
const { data: immobilisations, isLoading } = useListeImmobilisations(entrepriseId, statut);
const { data: aConfirmer } = useAcquisitionsAConfirmer(entrepriseId);

const colonnes: ColonneTable<Immobilisation>[] = [
  { cle: "libelle", libelle: "Libellé" },
  { cle: "categorie", libelle: "Catégorie" },
  { cle: "valeur_origine", libelle: "Valeur d'origine" },
  { cle: "date_mise_en_service", libelle: "Mise en service" },
  { cle: "statut", libelle: "Statut" },
];

function ouvrir(ligne: Immobilisation): void {
  router.push({ name: "immobilisations.detail", params: { id: ligne.id } });
}

const libellesStatut: Record<string, string> = {
  en_service: "En service",
  cedee: "Cédée",
  reformee: "Réformée",
};
const tonalitesStatut: Record<string, "succes" | "info" | "neutre"> = {
  en_service: "succes",
  cedee: "info",
  reformee: "neutre",
};
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-lg font-semibold text-text">Immobilisations</h1>
      <router-link
        v-if="aPermission('immobilisation.creer')"
        :to="{ name: 'immobilisations.nouvelle' }"
        class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover"
      >
        Nouvelle immobilisation
      </router-link>
    </div>

    <router-link
      v-if="aConfirmer && aConfirmer.length > 0 && aPermission('immobilisation.creer')"
      :to="{ name: 'immobilisations.a-confirmer' }"
      class="block rounded-lg border border-warning bg-warning-bg px-4 py-3 text-sm text-text"
    >
      {{ aConfirmer.length }} acquisition(s) saisie(s) en comptabilité (comptes 21 à 27) attendent d'être
      reprises en immobilisation — <span class="font-medium text-primary">les confirmer</span>.
    </router-link>

    <select v-model="statut" class="rounded-md border border-border px-3 py-2 text-sm text-text">
      <option :value="null">Tous les statuts</option>
      <option value="en_service">En service</option>
      <option value="cedee">Cédées</option>
      <option value="reformee">Réformées</option>
    </select>

    <BaseDataTable
      :colonnes="colonnes"
      :lignes="immobilisations ?? []"
      :chargement="isLoading"
      message-vide="Aucune immobilisation pour le moment."
      @ligne-cliquee="ouvrir"
    >
      <template #cell-categorie="{ valeur }">{{ valeur ?? "—" }}</template>
      <template #cell-valeur_origine="{ valeur }">{{ formaterMontant(valeur as string) }}</template>
      <template #cell-statut="{ valeur }">
        <StatutBadge :libelle="libellesStatut[valeur as string]" :tonalite="tonalitesStatut[valeur as string]" />
      </template>
    </BaseDataTable>
  </div>
</template>