<script setup lang="ts">
/**
 * Page unique du portail client : documents que le cabinet a rendus
 * visibles (téléchargement), et mes demandes de documents (création +
 * suivi de statut). Pas d'édition ni de suppression ici — ce module est
 * volontairement en lecture seule côté client pour les documents (voir
 * la note de tête de fichier de service.py côté backend) ; seule une
 * nouvelle demande peut être créée.
 */
import { computed, reactive, ref } from "vue";

import { useAuth } from "@/core/auth/useAuth";
import { messageErreur } from "@/core/api/erreurs";
import BaseDataTable, { type ColonneTable } from "@/core/ui/BaseDataTable.vue";
import { formaterDate } from "@/core/ui/formatage";
import StatutBadge from "@/core/ui/StatutBadge.vue";
import type { Document } from "@/modules/documents/types";
import { useCompteurNotifications } from "@/modules/notifications/api";
import FilCommentaires from "./FilCommentaires.vue";
import {
  telechargerDocumentVisible,
  useDocumentsVisibles,
  useListeDemandes,
  useMutationsDemandes,
  type FiltresDemandes,
  type FiltresDocumentsVisibles,
} from "./api";
import type { DemandeDocument } from "./types";

const { contexteActif, utilisateur, aPermission } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

// --- Documents partagés ---

const filtresDocuments = reactive<FiltresDocumentsVisibles>({
  categorie: null,
  exerciceId: null,
  dossierPermanentSeulement: false,
});
const { data: documents, isLoading: chargementDocuments } = useDocumentsVisibles(
  entrepriseId,
  computed(() => filtresDocuments),
);

function formaterTaille(octets: number): string {
  if (octets < 1024) return `${octets} o`;
  if (octets < 1024 * 1024) return `${(octets / 1024).toFixed(1)} Ko`;
  return `${(octets / (1024 * 1024)).toFixed(1)} Mo`;
}

const colonnesDocuments: ColonneTable<Document>[] = [
  { cle: "nom_fichier", libelle: "Fichier" },
  { cle: "categorie", libelle: "Catégorie" },
  { cle: "taille_octets", libelle: "Taille" },
  { cle: "date_document", libelle: "Date" },
];

async function telecharger(document: Document): Promise<void> {
  await telechargerDocumentVisible(entrepriseId, document);
}

// --- Tableau de bord client ---
// Pas de nouveau backend : des compteurs calculés à partir des données déjà
// chargées par cette page (demandes, documents) et du compteur de
// notifications non lues de l'Étape 3. Pas de reprise des indicateurs
// comptables (trésorerie, etc.), déjà couverts par le tableau de bord
// Pilotage et hors permission client.
const { data: compteurNotifications } = useCompteurNotifications(entrepriseId);
// Compteur indépendant du filtre de statut choisi plus bas dans la page
// (sinon le nombre affiché varierait avec un filtre qui n'a rien à voir
// avec le tableau de bord).
const { data: demandesEnAttente } = useListeDemandes(
  entrepriseId,
  computed(() => ({ statut: "en_attente", mesDemandesSeulement: true })),
);

// --- Mes demandes ---

const filtresDemandes = reactive<FiltresDemandes>({ statut: null, mesDemandesSeulement: true });
const { data: demandes, isLoading: chargementDemandes } = useListeDemandes(
  entrepriseId,
  computed(() => filtresDemandes),
);
const { creer } = useMutationsDemandes(entrepriseId);

const colonnesDemandes: ColonneTable<DemandeDocument>[] = [
  { cle: "libelle", libelle: "Demande" },
  { cle: "statut", libelle: "Statut" },
  { cle: "reponse", libelle: "Réponse du cabinet" },
  { cle: "cree_le", libelle: "Créée le" },
];

const libellesStatut: Record<string, string> = {
  en_attente: "En attente",
  traitee: "Traitée",
  refusee: "Refusée",
};
const tonalitesStatut: Record<string, "info" | "succes" | "danger"> = {
  en_attente: "info",
  traitee: "succes",
  refusee: "danger",
};

const formulaireOuvert = ref(false);
const formulaire = reactive({ libelle: "", description: "" });
const erreur = ref<string | null>(null);

async function soumettre(): Promise<void> {
  erreur.value = null;
  try {
    await creer.mutateAsync({ libelle: formulaire.libelle, description: formulaire.description || null });
    formulaireOuvert.value = false;
    formulaire.libelle = "";
    formulaire.description = "";
  } catch (e) {
    erreur.value = messageErreur(e);
  }
}

// --- Échanges sur une demande ---

const demandeOuverte = ref<DemandeDocument | null>(null);
function ouvrirEchanges(demande: DemandeDocument): void {
  demandeOuverte.value = demande;
}
</script>

<template>
  <div class="space-y-8">
    <div>
      <h1 class="text-lg font-semibold text-text">Portail client</h1>
      <p class="mt-1 text-sm text-text-muted">
        Bonjour {{ utilisateur?.prenom }}, retrouvez ici les documents partagés par votre cabinet et vos demandes.
      </p>
    </div>

    <section class="grid grid-cols-1 gap-4 sm:grid-cols-3">
      <div class="rounded-lg border border-border bg-surface p-4">
        <p class="text-xs font-medium uppercase text-text-muted">Demandes en attente</p>
        <p class="mt-1 text-2xl font-semibold text-text">{{ demandesEnAttente?.length ?? 0 }}</p>
      </div>
      <div class="rounded-lg border border-border bg-surface p-4">
        <p class="text-xs font-medium uppercase text-text-muted">Documents disponibles</p>
        <p class="mt-1 text-2xl font-semibold text-text">{{ documents?.length ?? 0 }}</p>
      </div>
      <div v-if="aPermission('notification.consulter')" class="rounded-lg border border-border bg-surface p-4">
        <p class="text-xs font-medium uppercase text-text-muted">Notifications non lues</p>
        <p class="mt-1 text-2xl font-semibold text-text">{{ compteurNotifications?.non_lues ?? 0 }}</p>
      </div>
    </section>

    <section class="space-y-3">
      <h2 class="text-base font-semibold text-text">Documents partagés</h2>
      <div class="flex flex-wrap items-center gap-4">
        <input
          v-model="filtresDocuments.categorie"
          placeholder="Filtrer par catégorie"
          class="rounded-md border border-border px-3 py-2 text-sm text-text"
        />
        <label class="flex items-center gap-2 text-sm text-text-muted">
          <input v-model="filtresDocuments.dossierPermanentSeulement" type="checkbox" />
          Dossier permanent seulement
        </label>
      </div>
      <BaseDataTable
        :colonnes="colonnesDocuments"
        :lignes="documents ?? []"
        :chargement="chargementDocuments"
        message-vide="Aucun document partagé pour le moment."
      >
        <template #cell-taille_octets="{ valeur }">{{ formaterTaille(valeur as number) }}</template>
        <template #cell-date_document="{ ligne, valeur }">
          <div class="flex items-center gap-2">
            <span class="text-text">{{ valeur ?? "—" }}</span>
            <button type="button" class="text-xs text-primary hover:underline" @click="telecharger(ligne)">
              Télécharger
            </button>
          </div>
        </template>
      </BaseDataTable>
    </section>

    <section class="space-y-3">
      <div class="flex items-center justify-between">
        <h2 class="text-base font-semibold text-text">Mes demandes de documents</h2>
        <button
          type="button"
          class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover"
          @click="formulaireOuvert = !formulaireOuvert"
        >
          Nouvelle demande
        </button>
      </div>

      <form
        v-if="formulaireOuvert"
        class="space-y-4 rounded-lg border border-border bg-surface p-6"
        @submit.prevent="soumettre"
      >
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Que souhaitez-vous recevoir ?</label>
          <input v-model="formulaire.libelle" required minlength="2" maxlength="255" placeholder="ex: Mon dernier bilan" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Précisions (optionnel)</label>
          <input v-model="formulaire.description" maxlength="500" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <p v-if="erreur" class="text-sm text-danger">{{ erreur }}</p>
        <div class="flex justify-end gap-2">
          <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted" @click="formulaireOuvert = false">
            Annuler
          </button>
          <button type="submit" :disabled="creer.isPending.value" class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60">
            Envoyer
          </button>
        </div>
      </form>

      <p class="text-xs text-text-muted">Cliquer sur une demande ouvre les échanges avec le cabinet.</p>

      <BaseDataTable
        :colonnes="colonnesDemandes"
        :lignes="demandes ?? []"
        :chargement="chargementDemandes"
        message-vide="Aucune demande pour le moment."
        @ligne-cliquee="ouvrirEchanges"
      >
        <template #cell-statut="{ valeur }">
          <StatutBadge :libelle="libellesStatut[valeur as string]" :tonalite="tonalitesStatut[valeur as string]" />
        </template>
        <template #cell-reponse="{ valeur }">{{ valeur ?? "—" }}</template>
        <template #cell-cree_le="{ valeur }">{{ formaterDate(valeur as string) }}</template>
      </BaseDataTable>

      <div v-if="demandeOuverte" class="space-y-2">
        <div class="flex justify-end">
          <button type="button" class="text-sm text-text-muted hover:underline" @click="demandeOuverte = null">
            Fermer
          </button>
        </div>
        <FilCommentaires :entreprise-id="entrepriseId" :demande="demandeOuverte" />
      </div>
    </section>
  </div>
</template>