<script setup lang="ts">
/**
 * Page unique du module : recherche dans le journal d'activité de
 * l'entreprise active, avec filtres et pagination simple (page suivante/
 * précédente via `limite`/`decalage`, pas de numérotation de pages — le
 * backend ne renvoie pas de total, voir router.py). Module 100% lecture
 * seule : aucune action de création/modification/suppression ici, le
 * journal ne s'écrit jamais depuis le frontend.
 */
import { computed, reactive, ref } from "vue";

import { useAuth } from "@/core/auth/useAuth";
import BaseDataTable, { type ColonneTable } from "@/core/ui/BaseDataTable.vue";
import { useJournalActivite, type FiltresJournalActivite } from "./api";
import type { EntreeJournalActivite } from "./types";

const { contexteActif } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const TAILLE_PAGE = 50;

const filtres = reactive<FiltresJournalActivite>({
  module: null,
  typeAction: null,
  typeObjet: null,
  depuis: null,
  jusquA: null,
  limite: TAILLE_PAGE,
  decalage: 0,
});
const { data: entrees, isLoading } = useJournalActivite(entrepriseId, computed(() => filtres));

function reinitialiserPagination(): void {
  filtres.decalage = 0;
}

function pagePrecedente(): void {
  filtres.decalage = Math.max(0, (filtres.decalage ?? 0) - TAILLE_PAGE);
}

function pageSuivante(): void {
  if ((entrees.value ?? []).length < TAILLE_PAGE) return;
  filtres.decalage = (filtres.decalage ?? 0) + TAILLE_PAGE;
}

const colonnes: ColonneTable<EntreeJournalActivite>[] = [
  { cle: "survenu_le", libelle: "Date" },
  { cle: "utilisateur_nom", libelle: "Auteur" },
  { cle: "module", libelle: "Module" },
  { cle: "type_action", libelle: "Action" },
  { cle: "type_objet", libelle: "Objet" },
  { cle: "description", libelle: "Description" },
];

function formaterDate(valeur: string): string {
  return new Date(valeur).toLocaleString("fr-FR");
}

/** "Prénom Nom", ou un intitulé explicite quand aucun utilisateur n'est
 * rattaché (événement système) ou que le compte a depuis été supprimé —
 * voir la note de tête de fichier de models.py côté backend. */
function nomAuteur(entree: EntreeJournalActivite): string {
  if (!entree.utilisateur_id) return "Système";
  if (!entree.utilisateur_nom) return "Compte supprimé";
  return `${entree.utilisateur_prenom} ${entree.utilisateur_nom}`;
}

// --- Détail d'une entrée (valeurs avant/après) ---

const entreeOuverte = ref<EntreeJournalActivite | null>(null);
function ouvrirDetail(entree: EntreeJournalActivite): void {
  if (!entree.valeurs_avant && !entree.valeurs_apres) return;
  entreeOuverte.value = entree;
}
</script>

<template>
  <div class="space-y-4">
    <h1 class="text-lg font-semibold text-text">Journal d'activité</h1>

    <div class="flex flex-wrap items-center gap-4">
      <input
        v-model="filtres.module"
        placeholder="Module (ex: comptabilite)"
        class="rounded-md border border-border px-3 py-2 text-sm text-text"
        @change="reinitialiserPagination"
      />
      <input
        v-model="filtres.typeAction"
        placeholder="Action (ex: valider)"
        class="rounded-md border border-border px-3 py-2 text-sm text-text"
        @change="reinitialiserPagination"
      />
      <input
        v-model="filtres.typeObjet"
        placeholder="Type d'objet (ex: Ecriture)"
        class="rounded-md border border-border px-3 py-2 text-sm text-text"
        @change="reinitialiserPagination"
      />
      <label class="flex items-center gap-2 text-sm text-text-muted">
        Depuis
        <input
          v-model="filtres.depuis"
          type="datetime-local"
          class="rounded-md border border-border px-3 py-2 text-sm text-text"
          @change="reinitialiserPagination"
        />
      </label>
      <label class="flex items-center gap-2 text-sm text-text-muted">
        Jusqu'à
        <input
          v-model="filtres.jusquA"
          type="datetime-local"
          class="rounded-md border border-border px-3 py-2 text-sm text-text"
          @change="reinitialiserPagination"
        />
      </label>
    </div>

    <p class="text-xs text-text-muted">Cliquer sur une ligne affiche le détail quand des valeurs avant/après ont été conservées.</p>

    <BaseDataTable
      :colonnes="colonnes"
      :lignes="entrees ?? []"
      :chargement="isLoading"
      message-vide="Aucune entrée pour ces filtres."
      @ligne-cliquee="ouvrirDetail"
    >
      <template #cell-survenu_le="{ valeur }">{{ formaterDate(valeur as string) }}</template>
      <template #cell-utilisateur_nom="{ ligne }">{{ nomAuteur(ligne) }}</template>
      <template #cell-type_objet="{ valeur }">{{ valeur ?? "—" }}</template>
      <template #cell-description="{ valeur }">{{ valeur ?? "—" }}</template>
    </BaseDataTable>

    <div class="flex items-center justify-between">
      <button
        type="button"
        class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted disabled:opacity-40"
        :disabled="(filtres.decalage ?? 0) === 0"
        @click="pagePrecedente"
      >
        ← Précédent
      </button>
      <button
        type="button"
        class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted disabled:opacity-40"
        :disabled="(entrees ?? []).length < TAILLE_PAGE"
        @click="pageSuivante"
      >
        Suivant →
      </button>
    </div>

    <div v-if="entreeOuverte" class="space-y-3 rounded-lg border border-border bg-surface p-6">
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-base font-semibold text-text">Détail — {{ entreeOuverte.description ?? entreeOuverte.type_action }}</h2>
          <p class="text-xs text-text-muted">
            {{ nomAuteur(entreeOuverte) }}<span v-if="entreeOuverte.utilisateur_email"> — {{ entreeOuverte.utilisateur_email }}</span>
          </p>
        </div>
        <button type="button" class="text-sm text-text-muted hover:underline" @click="entreeOuverte = null">
          Fermer
        </button>
      </div>
      <div class="grid grid-cols-2 gap-4">
        <div v-if="entreeOuverte.valeurs_avant">
          <p class="mb-1 text-xs font-medium text-text-muted">Avant</p>
          <pre class="overflow-auto rounded-md bg-surface-muted p-3 text-xs text-text">{{ JSON.stringify(entreeOuverte.valeurs_avant, null, 2) }}</pre>
        </div>
        <div v-if="entreeOuverte.valeurs_apres">
          <p class="mb-1 text-xs font-medium text-text-muted">Après</p>
          <pre class="overflow-auto rounded-md bg-surface-muted p-3 text-xs text-text">{{ JSON.stringify(entreeOuverte.valeurs_apres, null, 2) }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>
