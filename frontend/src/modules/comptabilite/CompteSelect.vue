<script setup lang="ts">
/**
 * Sélecteur de compte avec recherche (numéro ou libellé) — remplace la
 * liste déroulante classique, inutilisable avec un plan comptable de
 * plusieurs centaines de comptes. La liste complète est fournie par le
 * parent (une seule requête partagée par toutes les lignes) ; le filtrage
 * se fait ici, côté navigateur, et n'affiche que les 50 premiers résultats.
 */
import { computed, ref } from "vue";

import type { Compte } from "./types";

const props = defineProps<{
  modelValue: string;
  comptes: Compte[] | undefined;
  required?: boolean;
}>();
const emit = defineEmits<{ "update:modelValue": [valeur: string] }>();

const ouvert = ref(false);
const recherche = ref("");
const saisieEnCours = ref(false);

const compteSelectionne = computed(() => props.comptes?.find((c) => c.id === props.modelValue));
const libelleSelection = computed(() =>
  compteSelectionne.value ? `${compteSelectionne.value.numero} — ${compteSelectionne.value.libelle}` : "",
);
const texteAffiche = computed(() => (saisieEnCours.value ? recherche.value : libelleSelection.value));

const propositions = computed(() => {
  const tous = props.comptes ?? [];
  const terme = recherche.value.trim().toLowerCase();
  if (!saisieEnCours.value || !terme) return tous.slice(0, 50);
  const parNumero = tous.filter((c) => c.numero.startsWith(terme));
  const autres = tous.filter(
    (c) =>
      !c.numero.startsWith(terme) &&
      (c.numero.includes(terme) || c.libelle.toLowerCase().includes(terme)),
  );
  return [...parNumero, ...autres].slice(0, 50);
});

function surSaisie(evenement: Event): void {
  recherche.value = (evenement.target as HTMLInputElement).value;
  saisieEnCours.value = true;
  ouvert.value = true;
}

function surFocus(evenement: FocusEvent): void {
  ouvert.value = true;
  (evenement.target as HTMLInputElement).select();
}

function fermer(): void {
  ouvert.value = false;
  saisieEnCours.value = false;
  recherche.value = "";
}

function choisir(compte: Compte): void {
  emit("update:modelValue", compte.id);
  fermer();
}

function choisirPremier(): void {
  if (ouvert.value && propositions.value.length > 0) choisir(propositions.value[0]);
}
</script>

<template>
  <div class="relative">
    <input
      :value="texteAffiche"
      :required="required"
      type="text"
      autocomplete="off"
      placeholder="N° ou libellé du compte"
      class="w-full rounded-md border border-border px-2 py-1.5 text-sm text-text"
      @input="surSaisie"
      @focus="surFocus"
      @blur="fermer"
      @keydown.enter.prevent="choisirPremier"
      @keydown.esc="fermer"
    />
    <ul
      v-if="ouvert"
      class="absolute z-20 mt-1 max-h-60 w-80 overflow-y-auto rounded-md border border-border bg-surface text-sm shadow-lg"
    >
      <li v-if="propositions.length === 0" class="px-3 py-2 text-text-muted">Aucun compte trouvé.</li>
      <li
        v-for="c in propositions"
        :key="c.id"
        class="cursor-pointer px-3 py-1.5 text-text hover:bg-surface-muted"
        @mousedown.prevent="choisir(c)"
      >
        {{ c.numero }} — {{ c.libelle }}
      </li>
    </ul>
  </div>
</template>