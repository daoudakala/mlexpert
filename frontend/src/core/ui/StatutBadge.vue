<script setup lang="ts">
/**
 * Badge de statut générique, réutilisé par tous les modules (employé
 * actif/inactif, bulletin brouillon/validé, article actif/inactif, ...).
 * La palette ne dépend pas du libellé : on passe explicitement la
 * "tonalité" voulue, le libellé reste libre et traduit par l'appelant.
 */
withDefaults(
  defineProps<{
    libelle: string;
    tonalite?: "neutre" | "succes" | "avertissement" | "danger" | "info";
  }>(),
  { tonalite: "neutre" },
);

const classesParTonalite: Record<string, string> = {
  neutre: "bg-surface-muted text-text-muted",
  succes: "bg-success-bg text-success",
  avertissement: "bg-warning-bg text-warning",
  danger: "bg-danger-bg text-danger",
  info: "bg-info-bg text-info",
};
</script>

<template>
  <span
    class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium"
    :class="classesParTonalite[tonalite]"
  >
    {{ libelle }}
  </span>
</template>
