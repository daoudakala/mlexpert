<script setup lang="ts">
/**
 * Icône cloche + badge de compteur + panneau déroulant, montée à la fois
 * dans AppLayout.vue (cabinet) et PortailClientLayout.vue (client).
 * Polling léger (voir api.ts) plutôt que du temps réel : pas de
 * WebSocket/SSE dans ce projet pour l'instant.
 */
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useAuth } from "@/core/auth/useAuth";
import { useCompteurNotifications, useMesNotifications, useMutationsNotifications } from "./api";
import { LIBELLES_TYPE_NOTIFICATION, type Notification, type TypeNotification } from "./types";

const { contexteActif } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);
const router = useRouter();
const route = useRoute();

const panneauOuvert = ref(false);
const nonLuesSeulement = ref(false);

const { data: compteur } = useCompteurNotifications(entrepriseId);
const { data: notifications, isLoading: chargement } = useMesNotifications(entrepriseId, nonLuesSeulement);
const { marquerLue, marquerToutesLues } = useMutationsNotifications(entrepriseId);

function libelleType(type: string): string {
  return LIBELLES_TYPE_NOTIFICATION[type as TypeNotification] ?? type;
}

function classeCriticite(niveau: string): string {
  if (niveau === "critique") return "border-l-danger";
  if (niveau === "avertissement") return "border-l-warning";
  return "border-l-border";
}

function surClicNotification(notification: Notification): void {
  if (!notification.lu) {
    marquerLue.mutate(notification.id);
  }
  panneauOuvert.value = false;
}

function surMarquerToutesLues(): void {
  marquerToutesLues.mutate();
}

function surOuvrirPreferences(): void {
  panneauOuvert.value = false;
  // Ce composant est monté à la fois dans AppLayout.vue (cabinet) et
  // PortailClientLayout.vue (client) — deux coquilles visuelles
  // distinctes exprès (séparation des espaces, cahier annexe B). On reste
  // dans la bonne coquille plutôt que de toujours pousser vers la route
  // de préférences du cabinet, qui ferait sortir un client du portail.
  const nomRoute = route.path.startsWith("/portail")
    ? "portail.notifications.preferences"
    : "notifications.preferences";
  router.push({ name: nomRoute });
}
</script>

<template>
  <div class="relative">
    <button
      type="button"
      class="relative rounded-md p-2 text-text-muted hover:bg-surface-muted"
      aria-label="Notifications"
      @click="panneauOuvert = !panneauOuvert"
    >
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" class="h-5 w-5">
        <path stroke-linecap="round" stroke-linejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
      </svg>
      <span
        v-if="compteur && compteur.non_lues > 0"
        class="absolute -right-0.5 -top-0.5 flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-danger px-1 text-[10px] font-semibold text-white"
      >
        {{ compteur.non_lues > 99 ? "99+" : compteur.non_lues }}
      </span>
    </button>

    <div
      v-if="panneauOuvert"
      class="absolute right-0 z-20 mt-2 w-96 rounded-lg border border-border bg-surface shadow-lg"
    >
      <div class="flex items-center justify-between border-b border-border px-4 py-2">
        <span class="text-sm font-medium text-text">Notifications</span>
        <div class="flex items-center gap-3 text-xs">
          <button type="button" class="text-text-muted hover:underline" @click="nonLuesSeulement = !nonLuesSeulement">
            {{ nonLuesSeulement ? "Toutes" : "Non lues" }}
          </button>
          <button type="button" class="text-primary hover:underline" @click="surMarquerToutesLues">
            Tout marquer lu
          </button>
        </div>
      </div>

      <div class="max-h-96 overflow-y-auto">
        <p v-if="chargement" class="p-4 text-sm text-text-muted">Chargement…</p>
        <p v-else-if="!notifications || notifications.length === 0" class="p-4 text-sm text-text-muted">
          Aucune notification{{ nonLuesSeulement ? " non lue" : "" }}.
        </p>
        <button
          v-for="notification in notifications"
          :key="notification.id"
          type="button"
          class="block w-full border-l-4 border-b border-border px-4 py-2 text-left hover:bg-surface-muted"
          :class="[classeCriticite(notification.niveau_criticite), notification.lu ? 'opacity-60' : '']"
          @click="surClicNotification(notification)"
        >
          <p class="flex items-center justify-between text-xs text-text-muted">
            <span>{{ libelleType(notification.type_notification) }}</span>
            <span v-if="!notification.lu" class="h-1.5 w-1.5 rounded-full bg-primary" />
          </p>
          <p class="text-sm font-medium text-text">{{ notification.titre }}</p>
          <p class="text-xs text-text-muted">{{ notification.message }}</p>
        </button>
      </div>

      <div class="border-t border-border px-4 py-2">
        <button type="button" class="text-xs text-primary hover:underline" @click="surOuvrirPreferences">
          Préférences de notification
        </button>
      </div>
    </div>
  </div>
</template>