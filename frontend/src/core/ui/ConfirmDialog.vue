<script setup lang="ts">
/**
 * Boîte de confirmation générique (suppression, validation irréversible,
 * cession/réforme d'immobilisation, ...). Contrôlée par `v-model:ouvert`
 * pour que l'appelant garde la main sur quand elle apparaît.
 */
const ouvert = defineModel<boolean>("ouvert", { required: true });

withDefaults(
  defineProps<{
    titre: string;
    message: string;
    libelleConfirmer?: string;
    libelleAnnuler?: string;
    dangereux?: boolean;
  }>(),
  { libelleConfirmer: "Confirmer", libelleAnnuler: "Annuler", dangereux: false },
);

const emit = defineEmits<{ confirmer: []; annuler: [] }>();

function confirmer(): void {
  ouvert.value = false;
  emit("confirmer");
}

function annuler(): void {
  ouvert.value = false;
  emit("annuler");
}
</script>

<template>
  <div
    v-if="ouvert"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
    @click.self="annuler"
  >
    <div class="w-full max-w-sm rounded-lg bg-surface p-6 shadow-lg">
      <h2 class="text-base font-semibold text-text">{{ titre }}</h2>
      <p class="mt-2 text-sm text-text-muted">{{ message }}</p>
      <div class="mt-6 flex justify-end gap-2">
        <button
          type="button"
          class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted"
          @click="annuler"
        >
          {{ libelleAnnuler }}
        </button>
        <button
          type="button"
          class="rounded-md px-3 py-1.5 text-sm font-medium text-primary-foreground"
          :class="dangereux ? 'bg-danger hover:opacity-90' : 'bg-primary hover:bg-primary-hover'"
          @click="confirmer"
        >
          {{ libelleConfirmer }}
        </button>
      </div>
    </div>
  </div>
</template>
