<script setup lang="ts">
/**
 * Page d'accueil (route `accueil`). Son contenu est remplacé par celui du
 * tableau de bord (ReportingPage) pour les personnes qui ont la permission
 * `dashboard.consulter`, afin qu'elles aient une vue d'ensemble dès la
 * connexion. Le message de bienvenue simple reste le contenu de repli pour
 * les comptes qui n'ont pas cette permission (ex. portail client) — la route
 * `accueil` ne doit JAMAIS porter elle-même une exigence de permission, car
 * le garde de navigation (router/index.ts) y redirige en cas de refus de
 * permission ; une boucle de redirection infinie s'ensuivrait sinon.
 */
import { useAuth } from "@/core/auth/useAuth";
import ReportingPage from "./ReportingPage.vue";

const { utilisateur, contexteActif, aPermission } = useAuth();
</script>

<template>
  <ReportingPage v-if="aPermission('dashboard.consulter')" />
  <div v-else>
    <h1 class="text-lg font-semibold text-text">
      Bonjour{{ utilisateur ? `, ${utilisateur.prenom}` : "" }}
    </h1>
    <p v-if="contexteActif" class="mt-1 text-sm text-text-muted">
      {{ contexteActif.entreprise.raison_sociale }} — rôle {{ contexteActif.role.libelle }}
    </p>
  </div>
</template>