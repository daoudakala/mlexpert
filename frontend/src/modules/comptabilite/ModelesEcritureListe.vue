<script setup lang="ts">
/**
 * Saisie par modèle (cahier des charges, section 8.2) : une liste des
 * modèles de l'entreprise, un formulaire de création/édition (compte +
 * sens + libellé par ligne, jamais de montant — voir types.ts), et un
 * panneau "Appliquer" qui ne demande que les montants pour générer une
 * écriture brouillon (réutilise ServiceComptabilite.appliquer_modele côté
 * backend, qui réutilise lui-même creer_ecriture et tous ses contrôles).
 */
import { computed, reactive, ref } from "vue";
import { useRouter } from "vue-router";

import { useAuth } from "@/core/auth/useAuth";
import { messageErreur } from "@/core/api/erreurs";
import BaseDataTable, { type ColonneTable } from "@/core/ui/BaseDataTable.vue";
import ConfirmDialog from "@/core/ui/ConfirmDialog.vue";
import MontantInput from "@/core/ui/MontantInput.vue";
import StatutBadge from "@/core/ui/StatutBadge.vue";
import { useComptesEntreprise, useJournaux, useMutationsModelesEcriture, useModelesEcriture } from "./api";
import { useExercices } from "@/modules/exercices/api";
import type { ModeleEcritureAvecLignes, SensLigne } from "./types";

const router = useRouter();
const { contexteActif, aPermission } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const { data: journaux } = useJournaux(entrepriseId);
const { data: comptes } = useComptesEntreprise(entrepriseId);
const { data: exercices } = useExercices(entrepriseId);
const actifsSeulement = ref(true);
const { data: modeles, isLoading } = useModelesEcriture(entrepriseId, actifsSeulement);
const { creer, modifier, desactiver, appliquer } = useMutationsModelesEcriture(entrepriseId);

const colonnes: ColonneTable<ModeleEcritureAvecLignes>[] = [
  { cle: "code", libelle: "Code" },
  { cle: "libelle", libelle: "Libellé" },
  { cle: "actif", libelle: "Statut" },
];

function libelleJournal(journalId: string): string {
  const j = journaux.value?.find((j) => j.id === journalId);
  return j ? `${j.code} — ${j.libelle}` : journalId;
}
function libelleCompte(compteId: string): string {
  const c = comptes.value?.find((c) => c.id === compteId);
  return c ? `${c.numero} — ${c.libelle}` : compteId;
}

// --- Formulaire de création/édition -----------------------------------------

interface LigneFormulaire {
  compte_id: string;
  sens: SensLigne;
  libelle: string;
}
function ligneVide(): LigneFormulaire {
  return { compte_id: "", sens: "debit", libelle: "" };
}

const formulaireOuvert = ref(false);
const modeleEnEdition = ref<ModeleEcritureAvecLignes | null>(null);
const formulaire = reactive({
  code: "",
  libelle: "",
  journal_id: "",
  lignes: [ligneVide(), ligneVide()] as LigneFormulaire[],
});
const erreurFormulaire = ref<string | null>(null);

function ouvrirCreation(): void {
  modeleEnEdition.value = null;
  formulaire.code = "";
  formulaire.libelle = "";
  formulaire.journal_id = "";
  formulaire.lignes = [ligneVide(), ligneVide()];
  erreurFormulaire.value = null;
  formulaireOuvert.value = true;
}

function ouvrirEdition(modele: ModeleEcritureAvecLignes): void {
  modeleEnEdition.value = modele;
  formulaire.code = modele.code;
  formulaire.libelle = modele.libelle;
  formulaire.journal_id = modele.journal_id;
  formulaire.lignes = modele.lignes.map((l) => ({
    compte_id: l.compte_id,
    sens: l.sens,
    libelle: l.libelle ?? "",
  }));
  erreurFormulaire.value = null;
  formulaireOuvert.value = true;
}

function ajouterLigne(): void {
  formulaire.lignes.push(ligneVide());
}
function retirerLigne(index: number): void {
  formulaire.lignes.splice(index, 1);
}

const enEnvoiFormulaire = computed(() => creer.isPending.value || modifier.isPending.value);

async function soumettreFormulaire(): Promise<void> {
  erreurFormulaire.value = null;
  const lignes = formulaire.lignes.map((l) => ({
    compte_id: l.compte_id,
    sens: l.sens,
    libelle: l.libelle || null,
  }));
  try {
    if (modeleEnEdition.value) {
      await modifier.mutateAsync({
        id: modeleEnEdition.value.id,
        donnees: { code: formulaire.code, libelle: formulaire.libelle, journal_id: formulaire.journal_id, lignes },
      });
    } else {
      await creer.mutateAsync({ code: formulaire.code, libelle: formulaire.libelle, journal_id: formulaire.journal_id, lignes });
    }
    formulaireOuvert.value = false;
  } catch (e) {
    erreurFormulaire.value = messageErreur(e);
  }
}

// Deux refs distincts (voir le commentaire équivalent dans
// JournauxListe.vue) : la cible ne doit pas se perdre avant que
// "confirmer" ne soit émis par le dialogue.
const modeleADesactiver = ref<ModeleEcritureAvecLignes | null>(null);
const confirmationOuverte = ref(false);
function demanderDesactivation(modele: ModeleEcritureAvecLignes): void {
  modeleADesactiver.value = modele;
  confirmationOuverte.value = true;
}
async function confirmerDesactivation(): Promise<void> {
  if (!modeleADesactiver.value) return;
  await desactiver.mutateAsync(modeleADesactiver.value.id);
  modeleADesactiver.value = null;
}

// --- Panneau d'application : ne demande que les montants --------------------

const applicationOuverte = ref(false);
const modeleAAppliquer = ref<ModeleEcritureAvecLignes | null>(null);
const application = reactive({
  exercice_id: "",
  date_ecriture: "",
  libelle: "",
  montants: {} as Record<string, number>,
});
const erreurApplication = ref<string | null>(null);

function ouvrirApplication(modele: ModeleEcritureAvecLignes): void {
  modeleAAppliquer.value = modele;
  application.exercice_id = "";
  application.date_ecriture = "";
  application.libelle = "";
  application.montants = Object.fromEntries(modele.lignes.map((l) => [l.id, 0]));
  erreurApplication.value = null;
  applicationOuverte.value = true;
}

async function soumettreApplication(): Promise<void> {
  if (!modeleAAppliquer.value) return;
  erreurApplication.value = null;
  try {
    const ecriture = await appliquer.mutateAsync({
      id: modeleAAppliquer.value.id,
      donnees: {
        exercice_id: application.exercice_id,
        date_ecriture: application.date_ecriture,
        libelle: application.libelle || null,
        lignes: Object.entries(application.montants)
          .filter(([, montant]) => montant > 0)
          .map(([ligne_modele_id, montant]) => ({ ligne_modele_id, montant })),
      },
    });
    applicationOuverte.value = false;
    router.push({ name: "comptabilite.ecriture", params: { id: ecriture.id } });
  } catch (e) {
    erreurApplication.value = messageErreur(e);
  }
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-lg font-semibold text-text">Modèles d'écriture</h1>
      <button
        v-if="aPermission('modele_ecriture.creer')"
        type="button"
        class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover"
        @click="ouvrirCreation"
      >
        Nouveau modèle
      </button>
    </div>

    <label class="flex items-center gap-2 text-sm text-text">
      <input v-model="actifsSeulement" type="checkbox" />
      Actifs seulement
    </label>

    <BaseDataTable :colonnes="colonnes" :lignes="modeles ?? []" :chargement="isLoading" message-vide="Aucun modèle d'écriture pour le moment.">
      <template #cell-actif="{ ligne }">
        <div class="flex flex-wrap items-center gap-2">
          <StatutBadge :libelle="ligne.actif ? 'Actif' : 'Désactivé'" :tonalite="ligne.actif ? 'succes' : 'neutre'" />
          <button
            v-if="ligne.actif && aPermission('ecriture.creer')"
            type="button"
            class="text-xs text-primary hover:underline"
            @click="ouvrirApplication(ligne)"
          >
            Appliquer
          </button>
          <button
            v-if="aPermission('modele_ecriture.modifier')"
            type="button"
            class="text-xs text-text hover:underline"
            @click="ouvrirEdition(ligne)"
          >
            Modifier
          </button>
          <button
            v-if="ligne.actif && aPermission('modele_ecriture.modifier')"
            type="button"
            class="text-xs text-danger hover:underline"
            @click="demanderDesactivation(ligne)"
          >
            Désactiver
          </button>
        </div>
      </template>
    </BaseDataTable>

    <!-- Création / édition du modèle -->
    <div v-if="formulaireOuvert" class="rounded-lg border border-border bg-surface p-6">
      <h2 class="mb-3 text-base font-semibold text-text">
        {{ modeleEnEdition ? "Modifier le modèle" : "Nouveau modèle" }}
      </h2>
      <form class="space-y-4" @submit.prevent="soumettreFormulaire">
        <div class="grid grid-cols-3 gap-4">
          <div>
            <label class="mb-1 block text-sm font-medium text-text">Code</label>
            <input v-model="formulaire.code" required maxlength="20" class="w-full rounded-md border border-border px-3 py-2 text-text" />
          </div>
          <div class="col-span-2">
            <label class="mb-1 block text-sm font-medium text-text">Libellé</label>
            <input v-model="formulaire.libelle" required minlength="2" class="w-full rounded-md border border-border px-3 py-2 text-text" />
          </div>
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Journal</label>
          <select v-model="formulaire.journal_id" required class="w-full rounded-md border border-border px-3 py-2 text-text">
            <option value="" disabled>— Choisir —</option>
            <option v-for="j in journaux" :key="j.id" :value="j.id">{{ j.code }} — {{ j.libelle }}</option>
          </select>
        </div>

        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <h3 class="text-sm font-semibold text-text">Lignes (compte + sens, le montant se saisit à l'application)</h3>
            <button type="button" class="text-sm text-primary hover:underline" @click="ajouterLigne">+ Ajouter une ligne</button>
          </div>
          <div v-for="(ligne, index) in formulaire.lignes" :key="index" class="grid grid-cols-12 items-end gap-2 rounded-md border border-border p-3">
            <div class="col-span-5">
              <label class="mb-1 block text-xs font-medium text-text-muted">Compte</label>
              <select v-model="ligne.compte_id" required class="w-full rounded-md border border-border px-2 py-1.5 text-sm text-text">
                <option value="" disabled>— Choisir —</option>
                <option v-for="c in comptes" :key="c.id" :value="c.id">{{ c.numero }} — {{ c.libelle }}</option>
              </select>
            </div>
            <div class="col-span-4">
              <label class="mb-1 block text-xs font-medium text-text-muted">Libellé (optionnel)</label>
              <input v-model="ligne.libelle" class="w-full rounded-md border border-border px-2 py-1.5 text-sm text-text" />
            </div>
            <div class="col-span-2">
              <label class="mb-1 block text-xs font-medium text-text-muted">Sens</label>
              <select v-model="ligne.sens" class="w-full rounded-md border border-border px-2 py-1.5 text-sm text-text">
                <option value="debit">Débit</option>
                <option value="credit">Crédit</option>
              </select>
            </div>
            <div class="col-span-1">
              <button
                type="button"
                :disabled="formulaire.lignes.length <= 2"
                class="w-full rounded-md border border-border px-2 py-1.5 text-sm text-text hover:bg-surface-muted disabled:opacity-40"
                @click="retirerLigne(index)"
              >
                Retirer
              </button>
            </div>
          </div>
        </div>

        <p v-if="erreurFormulaire" class="text-sm text-danger">{{ erreurFormulaire }}</p>
        <div class="flex justify-end gap-2">
          <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted" @click="formulaireOuvert = false">
            Annuler
          </button>
          <button type="submit" :disabled="enEnvoiFormulaire" class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60">
            {{ modeleEnEdition ? "Enregistrer" : "Créer" }}
          </button>
        </div>
      </form>
    </div>

    <!-- Application du modèle -->
    <div v-if="applicationOuverte && modeleAAppliquer" class="rounded-lg border border-border bg-surface p-6">
      <h2 class="mb-3 text-base font-semibold text-text">Appliquer « {{ modeleAAppliquer.libelle }} »</h2>
      <form class="space-y-4" @submit.prevent="soumettreApplication">
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="mb-1 block text-sm font-medium text-text">Exercice</label>
            <select v-model="application.exercice_id" required class="w-full rounded-md border border-border px-3 py-2 text-text">
              <option value="" disabled>— Choisir —</option>
              <option v-for="e in exercices" :key="e.id" :value="e.id">{{ e.date_debut }} → {{ e.date_fin }}</option>
            </select>
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-text">Date</label>
            <input v-model="application.date_ecriture" type="date" required class="w-full rounded-md border border-border px-3 py-2 text-text" />
          </div>
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Libellé (optionnel — reprend celui du modèle)</label>
          <input v-model="application.libelle" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>

        <div class="space-y-2">
          <h3 class="text-sm font-semibold text-text">Montants</h3>
          <div v-for="ligne in modeleAAppliquer.lignes" :key="ligne.id" class="grid grid-cols-12 items-center gap-2">
            <div class="col-span-6 text-sm text-text">
              {{ libelleCompte(ligne.compte_id) }}
              <span class="text-text-muted">({{ ligne.sens === "debit" ? "débit" : "crédit" }})</span>
            </div>
            <div class="col-span-6">
              <MontantInput v-model="application.montants[ligne.id]" />
            </div>
          </div>
        </div>

        <p class="text-xs text-text-muted">Journal : {{ libelleJournal(modeleAAppliquer.journal_id) }}</p>
        <p v-if="erreurApplication" class="text-sm text-danger">{{ erreurApplication }}</p>
        <div class="flex justify-end gap-2">
          <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted" @click="applicationOuverte = false">
            Annuler
          </button>
          <button type="submit" :disabled="appliquer.isPending.value" class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60">
            Générer l'écriture (brouillon)
          </button>
        </div>
      </form>
    </div>

    <ConfirmDialog
      v-model:ouvert="confirmationOuverte"
      titre="Désactiver ce modèle ?"
      :message="`Le modèle ${modeleADesactiver?.code} ne sera plus proposé pour générer de nouvelles écritures, mais reste visible dans l'historique.`"
      libelle-confirmer="Désactiver"
      dangereux
      @confirmer="confirmerDesactivation"
    />
  </div>
</template>
