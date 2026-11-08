<script setup lang="ts">
/**
 * Page "Mes préférences de notification" : une ligne par type connu
 * (LIBELLES_TYPE_NOTIFICATION, voir types.ts), toggle actif/inactif +
 * niveau minimum. Absence de préférence enregistrée pour un type =
 * valeurs par défaut (actif, niveau "info") — voir service.py côté
 * backend ; cette page affiche donc ces valeurs par défaut pour un type
 * qui n'a jamais été configuré, sans qu'une ligne existe encore en base.
 */
import { computed } from "vue";

import { useAuth } from "@/core/auth/useAuth";
import { useMesPreferences, useMutationsNotifications } from "./api";
import { LIBELLES_TYPE_NOTIFICATION, type NiveauCriticite, type TypeNotification } from "./types";

const { contexteActif } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const { data: preferences, isLoading } = useMesPreferences(entrepriseId);
const { definirPreference } = useMutationsNotifications(entrepriseId);

const TYPES_CONNUS = Object.keys(LIBELLES_TYPE_NOTIFICATION) as TypeNotification[];

const NIVEAUX: { valeur: NiveauCriticite; libelle: string }[] = [
  { valeur: "info", libelle: "Info" },
  { valeur: "avertissement", libelle: "Avertissement" },
  { valeur: "critique", libelle: "Critique" },
];

function preferencePour(type: TypeNotification) {
  const existante = (preferences.value ?? []).find((p) => p.type_notification === type);
  return existante ?? { type_notification: type, active: true, niveau_minimum: "info" as NiveauCriticite };
}

function surChangementActif(type: TypeNotification, active: boolean): void {
  const actuelle = preferencePour(type);
  definirPreference.mutate({
    typeNotification: type,
    donnees: { active, niveau_minimum: actuelle.niveau_minimum },
  });
}

function surChangementNiveau(type: TypeNotification, niveau_minimum: NiveauCriticite): void {
  const actuelle = preferencePour(type);
  definirPreference.mutate({
    typeNotification: type,
    donnees: { active: actuelle.active, niveau_minimum },
  });
}
</script>

<template>
  <div class="space-y-4">
    <h1 class="text-lg font-semibold text-text">Mes préférences de notification</h1>
    <p class="text-sm text-text-muted">
      Choisissez quels types de notification vous souhaitez recevoir, et à partir de quel niveau de criticité.
      Les alertes de sécurité sont toujours envoyées, quel que soit ce réglage.
    </p>

    <p v-if="isLoading" class="text-sm text-text-muted">Chargement…</p>
    <div v-else class="overflow-hidden rounded-lg border border-border">
      <table class="w-full text-sm">
        <thead class="bg-surface-muted text-left text-xs uppercase text-text-muted">
          <tr>
            <th class="px-4 py-2">Type</th>
            <th class="px-4 py-2">Actif</th>
            <th class="px-4 py-2">Niveau minimum</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="type in TYPES_CONNUS" :key="type" class="border-t border-border">
            <td class="px-4 py-2 text-text">
              {{ LIBELLES_TYPE_NOTIFICATION[type] }}
              <span v-if="type === 'alerte_securite'" class="ml-1 text-xs text-text-muted">(toujours active)</span>
            </td>
            <td class="px-4 py-2">
              <input
                type="checkbox"
                :checked="preferencePour(type).active"
                :disabled="type === 'alerte_securite'"
                @change="surChangementActif(type, ($event.target as HTMLInputElement).checked)"
              />
            </td>
            <td class="px-4 py-2">
              <select
                :value="preferencePour(type).niveau_minimum"
                class="rounded-md border border-border bg-surface px-2 py-1 text-sm text-text"
                @change="surChangementNiveau(type, ($event.target as HTMLSelectElement).value as NiveauCriticite)"
              >
                <option v-for="n in NIVEAUX" :key="n.valeur" :value="n.valeur">{{ n.libelle }}</option>
              </select>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>