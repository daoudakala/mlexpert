<script setup lang="ts">
/**
 * Vue cabinet du module portail_client : toutes les demandes de
 * documents de l'entreprise (pas seulement les siennes, contrairement à
 * PortailAccueil.vue — voir la note de tête de fichier de router.py sur
 * `mes_demandes_seulement`), avec traitement (lier un document déjà
 * visible client) ou refus (motif).
 *
 * Traiter une demande exige un document DÉJÀ marqué visible_client
 * (voir service.py backend : ça ne rend pas un document visible tout
 * seul) — la liste déroulante ne propose donc que ceux-là, filtrés
 * côté frontend depuis la liste complète des documents.
 */
import { computed, reactive, ref } from "vue";

import { useAuth } from "@/core/auth/useAuth";
import { messageErreur } from "@/core/api/erreurs";
import BaseDataTable, { type ColonneTable } from "@/core/ui/BaseDataTable.vue";
import { formaterDate } from "@/core/ui/formatage";
import StatutBadge from "@/core/ui/StatutBadge.vue";
import { useListeDocuments } from "@/modules/documents/api";
import FilCommentaires from "./FilCommentaires.vue";
import { useListeDemandes, useMutationsDemandes, type FiltresDemandes } from "./api";
import type { DemandeDocument } from "./types";

const { contexteActif, aPermission } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const filtres = reactive<FiltresDemandes>({ statut: null, mesDemandesSeulement: false });
const { data: demandes, isLoading } = useListeDemandes(entrepriseId, computed(() => filtres));
const { traiter, refuser } = useMutationsDemandes(entrepriseId);

const { data: tousLesDocuments } = useListeDocuments(
  entrepriseId,
  computed(() => ({ categorie: null, exerciceId: null, dossierPermanentSeulement: false })),
);
const documentsVisibles = computed(() => (tousLesDocuments.value ?? []).filter((d) => d.visible_client));

const colonnes: ColonneTable<DemandeDocument>[] = [
  { cle: "libelle", libelle: "Demande" },
  { cle: "description", libelle: "Précisions" },
  { cle: "statut", libelle: "Statut" },
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

// --- Traitement ---

const demandeATraiterId = ref<string | null>(null);
const documentChoisiId = ref("");
const erreurTraitement = ref<string | null>(null);

function ouvrirTraitement(demande: DemandeDocument): void {
  if (demande.statut !== "en_attente") return;
  demandeATraiterId.value = demande.id;
  documentChoisiId.value = "";
  erreurTraitement.value = null;
}

async function confirmerTraitement(): Promise<void> {
  if (!demandeATraiterId.value || !documentChoisiId.value) return;
  erreurTraitement.value = null;
  try {
    await traiter.mutateAsync({ id: demandeATraiterId.value, documentId: documentChoisiId.value });
    demandeATraiterId.value = null;
  } catch (e) {
    erreurTraitement.value = messageErreur(e);
  }
}

// --- Refus ---

const demandeARefuserId = ref<string | null>(null);
const motifRefus = ref("");
const erreurRefus = ref<string | null>(null);

function ouvrirRefus(demande: DemandeDocument): void {
  if (demande.statut !== "en_attente") return;
  demandeARefuserId.value = demande.id;
  motifRefus.value = "";
  erreurRefus.value = null;
}

async function confirmerRefus(): Promise<void> {
  if (!demandeARefuserId.value || !motifRefus.value) return;
  erreurRefus.value = null;
  try {
    await refuser.mutateAsync({ id: demandeARefuserId.value, motif: motifRefus.value });
    demandeARefuserId.value = null;
  } catch (e) {
    erreurRefus.value = messageErreur(e);
  }
}

// --- Échanges sur une demande ---

const demandeOuverte = ref<DemandeDocument | null>(null);
function ouvrirEchanges(demande: DemandeDocument): void {
  demandeOuverte.value = demande;
}
</script>

<template>
  <div class="space-y-4">
    <h1 class="text-lg font-semibold text-text">Demandes clients</h1>

    <select v-model="filtres.statut" class="rounded-md border border-border px-3 py-2 text-sm text-text">
      <option :value="null">Tous les statuts</option>
      <option value="en_attente">En attente</option>
      <option value="traitee">Traitées</option>
      <option value="refusee">Refusées</option>
    </select>

    <p class="text-xs text-text-muted">Cliquer sur une demande ouvre les échanges avec le client.</p>

    <BaseDataTable
      :colonnes="colonnes"
      :lignes="demandes ?? []"
      :chargement="isLoading"
      message-vide="Aucune demande pour le moment."
      @ligne-cliquee="ouvrirEchanges"
    >
      <template #cell-description="{ valeur }">{{ valeur ?? "—" }}</template>
      <template #cell-cree_le="{ valeur }">{{ formaterDate(valeur as string) }}</template>
      <template #cell-statut="{ ligne, valeur }">
        <div class="flex items-center gap-2">
          <StatutBadge :libelle="libellesStatut[valeur as string]" :tonalite="tonalitesStatut[valeur as string]" />
          <template v-if="ligne.statut === 'en_attente' && aPermission('portail_client.traiter')">
            <button type="button" class="text-xs text-primary hover:underline" @click.stop="ouvrirTraitement(ligne)">
              Traiter
            </button>
            <button type="button" class="text-xs text-danger hover:underline" @click.stop="ouvrirRefus(ligne)">
              Refuser
            </button>
          </template>
        </div>
      </template>
    </BaseDataTable>

    <div v-if="demandeOuverte" class="space-y-2">
      <div class="flex justify-end">
        <button type="button" class="text-sm text-text-muted hover:underline" @click="demandeOuverte = null">
          Fermer
        </button>
      </div>
      <FilCommentaires :entreprise-id="entrepriseId" :demande="demandeOuverte" />
    </div>

    <form
      v-if="demandeATraiterId"
      class="space-y-4 rounded-lg border border-border bg-surface p-6"
      @submit.prevent="confirmerTraitement"
    >
      <h2 class="text-base font-semibold text-text">Traiter la demande</h2>
      <div>
        <label class="mb-1 block text-sm font-medium text-text">Document à transmettre (déjà visible client)</label>
        <select v-model="documentChoisiId" required class="w-full rounded-md border border-border px-3 py-2 text-text">
          <option value="" disabled>Choisir un document</option>
          <option v-for="d in documentsVisibles" :key="d.id" :value="d.id">{{ d.nom_fichier }} — {{ d.categorie }}</option>
        </select>
        <p v-if="documentsVisibles.length === 0" class="mt-1 text-xs text-text-muted">
          Aucun document n'est actuellement visible client ; rendez-en un visible depuis le module Documents avant de traiter cette demande.
        </p>
      </div>
      <p v-if="erreurTraitement" class="text-sm text-danger">{{ erreurTraitement }}</p>
      <div class="flex justify-end gap-2">
        <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted" @click="demandeATraiterId = null">
          Annuler
        </button>
        <button type="submit" :disabled="traiter.isPending.value" class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60">
          Confirmer
        </button>
      </div>
    </form>

    <form
      v-if="demandeARefuserId"
      class="space-y-4 rounded-lg border border-border bg-surface p-6"
      @submit.prevent="confirmerRefus"
    >
      <h2 class="text-base font-semibold text-text">Refuser la demande</h2>
      <div>
        <label class="mb-1 block text-sm font-medium text-text">Motif</label>
        <input v-model="motifRefus" required minlength="2" maxlength="500" class="w-full rounded-md border border-border px-3 py-2 text-text" />
      </div>
      <p v-if="erreurRefus" class="text-sm text-danger">{{ erreurRefus }}</p>
      <div class="flex justify-end gap-2">
        <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted" @click="demandeARefuserId = null">
          Annuler
        </button>
        <button type="submit" :disabled="refuser.isPending.value" class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60">
          Confirmer le refus
        </button>
      </div>
    </form>
  </div>
</template>