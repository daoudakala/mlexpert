<script setup lang="ts">
import { useRouter } from "vue-router";

import { useAuth } from "@/core/auth/useAuth";
import IconeNav from "@/core/ui/IconeNav.vue";
import NotificationCloche from "@/modules/notifications/NotificationCloche.vue";
import logoMLexpert from "@/assets/logo-mlexpert.png";

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
  <div class="flex min-h-screen flex-col">
    <header class="flex items-center justify-between border-b border-border bg-surface px-6 py-3">
      <div class="flex items-center gap-4">
        <img :src="logoMLexpert" alt="MLexpert" class="h-8 w-auto" />

        <select
          v-if="contextes.length > 0"
          :value="contexteActif?.entreprise.id"
          class="rounded-md border border-border bg-surface px-2 py-1 text-sm text-text"
          @change="surChangementEntreprise"
        >
          <option v-for="c in contextes" :key="c.entreprise.id" :value="c.entreprise.id">
            {{ c.entreprise.raison_sociale }}
          </option>
        </select>
      </div>

      <div class="flex items-center gap-3 text-sm text-text-muted">
        <NotificationCloche v-if="aPermission('notification.consulter')" />
        <span v-if="utilisateur">{{ utilisateur.prenom }} {{ utilisateur.nom }}</span>
        <button type="button" class="text-primary hover:underline" @click="surDeconnexion">
          Déconnexion
        </button>
      </div>
    </header>

    <div class="flex flex-1">
      <!-- Le menu latéral se construira module par module, piloté par
           contexteActif?.codes_permissions (cf. router/index.ts). -->
      <nav class="w-56 border-r border-border bg-surface p-4">
        <router-link
          :to="{ name: 'accueil' }"
          class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text hover:bg-surface-muted"
          active-class="bg-surface-muted font-medium"
        >
          <IconeNav nom="accueil" />
          Tableau de bord
        </router-link>
        <router-link
          v-if="aPermission('tiers.consulter')"
          :to="{ name: 'tiers.liste' }"
          class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text hover:bg-surface-muted"
          active-class="bg-surface-muted font-medium"
        >
          <IconeNav nom="tiers" />
          Tiers
        </router-link>
        <router-link
          v-if="aPermission('compte_bancaire.consulter')"
          :to="{ name: 'tresorerie.comptes-bancaires' }"
          class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text hover:bg-surface-muted"
          active-class="bg-surface-muted font-medium"
        >
          <IconeNav nom="tresorerie" />
          Trésorerie
        </router-link>
        <router-link
          v-if="aPermission('compte.consulter')"
          :to="{ name: 'comptabilite.comptes' }"
          class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text hover:bg-surface-muted"
          active-class="bg-surface-muted font-medium"
        >
          <IconeNav nom="plan-comptable" />
          Plan comptable
        </router-link>
        <router-link
          v-if="aPermission('journal.consulter')"
          :to="{ name: 'comptabilite.journaux' }"
          class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text hover:bg-surface-muted"
          active-class="bg-surface-muted font-medium"
        >
          <IconeNav nom="journaux" />
          Journaux
        </router-link>
        <router-link
          v-if="aPermission('ecriture.consulter')"
          :to="{ name: 'comptabilite.ecritures' }"
          class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text hover:bg-surface-muted"
          active-class="bg-surface-muted font-medium"
        >
          <IconeNav nom="ecritures" />
          Écritures
        </router-link>
        <router-link
          v-if="aPermission('modele_ecriture.consulter')"
          :to="{ name: 'comptabilite.modeles-ecriture' }"
          class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text hover:bg-surface-muted"
          active-class="bg-surface-muted font-medium"
        >
          <IconeNav nom="modeles-ecriture" />
          Modèles d'écriture
        </router-link>
        <router-link
          v-if="aPermission('ecriture.consulter')"
          :to="{ name: 'comptabilite.lettrage' }"
          class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text hover:bg-surface-muted"
          active-class="bg-surface-muted font-medium"
        >
          <IconeNav nom="lettrage" />
          Lettrage
        </router-link>
        <router-link
          v-if="aPermission('ecriture_recurrente.consulter')"
          :to="{ name: 'comptabilite.ecritures-recurrentes' }"
          class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text hover:bg-surface-muted"
          active-class="bg-surface-muted font-medium"
        >
          <IconeNav nom="ecritures-recurrentes" />
          Écritures récurrentes
        </router-link>
        <router-link
          v-if="aPermission('immobilisation.consulter')"
          :to="{ name: 'immobilisations.liste' }"
          class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text hover:bg-surface-muted"
          active-class="bg-surface-muted font-medium"
        >
          <IconeNav nom="immobilisations" />
          Immobilisations
        </router-link>
        <router-link
          v-if="aPermission('provision.consulter')"
          :to="{ name: 'provisions.liste' }"
          class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text hover:bg-surface-muted"
          active-class="bg-surface-muted font-medium"
        >
          <IconeNav nom="provisions" />
          Provisions
        </router-link>
        <router-link
          v-if="aPermission('regularisation.consulter')"
          :to="{ name: 'regularisations.liste' }"
          class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text hover:bg-surface-muted"
          active-class="bg-surface-muted font-medium"
        >
          <IconeNav nom="regularisations" />
          Régularisations (CCA/PCA)
        </router-link>
        <router-link
          v-if="aPermission('document.consulter')"
          :to="{ name: 'documents.liste' }"
          class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text hover:bg-surface-muted"
          active-class="bg-surface-muted font-medium"
        >
          <IconeNav nom="documents" />
          Documents
        </router-link>
        <router-link
          v-if="aPermission('interlocuteur.consulter')"
          :to="{ name: 'interlocuteurs.liste' }"
          class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text hover:bg-surface-muted"
          active-class="bg-surface-muted font-medium"
        >
          <IconeNav nom="interlocuteurs" />
          Interlocuteurs
        </router-link>
        <router-link
          v-if="aPermission('article.consulter')"
          :to="{ name: 'stocks.liste' }"
          class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text hover:bg-surface-muted"
          active-class="bg-surface-muted font-medium"
        >
          <IconeNav nom="stocks" />
          Stocks
        </router-link>
        <router-link
          v-if="aPermission('portail_client.consulter')"
          :to="{ name: 'portail_client.demandes' }"
          class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text hover:bg-surface-muted"
          active-class="bg-surface-muted font-medium"
        >
          <IconeNav nom="portail-client" />
          Demandes clients
        </router-link>
        <router-link
          v-if="aPermission('journal_activite.consulter')"
          :to="{ name: 'journal_activite.page' }"
          class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text hover:bg-surface-muted"
          active-class="bg-surface-muted font-medium"
        >
          <IconeNav nom="journal-activite" />
          Journal d'activité
        </router-link>
        <router-link
          v-if="aPermission('exercice.consulter')"
          :to="{ name: 'exercices.liste' }"
          class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text hover:bg-surface-muted"
          active-class="bg-surface-muted font-medium"
        >
          <IconeNav nom="exercices" />
          Exercices
        </router-link>
        <router-link
          v-if="aPermission('droits.consulter')"
          :to="{ name: 'droits.affectations' }"
          class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text hover:bg-surface-muted"
          active-class="bg-surface-muted font-medium"
        >
          <IconeNav nom="affectations" />
          Affectations
        </router-link>
        <router-link
          v-if="aPermission('employe.consulter')"
          :to="{ name: 'paie.employes' }"
          class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text hover:bg-surface-muted"
          active-class="bg-surface-muted font-medium"
        >
          <IconeNav nom="employes" />
          Employés
        </router-link>
        <router-link
          v-if="aPermission('rubrique_paie.consulter')"
          :to="{ name: 'paie.rubriques' }"
          class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text hover:bg-surface-muted"
          active-class="bg-surface-muted font-medium"
        >
          <IconeNav nom="rubriques-paie" />
          Rubriques de paie
        </router-link>
        <router-link
          v-if="aPermission('bulletin.consulter')"
          :to="{ name: 'paie.bulletins' }"
          class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text hover:bg-surface-muted"
          active-class="bg-surface-muted font-medium"
        >
          <IconeNav nom="bulletins-paie" />
          Bulletins de paie
        </router-link>

        <div class="my-3 border-t border-border" />
        <router-link
          :to="{ name: 'utilisateurs.mon-profil' }"
          class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text hover:bg-surface-muted"
          active-class="bg-surface-muted font-medium"
        >
          <IconeNav nom="mon-profil" />
          Mon profil
        </router-link>
        <router-link
          v-if="aPermission('notification.consulter')"
          :to="{ name: 'notifications.preferences' }"
          class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text hover:bg-surface-muted"
          active-class="bg-surface-muted font-medium"
        >
          <IconeNav nom="notifications" />
          Préférences de notification
        </router-link>

        <template v-if="estAdministrateurPlateforme">
          <p class="mt-3 px-3 text-xs font-semibold uppercase text-text-muted">Administration</p>
          <router-link
            :to="{ name: 'entreprises.liste' }"
            class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text hover:bg-surface-muted"
            active-class="bg-surface-muted font-medium"
          >
            <IconeNav nom="entreprises" />
            Entreprises
          </router-link>
          <router-link
            :to="{ name: 'utilisateurs.liste' }"
            class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text hover:bg-surface-muted"
            active-class="bg-surface-muted font-medium"
          >
            <IconeNav nom="utilisateurs-admin" />
            Utilisateurs
          </router-link>
          <router-link
            :to="{ name: 'droits.roles' }"
            class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text hover:bg-surface-muted"
            active-class="bg-surface-muted font-medium"
          >
            <IconeNav nom="roles-admin" />
            Rôles &amp; permissions
          </router-link>
        </template>
      </nav>

      <main class="flex-1 p-6">
        <router-view />
      </main>
    </div>
  </div>
</template>