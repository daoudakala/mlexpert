<script setup lang="ts">
/**
 * Pas de page détail dédiée : une régularisation est un événement figé dès
 * sa création (voir models.py), il n'y a rien à modifier ni de mouvement à
 * consulter. Cliquer une ligne ouvre directement l'écriture générée, où le
 * bouton "Extourner" existant (EcritureFormulaire.vue) permet de la
 * contre-passer sur l'exercice suivant.
 */
import { computed, reactive } from "vue";
import { useRouter } from "vue-router";

import { useAuth } from "@/core/auth/useAuth";
import BaseDataTable, { type ColonneTable } from "@/core/ui/BaseDataTable.vue";
import { formaterMontant } from "@/core/ui/formatage";
import { useListeRegularisations, type FiltresRegularisations } from "./api";
import type { Regularisation } from "./types";

const router = useRouter();
const { contexteActif, aPermission } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const filtres = reactive<FiltresRegularisations>({ typeRegularisation: null });
const { data: regularisations, isLoading } = useListeRegularisations(entrepriseId, computed(() => filtres));

const colonnes: ColonneTable<Regularisation>[] = [
  { cle: "date_regularisation", libelle: "Date" },
  { cle: "libelle", libelle: "Libellé" },
  { cle: "type_regularisation", libelle: "Type" },
  { cle: "montant", libelle: "Montant" },
];

function ouvrir(ligne: Regularisation): void {
  router.push({ name: "comptabilite.ecriture", params: { id: ligne.ecriture_id } });
}

const libellesType: Record<string, string> = {
  charge_constatee_avance: "Charge constatée d'avance (CCA)",
  produit_constate_avance: "Produit constaté d'avance (PCA)",
  charge_a_payer: "Charge à payer (FNP)",
  produit_a_recevoir: "Produit à recevoir",
};
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-lg font-semibold text-text">Écritures de régularisation (CCA/PCA, charges à payer, produits à recevoir)</h1>
      <router-link
        v-if="aPermission('regularisation.creer')"
        :to="{ name: 'regularisations.nouvelle' }"
        class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover"
      >
        Nouvelle régularisation
      </router-link>
    </div>

    <div class="flex gap-3">
      <select v-model="filtres.typeRegularisation" class="rounded-md border border-border px-3 py-2 text-sm text-text">
        <option :value="null">Tous les types</option>
        <option value="charge_constatee_avance">Charges constatées d'avance (CCA)</option>
        <option value="produit_constate_avance">Produits constatés d'avance (PCA)</option>
        <option value="charge_a_payer">Charges à payer (FNP)</option>
        <option value="produit_a_recevoir">Produits à recevoir</option>
      </select>
    </div>

    <BaseDataTable
      :colonnes="colonnes"
      :lignes="regularisations ?? []"
      :chargement="isLoading"
      message-vide="Aucune régularisation pour le moment."
      @ligne-cliquee="ouvrir"
    >
      <template #cell-type_regularisation="{ valeur }">{{ libellesType[valeur as string] }}</template>
      <template #cell-montant="{ valeur }">{{ formaterMontant(valeur as string) }}</template>
    </BaseDataTable>
  </div>
</template>