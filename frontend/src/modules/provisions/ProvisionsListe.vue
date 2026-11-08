<script setup lang="ts">
import { computed, reactive } from "vue";
import { useRouter } from "vue-router";

import { useAuth } from "@/core/auth/useAuth";
import BaseDataTable, { type ColonneTable } from "@/core/ui/BaseDataTable.vue";
import { formaterMontant } from "@/core/ui/formatage";
import StatutBadge from "@/core/ui/StatutBadge.vue";
import { useListeProvisions, type FiltresProvisions } from "./api";
import type { Provision } from "./types";

const router = useRouter();
const { contexteActif, aPermission } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const filtres = reactive<FiltresProvisions>({ typeProvision: null, statut: null });
const { data: provisions, isLoading } = useListeProvisions(entrepriseId, computed(() => filtres));

const colonnes: ColonneTable<Provision>[] = [
  { cle: "libelle", libelle: "Libellé" },
  { cle: "type_provision", libelle: "Type" },
  { cle: "montant_actuel", libelle: "Montant actuel" },
  { cle: "statut", libelle: "Statut" },
];

function ouvrir(ligne: Provision): void {
  router.push({ name: "provisions.detail", params: { id: ligne.id } });
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
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-lg font-semibold text-text">Provisions</h1>
      <router-link
        v-if="aPermission('provision.creer')"
        :to="{ name: 'provisions.nouvelle' }"
        class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover"
      >
        Nouvelle provision
      </router-link>
    </div>

    <div class="flex gap-3">
      <select v-model="filtres.typeProvision" class="rounded-md border border-border px-3 py-2 text-sm text-text">
        <option :value="null">Tous les types</option>
        <option value="depreciation_creance">Dépréciation de créance</option>
        <option value="depreciation_stock">Dépréciation de stock</option>
        <option value="risque_charge">Risques et charges</option>
      </select>
      <select v-model="filtres.statut" class="rounded-md border border-border px-3 py-2 text-sm text-text">
        <option :value="null">Tous les statuts</option>
        <option value="active">Actives</option>
        <option value="soldee">Soldées</option>
      </select>
    </div>

    <BaseDataTable
      :colonnes="colonnes"
      :lignes="provisions ?? []"
      :chargement="isLoading"
      message-vide="Aucune provision pour le moment."
      @ligne-cliquee="ouvrir"
    >
      <template #cell-type_provision="{ valeur }">{{ libellesType[valeur as string] }}</template>
      <template #cell-montant_actuel="{ valeur }">{{ formaterMontant(valeur as string) }}</template>
      <template #cell-statut="{ valeur }">
        <StatutBadge :libelle="libellesStatut[valeur as string]" :tonalite="tonalitesStatut[valeur as string]" />
      </template>
    </BaseDataTable>
  </div>
</template>