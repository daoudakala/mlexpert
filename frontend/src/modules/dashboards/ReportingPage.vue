<script setup lang="ts">
/**
 * Page unique du module dashboards : sélection d'un exercice, puis trois
 * vues en onglets — balance générale, compte de résultat sommaire, grand
 * livre d'un compte choisi dans la balance. Module 100% lecture seule
 * (voir la note de tête de service.py côté backend) : pas de formulaire
 * de création/modification ici.
 */
import { computed, ref, watch } from "vue";

import { useAuth } from "@/core/auth/useAuth";
import BaseDataTable, { type ColonneTable } from "@/core/ui/BaseDataTable.vue";
import { formaterMontant } from "@/core/ui/formatage";
import { useExercices } from "@/modules/exercices/api";
import {
  exporterEtatsFinanciers,
  useBalanceAgee,
  useBalanceCompareeN1,
  useBalanceGenerale,
  useBilan,
  useCompteResultatDetaille,
  useCompteResultatSommaire,
  useEcheancier,
  useGrandLivre,
  useMutationDetecterAlertes,
  usePrevisionTresorerie,
  useTableauComptabilite,
  useTableauDirection,
} from "./api";
import type {
  LigneBalance,
  LigneBalanceComparee,
  LigneEcheance,
  LigneGrandLivre,
  LignePrevisionTresorerie,
  TrancheAgee,
  TypeTiersEcheancier,
} from "./types";

const { contexteActif, aPermission } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const { data: exercices } = useExercices(entrepriseId);
const exerciceId = ref<string | null>(null);

// Sélectionne le dernier exercice connu par défaut, dès que la liste arrive
// (chargement asynchrone : un simple mounted serait trop tôt).
const exerciceInitialise = ref(false);
watch(exercices, (liste) => {
  if (exerciceInitialise.value || !liste || liste.length === 0) return;
  exerciceId.value = liste[liste.length - 1].id;
  exerciceInitialise.value = true;
});

type Onglet =
  | "balance"
  | "comparaison"
  | "resultat"
  | "resultat-detaille"
  | "bilan"
  | "grand-livre"
  | "echeancier"
  | "balance-agee"
  | "prevision-tresorerie"
  | "pilotage";
const ongletActif = ref<Onglet>("balance");

// Pilotage Direction/Comptabilité (Étape 5) : PAS scopé à l'exercice
// sélectionné dans le menu déroulant ci-dessus, chaque tableau détermine
// lui-même son "exercice courant" côté backend (voir service.py) — même
// logique d'indépendance que l'échéancier/la balance âgée au-dessus.
const { data: tableauDirection, isLoading: chargementTableauDirection } = useTableauDirection(entrepriseId);
const { data: tableauComptabilite, isLoading: chargementTableauComptabilite } =
  useTableauComptabilite(entrepriseId);
const mutationDetecterAlertes = useMutationDetecterAlertes(entrepriseId);
const resultatDetection = ref<Record<string, number> | null>(null);

async function lancerDetectionAlertes(): Promise<void> {
  const resultat = await mutationDetecterAlertes.mutateAsync();
  resultatDetection.value = resultat.notifications_creees;
}

const LIBELLES_TYPES_ALERTE: Record<string, string> = {
  echeance_client: "Échéances clients",
  echeance_fournisseur: "Échéances fournisseurs",
  demande_piece_non_traitee: "Demandes de pièces non traitées",
  validation_en_attente: "Validations en attente",
  cloture_comptable: "Clôtures comptables",
  document_manquant: "Documents à renouveler",
};

// Échéancier / balance âgée : PAS scopés à l'exercice sélectionné (une
// facture impayée reste ouverte au-delà de la clôture de l'exercice qui
// l'a vue naître, voir la note de tête de service.py côté backend) — un
// seul sélecteur client/fournisseur, partagé par les deux onglets.
const typeTiersEcheancier = ref<TypeTiersEcheancier>("client");
const { data: echeancier, isLoading: chargementEcheancier } = useEcheancier(entrepriseId, typeTiersEcheancier);
const { data: balanceAgee, isLoading: chargementBalanceAgee } = useBalanceAgee(entrepriseId, typeTiersEcheancier);

// Prévision de trésorerie : PAS scopée à l'exercice sélectionné (projette
// le solde bancaire actuel, indépendamment de l'exercice choisi dans le
// menu déroulant ci-dessus), un seul sélecteur d'horizon.
const horizonsDisponibles = [30, 60, 90, 180] as const;
const horizonJours = ref<number>(90);
const { data: prevision, isLoading: chargementPrevision } = usePrevisionTresorerie(
  entrepriseId,
  horizonJours,
);

const { data: balance, isLoading: chargementBalance } = useBalanceGenerale(entrepriseId, exerciceId);
const { data: comparaison, isLoading: chargementComparaison } = useBalanceCompareeN1(entrepriseId, exerciceId);
const { data: resultat, isLoading: chargementResultat } = useCompteResultatSommaire(entrepriseId, exerciceId);
const { data: resultatDetaille, isLoading: chargementResultatDetaille } = useCompteResultatDetaille(
  entrepriseId,
  exerciceId,
);
const { data: bilan, isLoading: chargementBilan } = useBilan(entrepriseId, exerciceId);

const compteSelectionneId = ref<string | null>(null);
const { data: grandLivre, isLoading: chargementGrandLivre } = useGrandLivre(
  entrepriseId,
  exerciceId,
  compteSelectionneId,
);

const compteSelectionne = computed(() =>
  (balance.value ?? []).find((l) => l.compte_id === compteSelectionneId.value),
);

function ouvrirGrandLivre(ligne: LigneBalance): void {
  compteSelectionneId.value = ligne.compte_id;
  ongletActif.value = "grand-livre";
}

const colonnesBalance: ColonneTable<LigneBalance>[] = [
  { cle: "numero", libelle: "Numéro" },
  { cle: "libelle", libelle: "Libellé" },
  { cle: "total_debit", libelle: "Total débit" },
  { cle: "total_credit", libelle: "Total crédit" },
  { cle: "solde", libelle: "Solde" },
];

const colonnesComparaison: ColonneTable<LigneBalanceComparee>[] = [
  { cle: "numero", libelle: "Numéro" },
  { cle: "libelle", libelle: "Libellé" },
  { cle: "solde_n", libelle: "Solde N" },
  { cle: "solde_n1", libelle: "Solde N-1" },
  { cle: "variation_montant", libelle: "Variation" },
  { cle: "variation_pourcentage", libelle: "Variation %" },
];

const colonnesGrandLivre: ColonneTable<LigneGrandLivre>[] = [
  { cle: "date_ecriture", libelle: "Date" },
  { cle: "numero_ecriture", libelle: "N° écriture" },
  { cle: "libelle", libelle: "Libellé" },
  { cle: "debit", libelle: "Débit" },
  { cle: "credit", libelle: "Crédit" },
  { cle: "solde_progressif", libelle: "Solde progressif" },
];

const colonnesEcheancier: ColonneTable<LigneEcheance>[] = [
  { cle: "date_ecriture", libelle: "Date" },
  { cle: "numero_ecriture", libelle: "N° écriture" },
  { cle: "code_tiers", libelle: "Tiers" },
  { cle: "raison_sociale_tiers", libelle: "Raison sociale" },
  { cle: "libelle", libelle: "Libellé" },
  { cle: "montant", libelle: "Montant dû" },
  { cle: "date_echeance", libelle: "Échéance" },
  { cle: "jours_retard", libelle: "Retard" },
];

const colonnesBalanceAgee: ColonneTable<TrancheAgee>[] = [
  { cle: "code_tiers", libelle: "Tiers" },
  { cle: "raison_sociale_tiers", libelle: "Raison sociale" },
  { cle: "non_echu", libelle: "Non échu" },
  { cle: "jours_0_30", libelle: "0-30 j" },
  { cle: "jours_31_60", libelle: "31-60 j" },
  { cle: "jours_61_90", libelle: "61-90 j" },
  { cle: "jours_plus_90", libelle: "+90 j" },
  { cle: "echeance_inconnue", libelle: "Échéance inconnue" },
  { cle: "total", libelle: "Total" },
];

const colonnesPrevision: ColonneTable<LignePrevisionTresorerie>[] = [
  { cle: "date_echeance", libelle: "Échéance" },
  { cle: "libelle", libelle: "Libellé" },
  { cle: "montant", libelle: "Montant" },
  { cle: "solde_cumule", libelle: "Solde cumulé" },
];

function formater(valeur: string): string {
  return formaterMontant(valeur);
}

const totauxBalance = computed(() => {
  const lignes = balance.value ?? [];
  return {
    debit: lignes.reduce((s, l) => s + Number(l.total_debit), 0),
    credit: lignes.reduce((s, l) => s + Number(l.total_credit), 0),
  };
});

// --- Export Excel des états financiers (cahier des charges, section 9) -----

const exportEnCours = ref(false);
const erreurExport = ref<string | null>(null);

async function exporter(): Promise<void> {
  if (!exerciceId.value) return;
  erreurExport.value = null;
  exportEnCours.value = true;
  try {
    await exporterEtatsFinanciers(entrepriseId, exerciceId.value);
  } catch {
    erreurExport.value = "Échec de l'export. Réessayez dans un instant.";
  } finally {
    exportEnCours.value = false;
  }
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-lg font-semibold text-text">Tableaux de bord</h1>
    </div>

    <div class="flex items-center gap-3">
      <label class="text-sm font-medium text-text">Exercice</label>
      <select v-model="exerciceId" class="rounded-md border border-border px-3 py-2 text-sm text-text">
        <option v-if="!exercices || exercices.length === 0" :value="null" disabled>Aucun exercice</option>
        <option v-for="ex in exercices ?? []" :key="ex.id" :value="ex.id">
          {{ ex.date_debut }} → {{ ex.date_fin }} ({{ ex.statut }})
        </option>
      </select>
      <button
        v-if="exerciceId"
        type="button"
        class="rounded-md border border-border px-3 py-2 text-sm font-medium text-text hover:bg-surface-muted disabled:opacity-50"
        :disabled="exportEnCours"
        @click="exporter"
      >
        {{ exportEnCours ? "Export en cours…" : "Exporter les états financiers (Excel)" }}
      </button>
      <p v-if="erreurExport" class="text-sm text-danger">{{ erreurExport }}</p>
    </div>

    <div v-if="exerciceId" class="space-y-4">
      <div class="flex gap-1 border-b border-border">
        <button
          type="button"
          class="px-3 py-2 text-sm"
          :class="ongletActif === 'balance' ? 'border-b-2 border-primary font-medium text-primary' : 'text-text-muted'"
          @click="ongletActif = 'balance'"
        >
          Balance générale
        </button>
        <button
          type="button"
          class="px-3 py-2 text-sm"
          :class="ongletActif === 'comparaison' ? 'border-b-2 border-primary font-medium text-primary' : 'text-text-muted'"
          @click="ongletActif = 'comparaison'"
        >
          Comparaison N / N-1
        </button>
        <button
          type="button"
          class="px-3 py-2 text-sm"
          :class="ongletActif === 'resultat' ? 'border-b-2 border-primary font-medium text-primary' : 'text-text-muted'"
          @click="ongletActif = 'resultat'"
        >
          Compte de résultat
        </button>
        <button
          type="button"
          class="px-3 py-2 text-sm"
          :class="ongletActif === 'resultat-detaille' ? 'border-b-2 border-primary font-medium text-primary' : 'text-text-muted'"
          @click="ongletActif = 'resultat-detaille'"
        >
          Compte de résultat détaillé
        </button>
        <button
          type="button"
          class="px-3 py-2 text-sm"
          :class="ongletActif === 'bilan' ? 'border-b-2 border-primary font-medium text-primary' : 'text-text-muted'"
          @click="ongletActif = 'bilan'"
        >
          Bilan
        </button>
        <button
          type="button"
          class="px-3 py-2 text-sm"
          :class="ongletActif === 'grand-livre' ? 'border-b-2 border-primary font-medium text-primary' : 'text-text-muted'"
          @click="ongletActif = 'grand-livre'"
        >
          Grand livre
        </button>
        <button
          type="button"
          class="px-3 py-2 text-sm"
          :class="ongletActif === 'echeancier' ? 'border-b-2 border-primary font-medium text-primary' : 'text-text-muted'"
          @click="ongletActif = 'echeancier'"
        >
          Échéancier
        </button>
        <button
          type="button"
          class="px-3 py-2 text-sm"
          :class="ongletActif === 'balance-agee' ? 'border-b-2 border-primary font-medium text-primary' : 'text-text-muted'"
          @click="ongletActif = 'balance-agee'"
        >
          Balance âgée
        </button>
        <button
          type="button"
          class="px-3 py-2 text-sm"
          :class="ongletActif === 'prevision-tresorerie' ? 'border-b-2 border-primary font-medium text-primary' : 'text-text-muted'"
          @click="ongletActif = 'prevision-tresorerie'"
        >
          Prévision trésorerie
        </button>
        <button
          type="button"
          class="px-3 py-2 text-sm"
          :class="ongletActif === 'pilotage' ? 'border-b-2 border-primary font-medium text-primary' : 'text-text-muted'"
          @click="ongletActif = 'pilotage'"
        >
          Pilotage
        </button>
      </div>

      <div v-if="ongletActif === 'balance'" class="space-y-2">
        <p class="text-xs text-text-muted">Cliquer sur une ligne ouvre son grand livre.</p>
        <BaseDataTable
          :colonnes="colonnesBalance"
          :lignes="balance ?? []"
          :chargement="chargementBalance"
          message-vide="Aucune écriture validée pour cet exercice."
          @ligne-cliquee="ouvrirGrandLivre"
        >
          <template #cell-total_debit="{ valeur }">{{ formater(valeur) }}</template>
          <template #cell-total_credit="{ valeur }">{{ formater(valeur) }}</template>
          <template #cell-solde="{ valeur }">{{ formater(valeur) }}</template>
        </BaseDataTable>
        <p v-if="balance && balance.length > 0" class="text-right text-sm font-medium text-text">
          Totaux : débit {{ formaterMontant(totauxBalance.debit) }} — crédit {{ formaterMontant(totauxBalance.credit) }}
        </p>
      </div>

      <div v-else-if="ongletActif === 'comparaison'" class="space-y-2">
        <p v-if="comparaison && comparaison.length > 0 && comparaison[0].solde_n1 === null" class="text-sm text-text-muted">
          Cet exercice n'a pas d'exercice précédent renseigné — rien à comparer.
        </p>
        <BaseDataTable
          :colonnes="colonnesComparaison"
          :lignes="comparaison ?? []"
          :chargement="chargementComparaison"
          message-vide="Aucune écriture validée pour cet exercice."
        >
          <template #cell-solde_n="{ valeur }">{{ formater(valeur as string) }}</template>
          <template #cell-solde_n1="{ valeur }">{{ valeur != null ? formater(valeur as string) : "—" }}</template>
          <template #cell-variation_montant="{ valeur }">{{ valeur != null ? formater(valeur as string) : "—" }}</template>
          <template #cell-variation_pourcentage="{ valeur }">
            <span v-if="valeur == null">—</span>
            <span v-else :class="Number(valeur) >= 0 ? 'text-success' : 'text-danger'">
              {{ Number(valeur) >= 0 ? "+" : "" }}{{ Number(valeur).toFixed(1) }} %
            </span>
          </template>
        </BaseDataTable>
      </div>

      <div v-else-if="ongletActif === 'resultat'" class="space-y-4">
        <div v-if="chargementResultat" class="text-sm text-text-muted">Chargement…</div>
        <div v-else-if="resultat" class="grid grid-cols-3 gap-4">
          <div class="rounded-lg border border-border bg-surface p-6">
            <p class="text-xs text-text-muted">Total charges</p>
            <p class="text-lg font-semibold text-text">{{ formater(resultat.total_charges) }}</p>
          </div>
          <div class="rounded-lg border border-border bg-surface p-6">
            <p class="text-xs text-text-muted">Total produits</p>
            <p class="text-lg font-semibold text-text">{{ formater(resultat.total_produits) }}</p>
          </div>
          <div class="rounded-lg border border-border bg-surface p-6">
            <p class="text-xs text-text-muted">Résultat net</p>
            <p
              class="text-lg font-semibold"
              :class="Number(resultat.resultat_net) >= 0 ? 'text-success' : 'text-danger'"
            >
              {{ formater(resultat.resultat_net) }}
            </p>
          </div>
        </div>
      </div>

      <div v-else-if="ongletActif === 'resultat-detaille'" class="space-y-4">
        <div v-if="chargementResultatDetaille" class="text-sm text-text-muted">Chargement…</div>
        <div v-else-if="resultatDetaille" class="space-y-4">
          <p class="text-xs text-text-muted">
            Répartition exploitation / financier selon le préfixe du numéro de compte (67x, 77x) ; le HAO (classe 8)
            est réparti selon le sens du solde de chaque compte — simplification documentée tant que le référentiel
            comptable exact n'est pas validé (cahier des charges, section 35.2).
          </p>

          <div>
            <h2 class="mb-2 text-sm font-medium text-text">Exploitation</h2>
            <div class="grid grid-cols-3 gap-4">
              <div class="rounded-lg border border-border bg-surface p-6">
                <p class="text-xs text-text-muted">Charges</p>
                <p class="text-lg font-semibold text-text">{{ formater(resultatDetaille.total_charges_exploitation) }}</p>
              </div>
              <div class="rounded-lg border border-border bg-surface p-6">
                <p class="text-xs text-text-muted">Produits</p>
                <p class="text-lg font-semibold text-text">{{ formater(resultatDetaille.total_produits_exploitation) }}</p>
              </div>
              <div class="rounded-lg border border-border bg-surface p-6">
                <p class="text-xs text-text-muted">Résultat exploitation</p>
                <p
                  class="text-lg font-semibold"
                  :class="Number(resultatDetaille.resultat_exploitation) >= 0 ? 'text-success' : 'text-danger'"
                >
                  {{ formater(resultatDetaille.resultat_exploitation) }}
                </p>
              </div>
            </div>
          </div>

          <div>
            <h2 class="mb-2 text-sm font-medium text-text">Financier</h2>
            <div class="grid grid-cols-3 gap-4">
              <div class="rounded-lg border border-border bg-surface p-6">
                <p class="text-xs text-text-muted">Charges financières</p>
                <p class="text-lg font-semibold text-text">{{ formater(resultatDetaille.total_charges_financieres) }}</p>
              </div>
              <div class="rounded-lg border border-border bg-surface p-6">
                <p class="text-xs text-text-muted">Produits financiers</p>
                <p class="text-lg font-semibold text-text">{{ formater(resultatDetaille.total_produits_financiers) }}</p>
              </div>
              <div class="rounded-lg border border-border bg-surface p-6">
                <p class="text-xs text-text-muted">Résultat financier</p>
                <p
                  class="text-lg font-semibold"
                  :class="Number(resultatDetaille.resultat_financier) >= 0 ? 'text-success' : 'text-danger'"
                >
                  {{ formater(resultatDetaille.resultat_financier) }}
                </p>
              </div>
            </div>
          </div>

          <div class="rounded-lg border border-border bg-surface p-6">
            <p class="text-xs text-text-muted">Résultat des activités ordinaires</p>
            <p
              class="text-lg font-semibold"
              :class="Number(resultatDetaille.resultat_activites_ordinaires) >= 0 ? 'text-success' : 'text-danger'"
            >
              {{ formater(resultatDetaille.resultat_activites_ordinaires) }}
            </p>
          </div>

          <div>
            <h2 class="mb-2 text-sm font-medium text-text">Hors activités ordinaires (HAO)</h2>
            <div class="grid grid-cols-3 gap-4">
              <div class="rounded-lg border border-border bg-surface p-6">
                <p class="text-xs text-text-muted">Charges HAO</p>
                <p class="text-lg font-semibold text-text">{{ formater(resultatDetaille.total_charges_hao) }}</p>
              </div>
              <div class="rounded-lg border border-border bg-surface p-6">
                <p class="text-xs text-text-muted">Produits HAO</p>
                <p class="text-lg font-semibold text-text">{{ formater(resultatDetaille.total_produits_hao) }}</p>
              </div>
              <div class="rounded-lg border border-border bg-surface p-6">
                <p class="text-xs text-text-muted">Résultat HAO</p>
                <p
                  class="text-lg font-semibold"
                  :class="Number(resultatDetaille.resultat_hao) >= 0 ? 'text-success' : 'text-danger'"
                >
                  {{ formater(resultatDetaille.resultat_hao) }}
                </p>
              </div>
            </div>
          </div>

          <div class="rounded-lg border border-primary bg-primary/5 p-6">
            <p class="text-xs text-text-muted">Résultat net</p>
            <p
              class="text-xl font-semibold"
              :class="Number(resultatDetaille.resultat_net) >= 0 ? 'text-success' : 'text-danger'"
            >
              {{ formater(resultatDetaille.resultat_net) }}
            </p>
          </div>
        </div>
      </div>

      <div v-else-if="ongletActif === 'bilan'" class="space-y-4">
        <div v-if="chargementBilan" class="text-sm text-text-muted">Chargement…</div>
        <div v-else-if="bilan" class="grid grid-cols-2 gap-6">
          <div class="space-y-2">
            <h2 class="text-sm font-medium text-text">Actif</h2>
            <div class="space-y-2 rounded-lg border border-border bg-surface p-4">
              <div class="flex justify-between text-sm">
                <span class="text-text-muted">Immobilisations</span>
                <span class="text-text">{{ formater(bilan.immobilisations) }}</span>
              </div>
              <div class="flex justify-between text-sm">
                <span class="text-text-muted">Stocks</span>
                <span class="text-text">{{ formater(bilan.stocks) }}</span>
              </div>
              <div class="flex justify-between text-sm">
                <span class="text-text-muted">Créances</span>
                <span class="text-text">{{ formater(bilan.creances) }}</span>
              </div>
              <div class="flex justify-between text-sm">
                <span class="text-text-muted">Trésorerie</span>
                <span class="text-text">{{ formater(bilan.tresorerie_actif) }}</span>
              </div>
              <div class="flex justify-between border-t border-border pt-2 text-sm font-semibold">
                <span class="text-text">Total actif</span>
                <span class="text-text">{{ formater(bilan.total_actif) }}</span>
              </div>
            </div>
          </div>

          <div class="space-y-2">
            <h2 class="text-sm font-medium text-text">Passif</h2>
            <div class="space-y-2 rounded-lg border border-border bg-surface p-4">
              <div class="flex justify-between text-sm">
                <span class="text-text-muted">Ressources durables</span>
                <span class="text-text">{{ formater(bilan.ressources_durables) }}</span>
              </div>
              <div class="flex justify-between text-sm">
                <span class="text-text-muted">Dettes circulantes</span>
                <span class="text-text">{{ formater(bilan.dettes_circulantes) }}</span>
              </div>
              <div class="flex justify-between text-sm">
                <span class="text-text-muted">Trésorerie passif</span>
                <span class="text-text">{{ formater(bilan.tresorerie_passif) }}</span>
              </div>
              <div class="flex justify-between border-t border-border pt-2 text-sm font-semibold">
                <span class="text-text">Total passif</span>
                <span class="text-text">{{ formater(bilan.total_passif) }}</span>
              </div>
            </div>
          </div>

          <div class="col-span-2">
            <p v-if="bilan.equilibre" class="text-sm font-medium text-success">
              Bilan équilibré (actif = passif).
            </p>
            <p v-else class="text-sm font-medium text-danger">
              Bilan déséquilibré : vérifier les écritures de cet exercice.
            </p>
          </div>
        </div>
      </div>

      <div v-else-if="ongletActif === 'grand-livre'" class="space-y-2">
        <p v-if="!compteSelectionneId" class="text-sm text-text-muted">
          Choisissez un compte depuis la balance générale pour afficher son grand livre.
        </p>
        <template v-else>
          <h2 class="text-sm font-medium text-text">
            {{ compteSelectionne?.numero }} — {{ compteSelectionne?.libelle }}
          </h2>
          <BaseDataTable
            :colonnes="colonnesGrandLivre"
            :lignes="grandLivre ?? []"
            :chargement="chargementGrandLivre"
            message-vide="Aucun mouvement pour ce compte sur cet exercice."
          >
            <template #cell-numero_ecriture="{ valeur }">{{ valeur ?? "—" }}</template>
            <template #cell-debit="{ valeur }">{{ formater(valeur as string) }}</template>
            <template #cell-credit="{ valeur }">{{ formater(valeur as string) }}</template>
            <template #cell-solde_progressif="{ valeur }">{{ formater(valeur as string) }}</template>
          </BaseDataTable>
        </template>
      </div>

      <div v-else-if="ongletActif === 'echeancier' || ongletActif === 'balance-agee'" class="space-y-2">
        <div class="flex gap-2">
          <button
            type="button"
            class="rounded-md border px-3 py-1 text-sm"
            :class="typeTiersEcheancier === 'client' ? 'border-primary bg-primary/10 font-medium text-primary' : 'border-border text-text-muted'"
            @click="typeTiersEcheancier = 'client'"
          >
            Clients
          </button>
          <button
            type="button"
            class="rounded-md border px-3 py-1 text-sm"
            :class="typeTiersEcheancier === 'fournisseur' ? 'border-primary bg-primary/10 font-medium text-primary' : 'border-border text-text-muted'"
            @click="typeTiersEcheancier = 'fournisseur'"
          >
            Fournisseurs
          </button>
        </div>

        <template v-if="ongletActif === 'echeancier'">
          <BaseDataTable
            :colonnes="colonnesEcheancier"
            :lignes="echeancier ?? []"
            :chargement="chargementEcheancier"
            message-vide="Aucune ligne ouverte (tout est lettré ou aucune écriture)."
          >
            <template #cell-numero_ecriture="{ valeur }">{{ valeur ?? "—" }}</template>
            <template #cell-montant="{ valeur }">{{ formater(valeur as string) }}</template>
            <template #cell-date_echeance="{ valeur }">{{ valeur ?? "—" }}</template>
            <template #cell-jours_retard="{ valeur }">
              <span v-if="valeur == null" class="text-text-muted">—</span>
              <span v-else-if="(valeur as number) > 0" class="text-danger">{{ valeur }} j</span>
              <span v-else class="text-text-muted">à échoir</span>
            </template>
          </BaseDataTable>
        </template>

        <template v-else>
          <BaseDataTable
            :colonnes="colonnesBalanceAgee"
            :lignes="balanceAgee ?? []"
            :chargement="chargementBalanceAgee"
            message-vide="Aucune ligne ouverte (tout est lettré ou aucune écriture)."
          >
            <template #cell-non_echu="{ valeur }">{{ formater(valeur as string) }}</template>
            <template #cell-jours_0_30="{ valeur }">{{ formater(valeur as string) }}</template>
            <template #cell-jours_31_60="{ valeur }">{{ formater(valeur as string) }}</template>
            <template #cell-jours_61_90="{ valeur }">{{ formater(valeur as string) }}</template>
            <template #cell-jours_plus_90="{ valeur }">{{ formater(valeur as string) }}</template>
            <template #cell-echeance_inconnue="{ valeur }">{{ formater(valeur as string) }}</template>
            <template #cell-total="{ valeur }">{{ formater(valeur as string) }}</template>
          </BaseDataTable>
        </template>
      </div>

      <div v-else-if="ongletActif === 'prevision-tresorerie'" class="space-y-4">
        <div class="flex items-center gap-2">
          <label class="text-sm font-medium text-text">Horizon</label>
          <button
            v-for="h in horizonsDisponibles"
            :key="h"
            type="button"
            class="rounded-md border px-3 py-1 text-sm"
            :class="horizonJours === h ? 'border-primary bg-primary/10 font-medium text-primary' : 'border-border text-text-muted'"
            @click="horizonJours = h"
          >
            {{ h }} j
          </button>
        </div>

        <div v-if="chargementPrevision" class="text-sm text-text-muted">Chargement…</div>
        <template v-else-if="prevision">
          <div class="grid grid-cols-2 gap-4">
            <div class="rounded-lg border border-border bg-surface p-6">
              <p class="text-xs text-text-muted">Solde actuel</p>
              <p class="text-lg font-semibold text-text">{{ formater(prevision.solde_actuel) }}</p>
            </div>
            <div class="rounded-lg border border-primary bg-primary/5 p-6">
              <p class="text-xs text-text-muted">Solde projeté à {{ prevision.horizon_jours }} jours</p>
              <p
                class="text-lg font-semibold"
                :class="Number(prevision.solde_final_projete) >= 0 ? 'text-success' : 'text-danger'"
              >
                {{ formater(prevision.solde_final_projete) }}
              </p>
            </div>
          </div>

          <BaseDataTable
            :colonnes="colonnesPrevision"
            :lignes="prevision.lignes"
            :chargement="false"
            message-vide="Aucune échéance connue sur cet horizon."
          >
            <template #cell-montant="{ valeur }">
              <span :class="Number(valeur) >= 0 ? 'text-success' : 'text-danger'">{{ formater(valeur as string) }}</span>
            </template>
            <template #cell-solde_cumule="{ valeur }">{{ formater(valeur as string) }}</template>
          </BaseDataTable>

          <p class="text-xs text-text-muted">
            Hors échéances : {{ Number(prevision.montant_sans_echeance_clients) !== 0 || Number(prevision.montant_sans_echeance_fournisseurs) !== 0
              ? `créances clients sans date d'échéance ${formater(prevision.montant_sans_echeance_clients)} — dettes fournisseurs sans date d'échéance ${formater(prevision.montant_sans_echeance_fournisseurs)} (non inclus dans la projection ci-dessus)`
              : "aucune" }}
          </p>
        </template>
      </div>

      <div v-else-if="ongletActif === 'pilotage'" class="space-y-6">
        <div v-if="aPermission('notification.administrer')" class="flex items-center gap-3">
          <button
            type="button"
            class="rounded-md bg-primary px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
            :disabled="mutationDetecterAlertes.isPending.value"
            @click="lancerDetectionAlertes"
          >
            {{ mutationDetecterAlertes.isPending.value ? "Détection en cours…" : "Lancer la détection des alertes" }}
          </button>
          <p v-if="resultatDetection" class="text-sm text-text-muted">
            <template v-if="Object.keys(resultatDetection).length === 0">
              Aucune nouvelle alerte à signaler.
            </template>
            <template v-else>
              {{
                Object.entries(resultatDetection)
                  .map(([type, n]) => `${LIBELLES_TYPES_ALERTE[type] ?? type} (${n})`)
                  .join(", ")
              }}
            </template>
          </p>
        </div>
        <p class="text-xs text-text-muted">
          Cahier des charges, section 22. Aucun indicateur "anomalies" (aucune notion équivalente dans ce projet) ;
          "rapprochements en attente" est représenté par les lignes de relevé bancaire non lettrées.
        </p>

        <div>
          <h2 class="mb-2 text-sm font-medium text-text">Direction</h2>
          <div v-if="chargementTableauDirection" class="text-sm text-text-muted">Chargement…</div>
          <div v-else-if="tableauDirection" class="grid grid-cols-3 gap-4">
            <div class="rounded-lg border border-border bg-surface p-6">
              <p class="text-xs text-text-muted">Trésorerie disponible</p>
              <p class="text-lg font-semibold text-text">{{ formater(tableauDirection.tresorerie_disponible) }}</p>
            </div>
            <div class="rounded-lg border border-border bg-surface p-6">
              <p class="text-xs text-text-muted">Créances clients ouvertes</p>
              <p class="text-lg font-semibold text-text">{{ formater(tableauDirection.creances_clients_ouvertes) }}</p>
            </div>
            <div class="rounded-lg border border-border bg-surface p-6">
              <p class="text-xs text-text-muted">Dettes fournisseurs ouvertes</p>
              <p class="text-lg font-semibold text-text">
                {{ formater(tableauDirection.dettes_fournisseurs_ouvertes) }}
              </p>
            </div>
            <div class="rounded-lg border border-border bg-surface p-6">
              <p class="text-xs text-text-muted">Échéances clients en retard</p>
              <p
                class="text-lg font-semibold"
                :class="tableauDirection.echeances_clients_en_retard > 0 ? 'text-danger' : 'text-text'"
              >
                {{ tableauDirection.echeances_clients_en_retard }}
              </p>
            </div>
            <div class="rounded-lg border border-border bg-surface p-6">
              <p class="text-xs text-text-muted">Échéances fournisseurs en retard</p>
              <p
                class="text-lg font-semibold"
                :class="tableauDirection.echeances_fournisseurs_en_retard > 0 ? 'text-danger' : 'text-text'"
              >
                {{ tableauDirection.echeances_fournisseurs_en_retard }}
              </p>
            </div>
            <div class="rounded-lg border border-primary bg-primary/5 p-6">
              <p class="text-xs text-text-muted">Résultat net (exercice courant)</p>
              <p v-if="tableauDirection.resultat_net_exercice == null" class="text-sm text-text-muted">
                Aucun exercice courant
              </p>
              <p
                v-else
                class="text-lg font-semibold"
                :class="Number(tableauDirection.resultat_net_exercice) >= 0 ? 'text-success' : 'text-danger'"
              >
                {{ formater(tableauDirection.resultat_net_exercice) }}
              </p>
            </div>
          </div>
        </div>

        <div>
          <h2 class="mb-2 text-sm font-medium text-text">Comptabilité</h2>
          <div v-if="chargementTableauComptabilite" class="text-sm text-text-muted">Chargement…</div>
          <div v-else-if="tableauComptabilite" class="grid grid-cols-4 gap-4">
            <div class="rounded-lg border border-border bg-surface p-6">
              <p class="text-xs text-text-muted">Écritures en brouillon</p>
              <p class="text-lg font-semibold text-text">{{ tableauComptabilite.ecritures_brouillon }}</p>
            </div>
            <div class="rounded-lg border border-border bg-surface p-6">
              <p class="text-xs text-text-muted">Lignes bancaires non lettrées</p>
              <p class="text-lg font-semibold text-text">{{ tableauComptabilite.lignes_bancaires_non_lettrees }}</p>
            </div>
            <div class="rounded-lg border border-border bg-surface p-6">
              <p class="text-xs text-text-muted">Clôtures à venir (30 j)</p>
              <p class="text-lg font-semibold text-text">{{ tableauComptabilite.clotures_a_venir }}</p>
            </div>
            <div class="rounded-lg border border-border bg-surface p-6">
              <p class="text-xs text-text-muted">Demandes clients non traitées</p>
              <p class="text-lg font-semibold text-text">{{ tableauComptabilite.demandes_non_traitees }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
    <p v-else class="text-sm text-text-muted">Aucun exercice disponible pour cette entreprise.</p>
  </div>
</template>