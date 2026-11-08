<script setup lang="ts">
import { computed, ref } from "vue";
import { useRouter } from "vue-router";

import { useAuth } from "@/core/auth/useAuth";
import BaseDataTable, { type ColonneTable } from "@/core/ui/BaseDataTable.vue";
import { formaterMontant } from "@/core/ui/formatage";
import StatutBadge from "@/core/ui/StatutBadge.vue";
import { useListeEmployes, type FiltresEmployes } from "./api";
import type { Employe } from "./types";

const router = useRouter();
const { contexteActif, aPermission } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const filtres = ref<FiltresEmployes>({ actifsSeulement: true });
const { data: employes, isLoading } = useListeEmployes(entrepriseId, filtres);

const colonnes: ColonneTable<Employe>[] = [
  { cle: "matricule", libelle: "Matricule" },
  { cle: "prenom", libelle: "Prénom" },
  { cle: "nom", libelle: "Nom" },
  { cle: "poste", libelle: "Poste" },
  { cle: "salaire_base", libelle: "Salaire de base" },
  { cle: "statut", libelle: "Statut" },
];

function ouvrir(ligne: Employe): void {
  router.push({ name: "paie.employe.modifier", params: { id: ligne.id } });
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-lg font-semibold text-text">Employés</h1>
      <router-link
        v-if="aPermission('employe.creer')"
        :to="{ name: 'paie.employe.nouveau' }"
        class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover"
      >
        Nouvel employé
      </router-link>
    </div>

    <label class="flex w-fit items-center gap-2 text-sm text-text-muted">
      <input v-model="filtres.actifsSeulement" type="checkbox" />
      Actifs seulement
    </label>

    <BaseDataTable
      :colonnes="colonnes"
      :lignes="employes ?? []"
      :chargement="isLoading"
      message-vide="Aucun employé pour le moment."
      @ligne-cliquee="ouvrir"
    >
      <template #cell-poste="{ valeur }">{{ valeur || "—" }}</template>
      <template #cell-salaire_base="{ valeur }">{{ formaterMontant(valeur as string) }}</template>
      <template #cell-statut="{ valeur }">
        <StatutBadge :libelle="valeur === 'actif' ? 'Actif' : 'Inactif'" :tonalite="valeur === 'actif' ? 'succes' : 'neutre'" />
      </template>
    </BaseDataTable>
  </div>
</template>
