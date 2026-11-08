<script setup lang="ts">
/**
 * Écritures récurrentes (cahier des charges, section 8.4) : une liste des
 * récurrences de l'entreprise, un formulaire de création/édition (compte +
 * sens + MONTANT FIXE par ligne, à la différence d'un modèle — voir
 * types.ts), et un panneau "Générer les échéances" qui ne demande qu'une
 * date limite pour produire autant d'écritures brouillon que d'échéances
 * dues (réutilise ServiceComptabilite.generer_echeances côté backend, qui
 * réutilise lui-même creer_ecriture et tous ses contrôles).
 */
import { computed, reactive, ref } from "vue";
import { useRouter } from "vue-router";

import { useAuth } from "@/core/auth/useAuth";
import { messageErreur } from "@/core/api/erreurs";
import BaseDataTable, { type ColonneTable } from "@/core/ui/BaseDataTable.vue";
import ConfirmDialog from "@/core/ui/ConfirmDialog.vue";
import MontantInput from "@/core/ui/MontantInput.vue";
import StatutBadge from "@/core/ui/StatutBadge.vue";
import {
  useComptesEntreprise,
  useJournaux,
  useMutationsEcrituresRecurrentes,
  useEcrituresRecurrentes,
} from "./api";
import type {
  EcritureRecurrenteAvecLignes,
  GenerationEcheancesResultat,
  PeriodiciteRecurrence,
  SensLigne,
} from "./types";

const router = useRouter();
const { contexteActif, aPermission } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const { data: journaux } = useJournaux(entrepriseId);
const { data: comptes } = useComptesEntreprise(entrepriseId);
const actifsSeulement = ref(true);
const { data: recurrentes, isLoading } = useEcrituresRecurrentes(entrepriseId, actifsSeulement);
const { creer, modifier, desactiver, activer, genererEcheances } =
  useMutationsEcrituresRecurrentes(entrepriseId);

const colonnes: ColonneTable<EcritureRecurrenteAvecLignes>[] = [
  { cle: "code", libelle: "Code" },
  { cle: "libelle", libelle: "Libellé" },
  { cle: "periodicite", libelle: "Périodicité" },
  { cle: "prochaine_echeance", libelle: "Prochaine échéance" },
  { cle: "actif", libelle: "Statut" },
];

const libellesPeriodicite: Record<PeriodiciteRecurrence, string> = {
  mensuelle: "Mensuelle",
  trimestrielle: "Trimestrielle",
  annuelle: "Annuelle",
};

function libelleCompte(compteId: string): string {
  const c = comptes.value?.find((c) => c.id === compteId);
  return c ? `${c.numero} — ${c.libelle}` : compteId;
}

// --- Formulaire de création/édition -----------------------------------------

interface LigneFormulaire {
  compte_id: string;
  sens: SensLigne;
  montant: number;
  libelle: string;
}
function ligneVide(): LigneFormulaire {
  return { compte_id: "", sens: "debit", montant: 0, libelle: "" };
}

const formulaireOuvert = ref(false);
const recurrenteEnEdition = ref<EcritureRecurrenteAvecLignes | null>(null);
const formulaire = reactive({
  code: "",
  libelle: "",
  journal_id: "",
  periodicite: "mensuelle" as PeriodiciteRecurrence,
  date_debut: "",
  date_fin: "",
  reference_piece: "",
  lignes: [ligneVide(), ligneVide()] as LigneFormulaire[],
});
const erreurFormulaire = ref<string | null>(null);

const totalDebit = computed(() =>
  formulaire.lignes.filter((l) => l.sens === "debit").reduce((s, l) => s + (Number(l.montant) || 0), 0),
);
const totalCredit = computed(() =>
  formulaire.lignes.filter((l) => l.sens === "credit").reduce((s, l) => s + (Number(l.montant) || 0), 0),
);
const equilibree = computed(() => Math.abs(totalDebit.value - totalCredit.value) < 0.005);

function ouvrirCreation(): void {
  recurrenteEnEdition.value = null;
  formulaire.code = "";
  formulaire.libelle = "";
  formulaire.journal_id = "";
  formulaire.periodicite = "mensuelle";
  formulaire.date_debut = "";
  formulaire.date_fin = "";
  formulaire.reference_piece = "";
  formulaire.lignes = [ligneVide(), ligneVide()];
  erreurFormulaire.value = null;
  formulaireOuvert.value = true;
}

function ouvrirEdition(recurrente: EcritureRecurrenteAvecLignes): void {
  recurrenteEnEdition.value = recurrente;
  formulaire.code = recurrente.code;
  formulaire.libelle = recurrente.libelle;
  formulaire.journal_id = recurrente.journal_id;
  formulaire.periodicite = recurrente.periodicite;
  formulaire.date_debut = recurrente.date_debut;
  formulaire.date_fin = recurrente.date_fin ?? "";
  formulaire.reference_piece = recurrente.reference_piece ?? "";
  formulaire.lignes = recurrente.lignes.map((l) => ({
    compte_id: l.compte_id,
    sens: l.sens,
    montant: Number(l.montant),
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
    montant: Number(l.montant),
    libelle: l.libelle || null,
  }));
  try {
    if (recurrenteEnEdition.value) {
      await modifier.mutateAsync({
        id: recurrenteEnEdition.value.id,
        donnees: {
          code: formulaire.code,
          libelle: formulaire.libelle,
          journal_id: formulaire.journal_id,
          periodicite: formulaire.periodicite,
          date_fin: formulaire.date_fin || null,
          reference_piece: formulaire.reference_piece || null,
          lignes,
        },
      });
    } else {
      await creer.mutateAsync({
        code: formulaire.code,
        libelle: formulaire.libelle,
        journal_id: formulaire.journal_id,
        periodicite: formulaire.periodicite,
        date_debut: formulaire.date_debut,
        date_fin: formulaire.date_fin || null,
        reference_piece: formulaire.reference_piece || null,
        lignes,
      });
    }
    formulaireOuvert.value = false;
  } catch (e) {
    erreurFormulaire.value = messageErreur(e);
  }
}

// --- Désactivation / réactivation --------------------------------------------

const recurrenteADesactiver = ref<EcritureRecurrenteAvecLignes | null>(null);
const confirmationOuverte = ref(false);
function demanderDesactivation(recurrente: EcritureRecurrenteAvecLignes): void {
  recurrenteADesactiver.value = recurrente;
  confirmationOuverte.value = true;
}
async function confirmerDesactivation(): Promise<void> {
  if (!recurrenteADesactiver.value) return;
  await desactiver.mutateAsync(recurrenteADesactiver.value.id);
  recurrenteADesactiver.value = null;
}
async function reactiver(recurrente: EcritureRecurrenteAvecLignes): Promise<void> {
  await activer.mutateAsync(recurrente.id);
}

// --- Génération des échéances : ne demande qu'une date limite --------------

const generationOuverte = ref(false);
const recurrenteAGenerer = ref<EcritureRecurrenteAvecLignes | null>(null);
const jusquau = ref("");
const erreurGeneration = ref<string | null>(null);
const dernierResultat = ref<GenerationEcheancesResultat | null>(null);

function ouvrirGeneration(recurrente: EcritureRecurrenteAvecLignes): void {
  recurrenteAGenerer.value = recurrente;
  jusquau.value = recurrente.prochaine_echeance;
  erreurGeneration.value = null;
  dernierResultat.value = null;
  generationOuverte.value = true;
}

async function soumettreGeneration(): Promise<void> {
  if (!recurrenteAGenerer.value) return;
  erreurGeneration.value = null;
  try {
    dernierResultat.value = await genererEcheances.mutateAsync({
      id: recurrenteAGenerer.value.id,
      donnees: { jusquau: jusquau.value },
    });
  } catch (e) {
    erreurGeneration.value = messageErreur(e);
  }
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-lg font-semibold text-text">Écritures récurrentes</h1>
      <button
        v-if="aPermission('ecriture_recurrente.creer')"
        type="button"
        class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover"
        @click="ouvrirCreation"
      >
        Nouvelle écriture récurrente
      </button>
    </div>

    <label class="flex items-center gap-2 text-sm text-text">
      <input v-model="actifsSeulement" type="checkbox" />
      Actives seulement
    </label>

    <BaseDataTable
      :colonnes="colonnes"
      :lignes="recurrentes ?? []"
      :chargement="isLoading"
      message-vide="Aucune écriture récurrente pour le moment."
    >
      <template #cell-periodicite="{ ligne }">
        {{ libellesPeriodicite[ligne.periodicite] }}
      </template>
      <template #cell-actif="{ ligne }">
        <div class="flex flex-wrap items-center gap-2">
          <StatutBadge :libelle="ligne.actif ? 'Active' : 'Désactivée'" :tonalite="ligne.actif ? 'succes' : 'neutre'" />
          <button
            v-if="ligne.actif && aPermission('ecriture_recurrente.generer')"
            type="button"
            class="text-xs text-primary hover:underline"
            @click="ouvrirGeneration(ligne)"
          >
            Générer les échéances
          </button>
          <button
            v-if="aPermission('ecriture_recurrente.modifier')"
            type="button"
            class="text-xs text-text hover:underline"
            @click="ouvrirEdition(ligne)"
          >
            Modifier
          </button>
          <button
            v-if="ligne.actif && aPermission('ecriture_recurrente.modifier')"
            type="button"
            class="text-xs text-danger hover:underline"
            @click="demanderDesactivation(ligne)"
          >
            Désactiver
          </button>
          <button
            v-if="!ligne.actif && aPermission('ecriture_recurrente.modifier')"
            type="button"
            class="text-xs text-primary hover:underline"
            @click="reactiver(ligne)"
          >
            Réactiver
          </button>
        </div>
      </template>
    </BaseDataTable>

    <!-- Création / édition de la récurrence -->
    <div v-if="formulaireOuvert" class="rounded-lg border border-border bg-surface p-6">
      <h2 class="mb-3 text-base font-semibold text-text">
        {{ recurrenteEnEdition ? "Modifier l'écriture récurrente" : "Nouvelle écriture récurrente" }}
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
        <div class="grid grid-cols-3 gap-4">
          <div>
            <label class="mb-1 block text-sm font-medium text-text">Journal</label>
            <select v-model="formulaire.journal_id" required class="w-full rounded-md border border-border px-3 py-2 text-text">
              <option value="" disabled>— Choisir —</option>
              <option v-for="j in journaux" :key="j.id" :value="j.id">{{ j.code }} — {{ j.libelle }}</option>
            </select>
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-text">Périodicité</label>
            <select v-model="formulaire.periodicite" required class="w-full rounded-md border border-border px-3 py-2 text-text">
              <option value="mensuelle">Mensuelle</option>
              <option value="trimestrielle">Trimestrielle</option>
              <option value="annuelle">Annuelle</option>
            </select>
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-text">Référence pièce (optionnel)</label>
            <input v-model="formulaire.reference_piece" class="w-full rounded-md border border-border px-3 py-2 text-text" />
          </div>
        </div>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="mb-1 block text-sm font-medium text-text">Date de début</label>
            <input
              v-model="formulaire.date_debut"
              type="date"
              required
              :disabled="!!recurrenteEnEdition"
              class="w-full rounded-md border border-border px-3 py-2 text-text disabled:bg-surface-muted disabled:text-text-muted"
            />
            <p v-if="recurrenteEnEdition" class="mt-1 text-xs text-text-muted">
              Non modifiable après création — seule la prochaine échéance avance (via la génération).
            </p>
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-text">Date de fin (optionnel)</label>
            <input v-model="formulaire.date_fin" type="date" class="w-full rounded-md border border-border px-3 py-2 text-text" />
          </div>
        </div>

        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <h3 class="text-sm font-semibold text-text">
              Lignes (compte + sens + montant FIXE — identique à chaque occurrence)
            </h3>
            <button type="button" class="text-sm text-primary hover:underline" @click="ajouterLigne">+ Ajouter une ligne</button>
          </div>
          <div v-for="(ligne, index) in formulaire.lignes" :key="index" class="grid grid-cols-12 items-end gap-2 rounded-md border border-border p-3">
            <div class="col-span-4">
              <label class="mb-1 block text-xs font-medium text-text-muted">Compte</label>
              <select v-model="ligne.compte_id" required class="w-full rounded-md border border-border px-2 py-1.5 text-sm text-text">
                <option value="" disabled>— Choisir —</option>
                <option v-for="c in comptes" :key="c.id" :value="c.id">{{ c.numero }} — {{ c.libelle }}</option>
              </select>
            </div>
            <div class="col-span-3">
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
            <div class="col-span-2">
              <label class="mb-1 block text-xs font-medium text-text-muted">Montant</label>
              <MontantInput v-model="ligne.montant" />
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
          <p class="text-sm" :class="equilibree ? 'text-text-muted' : 'text-danger'">
            Total débit {{ totalDebit.toFixed(2) }} — Total crédit {{ totalCredit.toFixed(2) }}
            <span v-if="!equilibree">(non équilibré)</span>
          </p>
        </div>

        <p v-if="erreurFormulaire" class="text-sm text-danger">{{ erreurFormulaire }}</p>
        <div class="flex justify-end gap-2">
          <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted" @click="formulaireOuvert = false">
            Annuler
          </button>
          <button
            type="submit"
            :disabled="enEnvoiFormulaire || !equilibree"
            class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60"
          >
            {{ recurrenteEnEdition ? "Enregistrer" : "Créer" }}
          </button>
        </div>
      </form>
    </div>

    <!-- Génération des échéances -->
    <div v-if="generationOuverte && recurrenteAGenerer" class="rounded-lg border border-border bg-surface p-6">
      <h2 class="mb-3 text-base font-semibold text-text">
        Générer les échéances de « {{ recurrenteAGenerer.libelle }} »
      </h2>
      <form class="space-y-4" @submit.prevent="soumettreGeneration">
        <p class="text-sm text-text-muted">
          Prochaine échéance due : {{ recurrenteAGenerer.prochaine_echeance }}. Une écriture brouillon sera
          générée pour chaque échéance due jusqu'à la date choisie (incluse).
        </p>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Jusqu'au</label>
          <input v-model="jusquau" type="date" required class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <p v-if="erreurGeneration" class="text-sm text-danger">{{ erreurGeneration }}</p>

        <div v-if="dernierResultat" class="space-y-2 rounded-md border border-border bg-surface-muted p-3 text-sm text-text">
          <p>
            {{ dernierResultat.ecritures_creees.length }} écriture(s) brouillon générée(s)
            <span v-if="dernierResultat.ignorees.length">
              — {{ dernierResultat.ignorees.length }} échéance(s) ignorée(s)
            </span>.
          </p>
          <ul v-if="dernierResultat.ecritures_creees.length" class="list-inside list-disc">
            <li v-for="e in dernierResultat.ecritures_creees" :key="e.id">
              <button type="button" class="text-primary hover:underline" @click="router.push({ name: 'comptabilite.ecriture', params: { id: e.id } })">
                {{ e.date_ecriture }} — {{ e.libelle }}
              </button>
            </li>
          </ul>
          <ul v-if="dernierResultat.ignorees.length" class="list-inside list-disc text-danger">
            <li v-for="(i, index) in dernierResultat.ignorees" :key="index">{{ i.date_echeance }} — {{ i.raison }}</li>
          </ul>
        </div>

        <div class="flex justify-end gap-2">
          <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted" @click="generationOuverte = false">
            Fermer
          </button>
          <button
            type="submit"
            :disabled="genererEcheances.isPending.value"
            class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60"
          >
            Générer
          </button>
        </div>
      </form>
    </div>

    <ConfirmDialog
      v-model:ouvert="confirmationOuverte"
      titre="Désactiver cette écriture récurrente ?"
      :message="`L'écriture récurrente ${recurrenteADesactiver?.code} ne générera plus de nouvelle échéance jusqu'à sa réactivation.`"
      libelle-confirmer="Désactiver"
      dangereux
      @confirmer="confirmerDesactivation"
    />
  </div>
</template>