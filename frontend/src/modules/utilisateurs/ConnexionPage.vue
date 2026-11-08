<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useAuth } from "@/core/auth/useAuth";
import logoMLexpert from "@/assets/logo-mlexpert.png";

const { connecter, contexteActif } = useAuth();
const route = useRoute();
const router = useRouter();

const email = ref("");
const motDePasse = ref("");
const erreur = ref<string | null>(null);
const enEnvoi = ref(false);

async function soumettre(): Promise<void> {
  erreur.value = null;
  enEnvoi.value = true;
  try {
    await connecter(email.value, motDePasse.value);
    // "suite" vient du garde de navigation (voir router/index.ts) quand une
    // page protégée a renvoyé ici faute de session — y compris "/" lui-même
    // pour une première visite non connectée, donc ce n'est une vraie
    // redirection explicite que si ça pointe ailleurs que la racine.
    const suite = route.query.suite as string | undefined;
    if (suite && suite !== "/") {
      router.push(suite);
      return;
    }
    // Pas de redirection explicite (première connexion, ou suite="/") : un utilisateur
    // dont le rôle n'a que des permissions portail_client.* (voir la note
    // de tête de fichier de service.py côté backend — un client est un
    // Utilisateur comme un autre, distingué par son rôle) va vers le
    // portail client plutôt que l'espace cabinet.
    const permissions = contexteActif.value?.codes_permissions ?? [];
    const estClient =
      permissions.some((c) => c.startsWith("portail_client.")) &&
      permissions.every((c) => c.startsWith("portail_client."));
    router.push(estClient ? { name: "portail.accueil" } : "/");
  } catch {
    erreur.value = "Email ou mot de passe incorrect.";
  } finally {
    enEnvoi.value = false;
  }
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-surface-muted">
    <form
      class="w-full max-w-sm space-y-4 rounded-lg border border-border bg-surface p-8 shadow-sm"
      @submit.prevent="soumettre"
    >
      <img :src="logoMLexpert" alt="MLexpert" class="mx-auto h-12 w-auto" />

      <div>
        <label class="mb-1 block text-sm font-medium text-text" for="email">Email</label>
        <input
          id="email"
          v-model="email"
          type="email"
          required
          autocomplete="username"
          class="w-full rounded-md border border-border px-3 py-2 text-text focus:outline-2 focus:outline-primary"
        />
      </div>

      <div>
        <label class="mb-1 block text-sm font-medium text-text" for="mot-de-passe">
          Mot de passe
        </label>
        <input
          id="mot-de-passe"
          v-model="motDePasse"
          type="password"
          required
          autocomplete="current-password"
          class="w-full rounded-md border border-border px-3 py-2 text-text focus:outline-2 focus:outline-primary"
        />
      </div>

      <p v-if="erreur" class="text-sm text-danger">{{ erreur }}</p>

      <button
        type="submit"
        :disabled="enEnvoi"
        class="w-full rounded-md bg-primary px-4 py-2 font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60"
      >
        {{ enEnvoi ? "Connexion..." : "Se connecter" }}
      </button>
    </form>
  </div>
</template>