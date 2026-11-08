<script setup lang="ts">
import { useRouter } from "vue-router";

import { useAuth } from "@/core/auth/useAuth";
import NotificationCloche from "@/modules/notifications/NotificationCloche.vue";

const { utilisateur, aPermission, deconnecter } = useAuth();
const router = useRouter();

async function surDeconnexion(): Promise<void> {
  await deconnecter();
  router.push({ name: "connexion" });
}
</script>

<template>
  <div class="flex min-h-screen flex-col">
    <header class="flex items-center justify-between border-b border-border bg-surface px-6 py-3">
      <span class="font-semibold text-text">MLexpert — Portail client</span>
      <div class="flex items-center gap-3 text-sm text-text-muted">
        <NotificationCloche v-if="aPermission('notification.consulter')" />
        <span v-if="utilisateur">{{ utilisateur.prenom }} {{ utilisateur.nom }}</span>
        <button type="button" class="text-primary hover:underline" @click="surDeconnexion">
          Déconnexion
        </button>
      </div>
    </header>
    <main class="flex-1 p-6">
      <router-view />
    </main>
  </div>
</template>