<script setup lang="ts" generic="T extends Record<string, unknown>">
/**
 * Table générique réutilisée par les listes de chaque module (employés,
 * articles, tiers, bulletins, ...). Chaque module définit ses propres
 * colonnes ; ce composant ne connaît rien du métier.
 *
 * Le rendu d'une cellule passe par un slot nommé `cell-<cle>` quand
 * l'appelant veut un rendu personnalisé (badge de statut, lien, montant
 * formaté) ; sinon la valeur brute est affichée.
 */
export interface ColonneTable<T> {
  cle: keyof T & string;
  libelle: string;
  classe?: string;
}

defineProps<{
  colonnes: ColonneTable<T>[];
  lignes: T[];
  chargement?: boolean;
  messageVide?: string;
}>();

defineEmits<{ "ligne-cliquee": [ligne: T] }>();
</script>

<template>
  <div class="overflow-hidden rounded-lg border border-border bg-surface">
    <table class="w-full text-sm">
      <thead class="bg-surface-muted text-left text-xs font-medium uppercase text-text-muted">
        <tr>
          <th v-for="colonne in colonnes" :key="colonne.cle" class="px-4 py-2" :class="colonne.classe">
            {{ colonne.libelle }}
          </th>
        </tr>
      </thead>
      <tbody class="divide-y divide-border">
        <tr v-if="chargement">
          <td :colspan="colonnes.length" class="px-4 py-6 text-center text-text-muted">
            Chargement...
          </td>
        </tr>
        <tr v-else-if="lignes.length === 0">
          <td :colspan="colonnes.length" class="px-4 py-6 text-center text-text-muted">
            {{ messageVide ?? "Aucun élément." }}
          </td>
        </tr>
        <tr
          v-for="(ligne, index) in lignes"
          v-else
          :key="index"
          class="cursor-pointer hover:bg-surface-muted"
          @click="$emit('ligne-cliquee', ligne)"
        >
          <td v-for="colonne in colonnes" :key="colonne.cle" class="px-4 py-2 text-text" :class="colonne.classe">
            <slot :name="`cell-${colonne.cle}`" :ligne="ligne" :valeur="ligne[colonne.cle]">
              {{ ligne[colonne.cle] }}
            </slot>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
