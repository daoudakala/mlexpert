<script setup lang="ts">
import { computed, ref } from "vue";
import { useRouter } from "vue-router";

import { useAuth } from "@/core/auth/useAuth";
import { useExercices } from "@/modules/exercices/api";
import BaseDataTable, { type ColonneTable } from "@/core/ui/BaseDataTable.vue";
import { formaterMontant } from "@/core/ui/formatage";
import StatutBadge from "@/core/ui/StatutBadge.vue";
import { useListeBulletins, useListeEmployes, type FiltresBulletins } from "./api";
import type { Bulletin } from "./types";

const router = useRouter();
const { contexteActif, aPermission } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const { data: employes } = useListeEmployes(entrepriseId, computed(() => ({ actifsSeulement: false })));
const { data: exercices } = useExercices(entrepriseId);

const filtres = ref<FiltresBulletins>({});
const { data: bulletins, isLoading } = useListeBulletins(entrepriseId, filtres);

function libelleEmploye(employeId: string): string {
  const e = employes.value?.find((emp) => emp.id === employeId);
  return e ? `${e.prenom} ${e.nom}` : employeId;
}

const colonnes: ColonneTable<Bulletin>[] = [
  { cle: "employe_id", libelle: "Employé" },
  { cle: "periode_debut", libelle: "Début" },
  { cle: "periode_fin", libelle: "Fin" },
  { cle: "net_a_payer", libelle: "Net à payer" },
  { cle: "statut", libelle: "Statut" },
];

function ouvrir(ligne: Bulletin): void {
  router.push({ name: "paie.bulletin", params: { id: ligne.id } });
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-lg font-semibold text-text">Bulletins de paie</h1>
      <router-link
        v-if="aPermission('bulletin.creer')"
        :to="{ name: 'paie.bulletin.nouveau' }"
        class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover"
      >
        Nouveau bulletin
      </router-link>
    </div>

    <div class="flex flex-wrap gap-4">
      <select v-model="filtres.employeId" class="rounded-md border border-border px-3 py-2 text-sm text-text">
        <option value="">Tous les employés</option>
        <option v-for="e in employes ?? []" :key="e.id" :value="e.id">{{ e.prenom }} {{ e.nom }}</option>
      </select>
      <select v-model="filtres.exerciceId" class="rounded-md border border-border px-3 py-2 text-sm text-text">
        <option value="">Tous les exercices</option>
        <option v-for="ex in exercices ?? []" :key="ex.id" :value="ex.id">{{ ex.date_debut }} → {{ ex.date_fin }}</option>
      </select>
      <select v-model="filtres.statut" class="rounded-md border border-border px-3 py-2 text-sm text-text">
        <option value="">Tous les statuts</option>
        <option value="brouillon">Brouillon</option>
        <option value="valide">Validé</option>
      </select>
    </div>

    <BaseDataTable
      :colonnes="colonnes"
      :lignes="bulletins ?? []"
      :chargement="isLoading"
      message-vide="Aucun bulletin pour le moment."
      @ligne-cliquee="ouvrir"
    >
      <template #cell-employe_id="{ valeur }">{{ libelleEmploye(valeur as string) }}</template>
      <template #cell-net_a_payer="{ valeur }">{{ formaterMontant(valeur as string) }}</template>
      <template #cell-statut="{ valeur }">
        <StatutBadge :libelle="valeur === 'valide' ? 'Validé' : 'Brouillon'" :tonalite="valeur === 'valide' ? 'succes' : 'avertissement'" />
      </template>
    </BaseDataTable>
  </div>
</template>
