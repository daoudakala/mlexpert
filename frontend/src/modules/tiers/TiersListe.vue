<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useAuth } from "@/core/auth/useAuth";
import { useComptesEntreprise } from "@/modules/comptabilite/api";
import BaseDataTable, { type ColonneTable } from "@/core/ui/BaseDataTable.vue";
import StatutBadge from "@/core/ui/StatutBadge.vue";
import { useListeTiers, type FiltresTiers } from "./api";
import type { Tiers } from "./types";

const router = useRouter();
const { contexteActif, aPermission } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const route = useRoute();
const filtres = ref<FiltresTiers>({ actifsSeulement: true });

// Le menu latéral ouvre cette page avec ?role=client ou ?role=fournisseur.
watch(
  () => route.query.role,
  (role) => {
    filtres.value.clientSeulement = role === "client";
    filtres.value.fournisseurSeulement = role === "fournisseur";
  },
  { immediate: true },
);
const { data: tiers, isLoading } = useListeTiers(entrepriseId, filtres);

// Numéro du compte de regroupement affiché dans la liste.
const { data: comptes } = useComptesEntreprise(entrepriseId, computed(() => ({ limite: 5000 })));
const numeroCompte = computed(() => new Map((comptes.value ?? []).map((c) => [c.id, c.numero])));

function comptesDuTiers(t: Tiers): string {
  return [t.compte_collectif_client_id, t.compte_collectif_fournisseur_id]
    .filter((id): id is string => !!id)
    .map((id) => numeroCompte.value.get(id) ?? "—")
    .join(" / ");
}

const colonnes: ColonneTable<Tiers>[] = [
  { cle: "code", libelle: "Code" },
  { cle: "raison_sociale", libelle: "Raison sociale" },
  { cle: "compte_collectif_client_id", libelle: "Compte de regroupement" },
  { cle: "est_client", libelle: "Rôle" },
  { cle: "actif", libelle: "Statut" },
];

function ouvrir(ligne: Tiers): void {
  router.push({ name: "tiers.modifier", params: { id: ligne.id } });
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-lg font-semibold text-text">Tiers</h1>
      <router-link
        v-if="aPermission('tiers.creer')"
        :to="{ name: 'tiers.nouveau' }"
        class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover"
      >
        Nouveau tiers
      </router-link>
    </div>

    <div class="flex gap-4 text-sm text-text-muted">
      <label class="flex items-center gap-2">
        <input v-model="filtres.actifsSeulement" type="checkbox" />
        Actifs seulement
      </label>
      <label class="flex items-center gap-2">
        <input v-model="filtres.clientSeulement" type="checkbox" />
        Clients seulement
      </label>
      <label class="flex items-center gap-2">
        <input v-model="filtres.fournisseurSeulement" type="checkbox" />
        Fournisseurs seulement
      </label>
    </div>

    <BaseDataTable
      :colonnes="colonnes"
      :lignes="tiers ?? []"
      :chargement="isLoading"
      message-vide="Aucun tiers pour le moment."
      @ligne-cliquee="ouvrir"
    >
      <template #cell-compte_collectif_client_id="{ ligne }">
        <span class="font-mono text-xs text-text">{{ comptesDuTiers(ligne) }}</span>
      </template>
      <template #cell-est_client="{ ligne }">
        <span class="text-text">
          {{ [ligne.est_client && "Client", ligne.est_fournisseur && "Fournisseur"].filter(Boolean).join(" / ") }}
        </span>
      </template>
      <template #cell-actif="{ ligne }">
        <StatutBadge
          :libelle="ligne.actif ? 'Actif' : 'Désactivé'"
          :tonalite="ligne.actif ? 'succes' : 'neutre'"
        />
      </template>
    </BaseDataTable>
  </div>
</template>