<script setup lang="ts">
/**
 * Coquille commune à tous les formulaires métier : titre, zone d'erreur
 * générale (ex. message 422 du backend), boutons Annuler/Enregistrer. Le
 * contenu des champs reste dans chaque module — ce composant ne connaît pas
 * les champs, seulement l'habillage.
 */
withDefaults(
  defineProps<{
    titre: string;
    erreur?: string | null;
    enEnvoi?: boolean;
    libelleEnregistrer?: string;
  }>(),
  { erreur: null, enEnvoi: false, libelleEnregistrer: "Enregistrer" },
);

defineEmits<{ soumettre: []; annuler: [] }>();
</script>

<template>
  <form
    class="space-y-4 rounded-lg border border-border bg-surface p-6"
    @submit.prevent="$emit('soumettre')"
  >
    <h2 class="text-base font-semibold text-text">{{ titre }}</h2>

    <div class="space-y-4">
      <slot />
    </div>

    <p v-if="erreur" class="text-sm text-danger">{{ erreur }}</p>

    <div class="flex justify-end gap-2 pt-2">
      <button
        type="button"
        class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted"
        @click="$emit('annuler')"
      >
        Annuler
      </button>
      <button
        type="submit"
        :disabled="enEnvoi"
        class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60"
      >
        {{ enEnvoi ? "Enregistrement..." : libelleEnregistrer }}
      </button>
    </div>
  </form>
</template>
