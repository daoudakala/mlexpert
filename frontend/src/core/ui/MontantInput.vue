<script setup lang="ts">
/**
 * Champ de saisie d'un montant avec séparateur de milliers à l'affichage
 * ("facilite la lecture et l'écriture", cf. demande utilisateur) :
 *   - au focus, affiche la valeur brute (sans séparateur) pour une
 *     édition simple, et la sélectionne entièrement ;
 *   - à la perte de focus, réaffiche la valeur groupée par milliers.
 * `v-model` reste un nombre (ou null si vide) — jamais une chaîne
 * formatée — pour ne rien changer aux payloads envoyés au backend.
 */
import { ref, watch } from "vue";

import { formaterMontant } from "./formatage";

const montant = defineModel<number | null>({ required: true });

withDefaults(
  defineProps<{
    required?: boolean;
    disabled?: boolean;
    placeholder?: string;
  }>(),
  { required: false, disabled: false },
);

const enFocus = ref(false);
const texte = ref(formaterAffiche(montant.value));

function formaterAffiche(v: number | null): string {
  return v === null || v === undefined ? "" : formaterMontant(v);
}

watch(montant, (v) => {
  if (!enFocus.value) texte.value = formaterAffiche(v);
});

function surFocus(e: FocusEvent): void {
  enFocus.value = true;
  texte.value = montant.value === null || montant.value === undefined ? "" : String(montant.value);
  (e.target as HTMLInputElement).select();
}

function surSaisie(e: Event): void {
  const brut = (e.target as HTMLInputElement).value;
  texte.value = brut;
  if (brut.trim() === "") {
    montant.value = null;
    return;
  }
  const normalise = brut.replace(/\s/g, "").replace(",", ".");
  const nombre = parseFloat(normalise);
  if (!Number.isNaN(nombre)) montant.value = nombre;
}

function surPerteFocus(): void {
  enFocus.value = false;
  texte.value = formaterAffiche(montant.value);
}
</script>

<template>
  <input
    type="text"
    inputmode="decimal"
    :value="texte"
    :disabled="disabled"
    :required="required"
    :placeholder="placeholder"
    class="w-full rounded-md border border-border px-3 py-2 text-right text-text disabled:opacity-60"
    @focus="surFocus"
    @input="surSaisie"
    @blur="surPerteFocus"
  />
</template>
