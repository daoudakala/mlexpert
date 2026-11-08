<script setup lang="ts">
import { computed, ref } from "vue";
import { useRouter } from "vue-router";

import { useAuth } from "@/core/auth/useAuth";
import BaseDataTable, { type ColonneTable } from "@/core/ui/BaseDataTable.vue";
import { formaterMontant } from "@/core/ui/formatage";
import StatutBadge from "@/core/ui/StatutBadge.vue";
import { useListeComptesBancaires } from "./api";
import type { CompteBancaire } from "./types";

const router = useRouter();
const { contexteActif, aPermission } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const actifsSeulement = ref(true);
const { data: comptes, isLoading } = useListeComptesBancaires(entrepriseId, actifsSeulement);

const colonnes: ColonneTable<CompteBancaire>[] = [
  { cle: "libelle", libelle: "Libellé" },
  { cle: "banque", libelle: "Banque" },
  { cle: "numero_compte", libelle: "N° compte" },
  { cle: "solde_initial", libelle: "Solde initial" },
  { cle: "actif", libelle: "Statut" },
];

function ouvrir(ligne: CompteBancaire): void {
  router.push({ name: "tresorerie.compte-bancaire", params: { id: ligne.id } });
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-lg font-semibold text-text">Comptes bancaires</h1>
      <router-link
        v-if="aPermission('compte_bancaire.creer')"
        :to="{ name: 'tresorerie.compte-bancaire.nouveau' }"
        class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover"
      >
        Nouveau compte bancaire
      </router-link>
    </div>

    <label class="flex items-center gap-2 text-sm text-text-muted">
      <input v-model="actifsSeulement" type="checkbox" />
      Actifs seulement
    </label>

    <BaseDataTable
      :colonnes="colonnes"
      :lignes="comptes ?? []"
      :chargement="isLoading"
      message-vide="Aucun compte bancaire pour le moment."
      @ligne-cliquee="ouvrir"
    >
      <template #cell-solde_initial="{ valeur }">{{ formaterMontant(valeur as string) }}</template>
      <template #cell-actif="{ ligne }">
        <StatutBadge
          :libelle="ligne.actif ? 'Actif' : 'Désactivé'"
          :tonalite="ligne.actif ? 'succes' : 'neutre'"
        />
      </template>
    </BaseDataTable>
  </div>
</template>
