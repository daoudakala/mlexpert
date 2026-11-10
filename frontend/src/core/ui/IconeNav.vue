<script setup lang="ts">
/**
 * Icônes du menu latéral de AppLayout.vue — formes géométriques simples
 * (lignes droites, cercles, rectangles), dessinées à la main plutôt que
 * via une librairie externe (aucune n'est installée dans ce projet).
 * Une valeur de `nom` non reconnue n'affiche rien plutôt que de lever une
 * erreur : un oubli de mise à jour de ce fichier ne casse jamais la page.
 */
defineProps<{ nom: string }>();
</script>

<template>
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 20 20"
    fill="none"
    stroke="currentColor"
    stroke-width="1.6"
    stroke-linecap="round"
    stroke-linejoin="round"
    class="h-4 w-4 shrink-0"
  >
    <template v-if="nom === 'accueil'">
      <path d="M3 9.5 10 4l7 5.5" />
      <path d="M5 8.5V16a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V8.5" />
      <path d="M8 17v-4h4v4" />
    </template>

    <template v-else-if="nom === 'tiers'">
      <circle cx="7" cy="7" r="2.5" />
      <path d="M2.5 17c0-3 2-4.8 4.5-4.8s4.5 1.8 4.5 4.8" />
      <circle cx="15" cy="7.5" r="2" />
      <path d="M12.3 17c.2-2.3 1.5-3.8 2.7-3.8 1.6 0 3 1.5 3.3 3.8" />
    </template>

    <template v-else-if="nom === 'tresorerie'">
      <rect x="2.5" y="6" width="15" height="8" rx="1.2" />
      <circle cx="10" cy="10" r="2" />
    </template>

    <template v-else-if="nom === 'plan-comptable'">
      <path d="M4 4.5h6a2 2 0 0 1 2 2v10a2 2 0 0 0-2-2H4V4.5Z" />
      <path d="M16 4.5h-6a2 2 0 0 0-2 2v10a2 2 0 0 1 2-2h6V4.5Z" />
    </template>

    <template v-else-if="nom === 'journaux'">
      <rect x="4" y="3" width="12" height="14" rx="1.2" />
      <line x1="6.5" y1="7" x2="13.5" y2="7" />
      <line x1="6.5" y1="10" x2="13.5" y2="10" />
      <line x1="6.5" y1="13" x2="11" y2="13" />
    </template>

    <template v-else-if="nom === 'ecritures'">
      <path d="m4 16 1-3.5L13 4.5l2.5 2.5L7.5 15 4 16Z" />
      <line x1="12" y1="5.5" x2="14.5" y2="8" />
    </template>

    <template v-else-if="nom === 'modeles-ecriture'">
      <rect x="3" y="5" width="9" height="11" rx="1" />
      <rect x="7" y="2.5" width="9" height="11" rx="1" />
    </template>

    <template v-else-if="nom === 'lettrage'">
      <rect x="3" y="7" width="7" height="6" rx="3" />
      <rect x="9" y="7" width="7" height="6" rx="3" />
    </template>

    <template v-else-if="nom === 'ecritures-recurrentes'">
      <path d="M15.5 8a5.5 5.5 0 1 0-1.2 6.2" />
      <path d="M15.5 4.5V8h-3.5" />
    </template>

    <template v-else-if="nom === 'immobilisations'">
      <rect x="4" y="3" width="12" height="14" rx="1" />
      <rect x="6.5" y="6" width="1.8" height="1.8" />
      <rect x="11.7" y="6" width="1.8" height="1.8" />
      <rect x="6.5" y="10" width="1.8" height="1.8" />
      <rect x="11.7" y="10" width="1.8" height="1.8" />
      <rect x="8.5" y="13.5" width="3" height="3.5" />
    </template>

    <template v-else-if="nom === 'provisions'">
      <path d="M10 2.5 16 4.7v4.8c0 4-2.5 7-6 8-3.5-1-6-4-6-8V4.7Z" />
    </template>

    <template v-else-if="nom === 'regularisations'">
      <line x1="10" y1="3" x2="10" y2="16" />
      <line x1="4" y1="6" x2="16" y2="6" />
      <path d="M4 6 1.5 11a2.5 2.5 0 0 0 5 0Z" />
      <path d="M16 6l-2.5 5a2.5 2.5 0 0 0 5 0Z" />
      <line x1="7" y1="17" x2="13" y2="17" />
    </template>

    <template v-else-if="nom === 'documents'">
      <path d="M3 6a1 1 0 0 1 1-1h4l1.5 2H16a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6Z" />
    </template>

    <template v-else-if="nom === 'interlocuteurs'">
      <rect x="3" y="4.5" width="14" height="11" rx="1.2" />
      <circle cx="7.2" cy="9" r="1.6" />
      <path d="M4.8 13.2c.3-1.6 1.3-2.4 2.4-2.4s2.1.8 2.4 2.4" />
      <line x1="11.5" y1="8" x2="14.5" y2="8" />
      <line x1="11.5" y1="10.5" x2="14.5" y2="10.5" />
    </template>

    <template v-else-if="nom === 'stocks'">
      <path d="M10 3 16.5 6.5v7L10 17l-6.5-3.5v-7Z" />
      <path d="M3.5 6.5 10 10l6.5-3.5" />
      <line x1="10" y1="10" x2="10" y2="17" />
    </template>

    <template v-else-if="nom === 'dashboards'">
      <line x1="4.5" y1="16" x2="4.5" y2="11" />
      <line x1="9" y1="16" x2="9" y2="7" />
      <line x1="13.5" y1="16" x2="13.5" y2="9.5" />
      <line x1="2.5" y1="16" x2="17.5" y2="16" />
    </template>

    <template v-else-if="nom === 'portail-client'">
      <path d="M3 5.5a1.5 1.5 0 0 1 1.5-1.5h11a1.5 1.5 0 0 1 1.5 1.5v6a1.5 1.5 0 0 1-1.5 1.5H9l-3.5 3v-3H4.5A1.5 1.5 0 0 1 3 11.5Z" />
    </template>

    <template v-else-if="nom === 'journal-activite'">
      <rect x="4.5" y="4" width="11" height="13" rx="1.2" />
      <rect x="7.5" y="2.5" width="5" height="2.5" rx="0.8" />
      <line x1="6.5" y1="9" x2="13.5" y2="9" />
      <line x1="6.5" y1="12" x2="13.5" y2="12" />
      <line x1="6.5" y1="15" x2="11" y2="15" />
    </template>

    <template v-else-if="nom === 'exercices'">
      <rect x="3.5" y="4.5" width="13" height="12" rx="1.2" />
      <line x1="3.5" y1="8" x2="16.5" y2="8" />
      <line x1="7" y1="2.5" x2="7" y2="5.5" />
      <line x1="13" y1="2.5" x2="13" y2="5.5" />
    </template>

    <template v-else-if="nom === 'affectations'">
      <circle cx="6" cy="10" r="3" />
      <line x1="8.8" y1="10" x2="17" y2="10" />
      <line x1="14" y1="10" x2="14" y2="12.5" />
      <line x1="16.5" y1="10" x2="16.5" y2="12" />
    </template>

    <template v-else-if="nom === 'employes'">
      <circle cx="10" cy="7" r="2.8" />
      <path d="M4.5 17c.5-3.8 3-5.8 5.5-5.8s5 2 5.5 5.8" />
    </template>

    <template v-else-if="nom === 'rubriques-paie'">
      <line x1="4" y1="6" x2="16" y2="6" />
      <line x1="4" y1="10" x2="16" y2="10" />
      <line x1="4" y1="14" x2="11" y2="14" />
      <circle cx="14.5" cy="14" r="1.2" />
    </template>

    <template v-else-if="nom === 'bulletins-paie'">
      <path d="M5 3.5h10v13l-1.5-1-1.5 1-1.5-1-1.5 1-1.5-1-1.5 1-1.5-1Z" />
      <line x1="7" y1="7" x2="13" y2="7" />
      <line x1="7" y1="10" x2="13" y2="10" />
    </template>

    <template v-else-if="nom === 'mon-profil'">
      <circle cx="10" cy="10" r="7" />
      <circle cx="10" cy="8" r="2" />
      <path d="M5.5 15.2c.8-2.3 2.5-3.5 4.5-3.5s3.7 1.2 4.5 3.5" />
    </template>

    <template v-else-if="nom === 'notifications'">
      <path d="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0" transform="translate(-1 -1) scale(0.83)" />
    </template>

    <template v-else-if="nom === 'entreprises'">
      <rect x="3.5" y="7" width="13" height="9" rx="1.2" />
      <path d="M7.5 7V5.5a1.5 1.5 0 0 1 1.5-1.5h2a1.5 1.5 0 0 1 1.5 1.5V7" />
      <line x1="3.5" y1="10.5" x2="16.5" y2="10.5" />
    </template>

    <template v-else-if="nom === 'utilisateurs-admin'">
      <circle cx="9" cy="8" r="2.5" />
      <path d="M4.5 16.5c.4-3 2.2-4.8 4.5-4.8s4.1 1.8 4.5 4.8" />
      <circle cx="15.5" cy="14.5" r="1.8" />
      <line x1="15.5" y1="11.7" x2="15.5" y2="12.4" />
      <line x1="15.5" y1="16.6" x2="15.5" y2="17.3" />
      <line x1="12.7" y1="14.5" x2="13.4" y2="14.5" />
      <line x1="17.6" y1="14.5" x2="18.3" y2="14.5" />
    </template>

    <template v-else-if="nom === 'roles-admin'">
      <path d="M10 2.5 16 4.7v4.8c0 4-2.5 7-6 8-3.5-1-6-4-6-8V4.7Z" />
      <path d="M7.5 10 9.3 11.8 12.5 8.2" />
    </template>

    <template v-else-if="nom === 'tableau-bord'">
      <rect x="3" y="3" width="6" height="7" rx="1.2" />
      <rect x="11" y="3" width="6" height="4" rx="1.2" />
      <rect x="11" y="9" width="6" height="8" rx="1.2" />
      <rect x="3" y="12" width="6" height="5" rx="1.2" />
    </template>

    <template v-else-if="nom === 'grand-livre'">
      <path d="M4.5 3.5h9a1.5 1.5 0 0 1 1.5 1.5v11.5H6a1.5 1.5 0 0 1-1.5-1.5Z" />
      <path d="M4.5 15a1.5 1.5 0 0 1 1.5-1.5h9" />
      <line x1="7.5" y1="6.5" x2="12.5" y2="6.5" />
    </template>

    <template v-else-if="nom === 'balance'">
      <line x1="10" y1="3.5" x2="10" y2="16.5" />
      <line x1="6" y1="16.5" x2="14" y2="16.5" />
      <line x1="4" y1="6" x2="16" y2="6" />
      <path d="M4 6 2 11a2.5 2.5 0 0 0 4 0Z" />
      <path d="M16 6l-2 5a2.5 2.5 0 0 0 4 0Z" />
    </template>

    <template v-else-if="nom === 'fournisseurs'">
      <path d="M2.5 5.5h9v8h-9Z" />
      <path d="M11.5 8h3.2l2.3 2.6v2.9h-5.5Z" />
      <circle cx="6" cy="14.5" r="1.4" />
      <circle cx="14" cy="14.5" r="1.4" />
    </template>

    <template v-else-if="nom === 'parametres'">
      <line x1="3.5" y1="6" x2="16.5" y2="6" />
      <line x1="3.5" y1="10" x2="16.5" y2="10" />
      <line x1="3.5" y1="14" x2="16.5" y2="14" />
      <circle cx="7" cy="6" r="1.6" fill="currentColor" />
      <circle cx="13" cy="10" r="1.6" fill="currentColor" />
      <circle cx="8.5" cy="14" r="1.6" fill="currentColor" />
    </template>
  </svg>
</template>