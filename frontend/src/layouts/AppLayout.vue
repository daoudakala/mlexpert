<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useAuth } from "@/core/auth/useAuth";
import MenuLateral from "@/core/ui/MenuLateral.vue";
import NotificationCloche from "@/modules/notifications/NotificationCloche.vue";

const {
  utilisateur,
  contextes,
  contexteActif,
  aPermission,
  estAdministrateurPlateforme,
  definirEntrepriseActive,
  deconnecter,
} = useAuth();
const router = useRouter();
const route = useRoute();

// Tiroir du menu (petits écrans uniquement : sur grand écran le menu est fixe).
const menuOuvert = ref(false);
watch(
  () => route.fullPath,
  () => {
    menuOuvert.value = false;
  },
);

const initiales = computed(() => {
  const u = utilisateur.value;
  if (!u) return "?";
  return `${u.prenom?.[0] ?? ""}${u.nom?.[0] ?? ""}`.toUpperCase() || "?";
});

const sousTitreUtilisateur = computed(() =>
  estAdministrateurPlateforme.value
    ? "Admin plateforme"
    : (contexteActif.value?.entreprise.raison_sociale ?? ""),
);

function surChangementEntreprise(evenement: Event): void {
  const id = (evenement.target as HTMLSelectElement).value;
  definirEntrepriseActive(id);
  // La plupart des pages dépendent de l'entreprise active : on revient à
  // l'accueil plutôt que de laisser une page afficher des données d'une
  // autre entreprise un court instant.
  router.push({ name: "accueil" });
}

async function surDeconnexion(): Promise<void> {
  await deconnecter();
  router.push({ name: "connexion" });
}
</script>

<template>
  <div class="min-h-screen">
    <!-- Voile derrière le tiroir (petits écrans) -->
    <div
      v-if="menuOuvert"
      class="fixed inset-0 z-30 bg-black/50 lg:hidden"
      aria-hidden="true"
      @click="menuOuvert = false"
    />

    <!-- Menu latéral : fixe sur grand écran, tiroir sinon -->
    <aside
      class="fixed inset-y-0 left-0 z-40 flex w-64 flex-col bg-[var(--color-sidebar)] transition-transform duration-200 lg:translate-x-0"
      :class="menuOuvert ? 'translate-x-0' : '-translate-x-full'"
    >
      <div class="flex items-center justify-between border-b border-[var(--color-sidebar-line)] px-5 py-4">
        <div class="flex items-center gap-3">
          <div
            class="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--color-sidebar-active)] text-sm font-bold text-white"
          >
            ML
          </div>
          <div class="leading-tight">
            <p class="text-base font-semibold text-white">MLexpert</p>
            <p class="text-xs text-[var(--color-sidebar-text-muted)]">Comptabilité</p>
          </div>
        </div>
        <button
          type="button"
          class="rounded-md p-1 text-[var(--color-sidebar-text-muted)] hover:bg-[var(--color-sidebar-hover)] hover:text-white lg:hidden"
          aria-label="Fermer le menu"
          @click="menuOuvert = false"
        >
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" class="h-5 w-5">
            <path d="M5 5l10 10M15 5 5 15" />
          </svg>
        </button>
      </div>

      <MenuLateral @navigation="menuOuvert = false" />

      <!-- Carte utilisateur -->
      <div class="border-t border-[var(--color-sidebar-line)] p-3">
        <div class="flex items-center gap-3 rounded-lg px-2 py-2">
          <div
            class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[var(--color-sidebar-active)] text-xs font-semibold text-white"
          >
            {{ initiales }}
          </div>
          <div class="min-w-0 flex-1 leading-tight">
            <p class="truncate text-sm font-medium text-white">
              {{ utilisateur ? `${utilisateur.prenom} ${utilisateur.nom}` : "" }}
            </p>
            <p class="truncate text-xs text-[var(--color-sidebar-text-muted)]">{{ sousTitreUtilisateur }}</p>
          </div>
          <button
            type="button"
            class="rounded-md p-1.5 text-[var(--color-sidebar-text-muted)] hover:bg-[var(--color-sidebar-hover)] hover:text-white"
            title="Déconnexion"
            aria-label="Déconnexion"
            @click="surDeconnexion"
          >
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" class="h-4 w-4">
              <path d="M8 3.5H5a1.5 1.5 0 0 0-1.5 1.5v10A1.5 1.5 0 0 0 5 16.5h3" />
              <path d="M12.5 6.5 16 10l-3.5 3.5" />
              <line x1="16" y1="10" x2="7.5" y2="10" />
            </svg>
          </button>
        </div>
      </div>
    </aside>

    <!-- Contenu -->
    <div class="flex min-h-screen flex-col lg:pl-64">
      <header class="flex items-center justify-between gap-3 border-b border-border bg-surface px-4 py-3 sm:px-6">
        <div class="flex min-w-0 items-center gap-3">
          <button
            type="button"
            class="rounded-md border border-border p-2 text-text hover:bg-surface-muted lg:hidden"
            aria-label="Ouvrir le menu"
            @click="menuOuvert = true"
          >
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" class="h-5 w-5">
              <path d="M3.5 6h13M3.5 10h13M3.5 14h13" />
            </svg>
          </button>

          <select
            v-if="contextes.length > 0"
            :value="contexteActif?.entreprise.id"
            class="max-w-[14rem] truncate rounded-md border border-border bg-surface px-2 py-1.5 text-sm text-text sm:max-w-xs"
            @change="surChangementEntreprise"
          >
            <option v-for="c in contextes" :key="c.entreprise.id" :value="c.entreprise.id">
              {{ c.entreprise.raison_sociale }}
            </option>
          </select>
        </div>

        <NotificationCloche v-if="aPermission('notification.consulter')" />
      </header>

      <main class="flex-1 p-4 sm:p-6">
        <router-view />
      </main>
    </div>
  </div>
</template>