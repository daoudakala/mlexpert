<script setup lang="ts">
/**
 * Sert à la fois pour la création (route .../comptes-bancaires/:id/releves/
 * nouveau, :id = compte bancaire) et la modification (route .../releves/
 * :releveId) : le backend distingue les deux par des routes différentes
 * (POST sous le compte bancaire, PATCH au niveau entreprise), mais le
 * formulaire est identique. La cohérence solde_fin = solde_debut +
 * Σ(credit - debit) est vérifiée côté backend (schemas.py) ; on affiche
 * seulement le solde calculé à titre indicatif pour aider la saisie.
 */
import { computed, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useAuth } from "@/core/auth/useAuth";
import { messageErreur } from "@/core/api/erreurs";
import BaseFormulaire from "@/core/ui/BaseFormulaire.vue";
import ConfirmDialog from "@/core/ui/ConfirmDialog.vue";
import { formaterMontant } from "@/core/ui/formatage";
import MontantInput from "@/core/ui/MontantInput.vue";
import { useMutationsReleves, useReleve } from "./api";
import type { LigneReleveSaisie } from "./types";

const route = useRoute();
const router = useRouter();
const { contexteActif } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const compteBancaireId = computed(() => (route.params.id as string) || null);
const releveId = computed(() => (route.params.releveId as string) || null);
const enEdition = computed(() => releveId.value !== null);

const { data: releveExistant } = useReleve(entrepriseId, releveId);
const { creer, modifier, supprimer } = useMutationsReleves(entrepriseId);

interface LigneFormulaire {
  date_operation: string;
  libelle: string;
  sens: "debit" | "credit";
  montant: number;
  reference: string;
}

function ligneVide(): LigneFormulaire {
  return { date_operation: "", libelle: "", sens: "debit", montant: 0, reference: "" };
}

const formulaire = reactive({
  date_debut: "",
  date_fin: "",
  solde_debut: 0 as number,
  reference: "",
  lignes: [ligneVide()] as LigneFormulaire[],
});

watch(
  releveExistant,
  (r) => {
    if (!r) return;
    formulaire.date_debut = r.date_debut;
    formulaire.date_fin = r.date_fin;
    formulaire.solde_debut = Number(r.solde_debut);
    formulaire.reference = r.reference ?? "";
    formulaire.lignes = r.lignes.map((l) => ({
      date_operation: l.date_operation,
      libelle: l.libelle,
      sens: Number(l.credit) > 0 ? "credit" : "debit",
      montant: Number(l.credit) > 0 ? Number(l.credit) : Number(l.debit),
      reference: l.reference ?? "",
    }));
  },
  { immediate: true },
);

const soldeFinCalcule = computed(() => {
  const mouvement = formulaire.lignes.reduce(
    (somme, l) => somme + (l.sens === "credit" ? l.montant : -l.montant),
    0,
  );
  return formulaire.solde_debut + mouvement;
});

function ajouterLigne(): void {
  formulaire.lignes.push(ligneVide());
}

function retirerLigne(index: number): void {
  formulaire.lignes.splice(index, 1);
}

function lignesSaisies(): LigneReleveSaisie[] {
  return formulaire.lignes.map((l) => ({
    date_operation: l.date_operation,
    libelle: l.libelle,
    reference: l.reference || null,
    debit: l.sens === "debit" ? l.montant : 0,
    credit: l.sens === "credit" ? l.montant : 0,
  }));
}

const erreur = ref<string | null>(null);
const enEnvoi = computed(() => creer.isPending.value || modifier.isPending.value);

async function soumettre(): Promise<void> {
  erreur.value = null;
  try {
    if (enEdition.value) {
      await modifier.mutateAsync({
        id: releveId.value!,
        donnees: {
          solde_debut: formulaire.solde_debut,
          solde_fin: soldeFinCalcule.value,
          reference: formulaire.reference || null,
          lignes: lignesSaisies(),
        },
      });
      router.push({ name: "tresorerie.compte-bancaire", params: { id: releveExistant.value!.compte_bancaire_id } });
    } else {
      await creer.mutateAsync({
        compteBancaireId: compteBancaireId.value!,
        donnees: {
          date_debut: formulaire.date_debut,
          date_fin: formulaire.date_fin,
          solde_debut: formulaire.solde_debut,
          solde_fin: soldeFinCalcule.value,
          reference: formulaire.reference || null,
          lignes: lignesSaisies(),
        },
      });
      router.push({ name: "tresorerie.compte-bancaire", params: { id: compteBancaireId.value! } });
    }
  } catch (e) {
    erreur.value = messageErreur(e);
  }
}

const confirmationSuppression = ref(false);

async function confirmerSuppression(): Promise<void> {
  await supprimer.mutateAsync(releveId.value!);
  router.push({ name: "tresorerie.compte-bancaire", params: { id: releveExistant.value!.compte_bancaire_id } });
}

function retour(): void {
  if (enEdition.value && releveExistant.value) {
    router.push({ name: "tresorerie.compte-bancaire", params: { id: releveExistant.value.compte_bancaire_id } });
  } else {
    router.push({ name: "tresorerie.compte-bancaire", params: { id: compteBancaireId.value! } });
  }
}
</script>

<template>
  <div class="max-w-3xl space-y-6">
    <h1 class="text-lg font-semibold text-text">
      {{ enEdition ? "Relevé bancaire" : "Nouveau relevé" }}
    </h1>

    <BaseFormulaire
      titre="Période et soldes"
      :erreur="erreur"
      :en-envoi="enEnvoi"
      @soumettre="soumettre"
      @annuler="retour"
    >
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Date de début</label>
          <input
            v-model="formulaire.date_debut"
            type="date"
            required
            :disabled="enEdition"
            class="w-full rounded-md border border-border px-3 py-2 text-text disabled:opacity-60"
          />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Date de fin</label>
          <input
            v-model="formulaire.date_fin"
            type="date"
            required
            :disabled="enEdition"
            class="w-full rounded-md border border-border px-3 py-2 text-text disabled:opacity-60"
          />
        </div>
      </div>

      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Solde début</label>
          <MontantInput v-model="formulaire.solde_debut" required />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Solde fin (calculé)</label>
          <input
            :value="formaterMontant(soldeFinCalcule)"
            type="text"
            disabled
            class="w-full rounded-md border border-border bg-surface-muted px-3 py-2 text-right text-text"
          />
        </div>
      </div>

      <div>
        <label class="mb-1 block text-sm font-medium text-text">Référence</label>
        <input v-model="formulaire.reference" class="w-full rounded-md border border-border px-3 py-2 text-text" />
      </div>

      <div class="space-y-3">
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-semibold text-text">Lignes du relevé</h3>
          <button
            type="button"
            class="text-sm text-primary hover:underline"
            @click="ajouterLigne"
          >
            + Ajouter une ligne
          </button>
        </div>

        <div
          v-for="(ligne, index) in formulaire.lignes"
          :key="index"
          class="grid grid-cols-12 items-end gap-2 rounded-md border border-border p-3"
        >
          <div class="col-span-2">
            <label class="mb-1 block text-xs font-medium text-text-muted">Date</label>
            <input
              v-model="ligne.date_operation"
              type="date"
              required
              class="w-full rounded-md border border-border px-2 py-1.5 text-sm text-text"
            />
          </div>
          <div class="col-span-4">
            <label class="mb-1 block text-xs font-medium text-text-muted">Libellé</label>
            <input
              v-model="ligne.libelle"
              required
              class="w-full rounded-md border border-border px-2 py-1.5 text-sm text-text"
            />
          </div>
          <div class="col-span-2">
            <label class="mb-1 block text-xs font-medium text-text-muted">Sens</label>
            <select v-model="ligne.sens" class="w-full rounded-md border border-border px-2 py-1.5 text-sm text-text">
              <option value="debit">Débit</option>
              <option value="credit">Crédit</option>
            </select>
          </div>
          <div class="col-span-2">
            <label class="mb-1 block text-xs font-medium text-text-muted">Montant</label>
            <MontantInput v-model="ligne.montant" required />
          </div>
          <div class="col-span-1">
            <label class="mb-1 block text-xs font-medium text-text-muted">Réf.</label>
            <input
              v-model="ligne.reference"
              class="w-full rounded-md border border-border px-2 py-1.5 text-sm text-text"
            />
          </div>
          <div class="col-span-1">
            <button
              type="button"
              :disabled="formulaire.lignes.length <= 1"
              class="w-full rounded-md border border-border px-2 py-1.5 text-sm text-text hover:bg-surface-muted disabled:opacity-40"
              @click="retirerLigne(index)"
            >
              Retirer
            </button>
          </div>
        </div>
      </div>
    </BaseFormulaire>

    <div v-if="enEdition" class="flex justify-end">
      <button
        type="button"
        class="rounded-md border border-danger px-3 py-1.5 text-sm text-danger hover:bg-danger/10"
        @click="confirmationSuppression = true"
      >
        Supprimer ce relevé
      </button>
    </div>

    <ConfirmDialog
      v-model:ouvert="confirmationSuppression"
      titre="Supprimer ce relevé ?"
      message="Cette action est irréversible."
      libelle-confirmer="Supprimer"
      dangereux
      @confirmer="confirmerSuppression"
    />
  </div>
</template>
