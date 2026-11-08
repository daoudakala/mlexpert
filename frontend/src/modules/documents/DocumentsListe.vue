<script setup lang="ts">
/**
 * Page unique pour tout le module : liste + dépôt + édition des métadonnées
 * + téléchargement + visibilité client + suppression. Le volume de
 * fonctionnalités reste limité (une seule table côté backend, pas de
 * sous-objets) — pas besoin d'éclater en plusieurs routes comme pour
 * tiers/tresorerie/comptabilite/immobilisations.
 */
import { computed, reactive, ref } from "vue";

import { useAuth } from "@/core/auth/useAuth";
import { useExercices } from "@/modules/exercices/api";
import { messageErreur } from "@/core/api/erreurs";
import BaseDataTable, { type ColonneTable } from "@/core/ui/BaseDataTable.vue";
import ConfirmDialog from "@/core/ui/ConfirmDialog.vue";
import StatutBadge from "@/core/ui/StatutBadge.vue";
import {
  telechargerDocument,
  useListeDocuments,
  useMutationsDocuments,
  type FiltresDocuments,
} from "./api";
import { CATEGORIES_DOCUMENT, type CategorieDocument, type Document } from "./types";

function libelleCategorie(valeur: string): string {
  return CATEGORIES_DOCUMENT.find((c) => c.valeur === valeur)?.libelle ?? valeur;
}

const { contexteActif, aPermission } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const { data: exercices } = useExercices(entrepriseId);

const filtres = reactive<FiltresDocuments>({ categorie: null, exerciceId: null, dossierPermanentSeulement: false });
const { data: documents, isLoading } = useListeDocuments(entrepriseId, computed(() => filtres));
const { deposer, modifier, definirVisibiliteClient, supprimer, detacherEcriture } = useMutationsDocuments(entrepriseId);

async function detacher(document: Document): Promise<void> {
  await detacherEcriture.mutateAsync(document.id);
}

function formaterTaille(octets: number): string {
  if (octets < 1024) return `${octets} o`;
  if (octets < 1024 * 1024) return `${(octets / 1024).toFixed(1)} Ko`;
  return `${(octets / (1024 * 1024)).toFixed(1)} Mo`;
}

const colonnes: ColonneTable<Document>[] = [
  { cle: "nom_fichier", libelle: "Fichier" },
  { cle: "categorie", libelle: "Catégorie" },
  { cle: "taille_octets", libelle: "Taille" },
  { cle: "exercice_id", libelle: "Dossier" },
  { cle: "ecriture_id", libelle: "Pièce justificative" },
  { cle: "visible_client", libelle: "Visible client" },
  { cle: "date_expiration", libelle: "Expiration" },
];

// --- Dépôt ---

const depotOuvert = ref(false);
const depot = reactive({
  fichier: null as File | null,
  categorie: "" as CategorieDocument | "",
  description: "",
  date_document: "",
  date_expiration: "",
  exercice_id: "",
});
const erreurDepot = ref<string | null>(null);

function surChoixFichier(evenement: Event): void {
  depot.fichier = (evenement.target as HTMLInputElement).files?.[0] ?? null;
}

async function soumettreDepot(): Promise<void> {
  erreurDepot.value = null;
  if (!depot.fichier) {
    erreurDepot.value = "Choisis un fichier à déposer.";
    return;
  }
  if (!depot.categorie) {
    erreurDepot.value = "Choisis une catégorie.";
    return;
  }
  try {
    await deposer.mutateAsync({
      fichier: depot.fichier,
      categorie: depot.categorie,
      description: depot.description || null,
      date_document: depot.date_document || null,
      date_expiration: depot.date_expiration || null,
      exercice_id: depot.exercice_id || null,
    });
    depotOuvert.value = false;
    depot.fichier = null;
    depot.categorie = "";
    depot.description = "";
    depot.date_document = "";
    depot.date_expiration = "";
    depot.exercice_id = "";
  } catch (e) {
    erreurDepot.value = messageErreur(e);
  }
}

// --- Édition ---

const documentEnEdition = ref<Document | null>(null);
const edition = reactive({
  categorie: "" as CategorieDocument | "",
  description: "",
  date_document: "",
  date_expiration: "",
});
const erreurEdition = ref<string | null>(null);

function ouvrirEdition(document: Document): void {
  documentEnEdition.value = document;
  // Un document déposé avant l'introduction de la liste fermée peut
  // porter une valeur libre (voir le docstring de models.py côté
  // backend) : on retombe sur "autre" plutôt que de soumettre une
  // valeur qui échouerait à la validation.
  const categorieConnue = CATEGORIES_DOCUMENT.find((c) => c.valeur === document.categorie);
  edition.categorie = categorieConnue ? categorieConnue.valeur : "autre";
  edition.description = document.description ?? "";
  edition.date_document = document.date_document ?? "";
  edition.date_expiration = document.date_expiration ?? "";
  erreurEdition.value = null;
}

async function enregistrerEdition(): Promise<void> {
  if (!documentEnEdition.value) return;
  erreurEdition.value = null;
  try {
    await modifier.mutateAsync({
      id: documentEnEdition.value.id,
      donnees: {
        categorie: edition.categorie || undefined,
        description: edition.description || null,
        date_document: edition.date_document || null,
        date_expiration: edition.date_expiration || null,
      },
    });
    documentEnEdition.value = null;
  } catch (e) {
    erreurEdition.value = messageErreur(e);
  }
}

async function basculerVisibiliteClient(document: Document): Promise<void> {
  await definirVisibiliteClient.mutateAsync({ id: document.id, visibleClient: !document.visible_client });
}

// `documentASupprimer` garde la ligne ciblée, `confirmationSuppressionOuverte`
// ne pilote que la visibilité du dialogue : les deux sont volontairement
// séparés, pour ne jamais perdre le document au clic sur "Confirmer"
// (ConfirmDialog ferme le dialogue — donc émet update:ouvert=false — AVANT
// d'émettre "confirmer" ; si un seul ref portait les deux rôles, un
// handler sur update:ouvert effacerait la cible avant que le gestionnaire
// de confirmation ne la lise).
const documentASupprimer = ref<Document | null>(null);
const confirmationSuppressionOuverte = ref(false);
function demanderSuppression(document: Document): void {
  documentASupprimer.value = document;
  confirmationSuppressionOuverte.value = true;
}
async function confirmerSuppression(): Promise<void> {
  if (!documentASupprimer.value) return;
  await supprimer.mutateAsync(documentASupprimer.value.id);
  documentASupprimer.value = null;
}

async function telecharger(document: Document): Promise<void> {
  await telechargerDocument(entrepriseId, document);
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-lg font-semibold text-text">Documents</h1>
      <button
        v-if="aPermission('document.creer')"
        type="button"
        class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover"
        @click="depotOuvert = !depotOuvert"
      >
        Déposer un document
      </button>
    </div>

    <div class="flex flex-wrap items-center gap-4">
      <select v-model="filtres.categorie" class="rounded-md border border-border px-3 py-2 text-sm text-text">
        <option :value="null">Toutes les catégories</option>
        <option v-for="c in CATEGORIES_DOCUMENT" :key="c.valeur" :value="c.valeur">{{ c.libelle }}</option>
      </select>
      <select v-model="filtres.exerciceId" class="rounded-md border border-border px-3 py-2 text-sm text-text">
        <option :value="null">Tous les exercices</option>
        <option v-for="e in exercices" :key="e.id" :value="e.id">{{ e.date_debut }} → {{ e.date_fin }}</option>
      </select>
      <label class="flex items-center gap-2 text-sm text-text-muted">
        <input v-model="filtres.dossierPermanentSeulement" type="checkbox" />
        Dossier permanent seulement
      </label>
    </div>

    <form v-if="depotOuvert" class="space-y-4 rounded-lg border border-border bg-surface p-6" @submit.prevent="soumettreDepot">
      <h2 class="text-base font-semibold text-text">Déposer un document</h2>
      <div>
        <label class="mb-1 block text-sm font-medium text-text">Fichier</label>
        <input type="file" required class="w-full text-sm text-text" @change="surChoixFichier" />
      </div>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Catégorie</label>
          <select v-model="depot.categorie" required class="w-full rounded-md border border-border px-3 py-2 text-text">
            <option value="" disabled>Choisir…</option>
            <option v-for="c in CATEGORIES_DOCUMENT" :key="c.valeur" :value="c.valeur">{{ c.libelle }}</option>
          </select>
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Exercice (optionnel — dossier annuel)</label>
          <select v-model="depot.exercice_id" class="w-full rounded-md border border-border px-3 py-2 text-text">
            <option value="">— Dossier permanent —</option>
            <option v-for="e in exercices" :key="e.id" :value="e.id">{{ e.date_debut }} → {{ e.date_fin }}</option>
          </select>
        </div>
      </div>
      <div>
        <label class="mb-1 block text-sm font-medium text-text">Description</label>
        <input v-model="depot.description" class="w-full rounded-md border border-border px-3 py-2 text-text" />
      </div>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Date du document</label>
          <input v-model="depot.date_document" type="date" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Date d'expiration</label>
          <input v-model="depot.date_expiration" type="date" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
      </div>
      <p v-if="erreurDepot" class="text-sm text-danger">{{ erreurDepot }}</p>
      <div class="flex justify-end gap-2">
        <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted" @click="depotOuvert = false">
          Annuler
        </button>
        <button type="submit" :disabled="deposer.isPending.value" class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60">
          {{ deposer.isPending.value ? "Dépôt..." : "Déposer" }}
        </button>
      </div>
    </form>

    <BaseDataTable
      :colonnes="colonnes"
      :lignes="documents ?? []"
      :chargement="isLoading"
      message-vide="Aucun document pour le moment."
      @ligne-cliquee="ouvrirEdition"
    >
      <template #cell-taille_octets="{ valeur }">{{ formaterTaille(valeur as number) }}</template>
      <template #cell-categorie="{ valeur }">{{ libelleCategorie(valeur as string) }}</template>
      <template #cell-exercice_id="{ valeur }">
        <StatutBadge :libelle="valeur ? 'Dossier annuel' : 'Dossier permanent'" tonalite="info" />
      </template>
      <template #cell-ecriture_id="{ ligne, valeur }">
        <div v-if="valeur" class="flex items-center gap-2">
          <StatutBadge libelle="Rattachée" tonalite="succes" />
          <button
            v-if="aPermission('document.modifier')"
            type="button"
            class="text-xs text-text-muted hover:underline"
            @click.stop="detacher(ligne)"
          >
            Détacher
          </button>
        </div>
        <span v-else class="text-text-muted">—</span>
      </template>
      <template #cell-visible_client="{ ligne }">
        <button
          type="button"
          class="text-xs"
          :class="ligne.visible_client ? 'text-success hover:underline' : 'text-text-muted hover:underline'"
          @click.stop="basculerVisibiliteClient(ligne)"
        >
          {{ ligne.visible_client ? "Visible" : "Masqué" }}
        </button>
      </template>
      <template #cell-date_expiration="{ ligne, valeur }">
        <div class="flex items-center gap-2">
          <span class="text-text">{{ valeur ?? "—" }}</span>
          <button type="button" class="text-xs text-primary hover:underline" @click.stop="telecharger(ligne)">
            Télécharger
          </button>
          <button
            v-if="aPermission('document.supprimer')"
            type="button"
            class="text-xs text-danger hover:underline"
            @click.stop="demanderSuppression(ligne)"
          >
            Supprimer
          </button>
        </div>
      </template>
    </BaseDataTable>

    <form
      v-if="documentEnEdition"
      class="space-y-4 rounded-lg border border-border bg-surface p-6"
      @submit.prevent="enregistrerEdition"
    >
      <h2 class="text-base font-semibold text-text">Modifier — {{ documentEnEdition.nom_fichier }}</h2>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Catégorie</label>
          <select v-model="edition.categorie" required class="w-full rounded-md border border-border px-3 py-2 text-text">
            <option v-for="c in CATEGORIES_DOCUMENT" :key="c.valeur" :value="c.valeur">{{ c.libelle }}</option>
          </select>
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Description</label>
          <input v-model="edition.description" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
      </div>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Date du document</label>
          <input v-model="edition.date_document" type="date" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Date d'expiration</label>
          <input v-model="edition.date_expiration" type="date" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
      </div>
      <p v-if="erreurEdition" class="text-sm text-danger">{{ erreurEdition }}</p>
      <div class="flex justify-end gap-2">
        <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted" @click="documentEnEdition = null">
          Annuler
        </button>
        <button type="submit" :disabled="modifier.isPending.value" class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60">
          Enregistrer
        </button>
      </div>
    </form>

    <ConfirmDialog
      v-model:ouvert="confirmationSuppressionOuverte"
      titre="Supprimer ce document ?"
      :message="`« ${documentASupprimer?.nom_fichier} » sera définitivement supprimé.`"
      libelle-confirmer="Supprimer"
      dangereux
      @confirmer="confirmerSuppression"
    />
  </div>
</template>