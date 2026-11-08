<script setup lang="ts">
/**
 * Administration de plateforme : liste de toutes les entreprises clientes
 * (route réservée à l'administrateur plateforme, meta.adminPlateforme).
 */
import { ref } from "vue";
import { useRouter } from "vue-router";

import BaseDataTable, { type ColonneTable } from "@/core/ui/BaseDataTable.vue";
import StatutBadge from "@/core/ui/StatutBadge.vue";
import { useListeEntreprises } from "./api";
import type { Entreprise } from "./types";

const router = useRouter();
const recherche = ref("");
const { data: entreprises, isLoading } = useListeEntreprises(recherche);

const colonnes: ColonneTable<Entreprise>[] = [
  { cle: "raison_sociale", libelle: "Raison sociale" },
  { cle: "sigle", libelle: "Sigle" },
  { cle: "activite", libelle: "Activité" },
  { cle: "statut", libelle: "Statut" },
];

const tonaliteStatut: Record<string, "succes" | "neutre" | "danger"> = {
  active: "succes",
  suspendue: "danger",
  archivee: "neutre",
};

function ouvrir(ligne: Entreprise): void {
  router.push({ name: "entreprises.modifier", params: { id: ligne.id } });
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-lg font-semibold text-text">Entreprises</h1>
      <router-link
        :to="{ name: 'entreprises.nouvelle' }"
        class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover"
      >
        Nouvelle entreprise
      </router-link>
    </div>

    <input
      v-model="recherche"
      placeholder="Rechercher par raison sociale ou sigle..."
      class="w-full max-w-sm rounded-md border border-border px-3 py-2 text-sm text-text"
    />

    <BaseDataTable
      :colonnes="colonnes"
      :lignes="entreprises ?? []"
      :chargement="isLoading"
      message-vide="Aucune entreprise."
      @ligne-cliquee="ouvrir"
    >
      <template #cell-statut="{ valeur }">
        <StatutBadge :libelle="(valeur as string)" :tonalite="tonaliteStatut[valeur as string] ?? 'neutre'" />
      </template>
    </BaseDataTable>
  </div>
</template>
