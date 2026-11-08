<script setup lang="ts">
/**
 * Fiche article : informations descriptives (modification limitée au
 * libellé/unité, voir ArticleMiseAJour), historique des mouvements,
 * saisie d'une entrée ou d'une sortie, et génération de l'écriture
 * comptable d'un mouvement (journal + compte de contrepartie fournis à
 * la demande, voir la note de GenerationEcritureMouvementDemande).
 */
import { computed, reactive, ref } from "vue";
import { useRoute } from "vue-router";

import { useAuth } from "@/core/auth/useAuth";
import { messageErreur } from "@/core/api/erreurs";
import BaseDataTable, { type ColonneTable } from "@/core/ui/BaseDataTable.vue";
import { formaterMontant } from "@/core/ui/formatage";
import { useComptesEntreprise, useJournaux } from "@/modules/comptabilite/api";
import { useExercices } from "@/modules/exercices/api";
import {
  useArticle,
  useInventairesPhysiques,
  useLignesConsommation,
  useMouvements,
  useMutationsArticles,
  useMutationsInventairesPhysiques,
  useMutationsMouvements,
} from "./api";
import type { InventairePhysique, MouvementStock } from "./types";

const route = useRoute();
const { contexteActif, aPermission } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);
const articleId = computed(() => route.params.id as string);

const { data: article } = useArticle(entrepriseId, articleId);
const { data: mouvements, isLoading: chargementMouvements } = useMouvements(entrepriseId, articleId);
const { modifier } = useMutationsArticles(entrepriseId);
const { creerEntree, creerSortie, genererEcriture } = useMutationsMouvements(entrepriseId);

const { data: journaux } = useJournaux(entrepriseId);
const { data: comptes } = useComptesEntreprise(entrepriseId);
const { data: exercices } = useExercices(entrepriseId);
const { data: inventaires, isLoading: chargementInventaires } = useInventairesPhysiques(entrepriseId, articleId);
const { creer: creerInventaire } = useMutationsInventairesPhysiques(entrepriseId);

const libellesMethode: Record<string, string> = { cmup: "CMUP", fifo: "FIFO" };

// --- Édition descriptive -----------------------------------------------

const editionOuverte = ref(false);
const edition = reactive({ libelle: "", unite: "" });
const erreurEdition = ref<string | null>(null);

function ouvrirEdition(): void {
  if (!article.value) return;
  edition.libelle = article.value.libelle;
  edition.unite = article.value.unite;
  editionOuverte.value = true;
}

async function soumettreEdition(): Promise<void> {
  erreurEdition.value = null;
  try {
    await modifier.mutateAsync({ id: articleId.value, donnees: { ...edition } });
    editionOuverte.value = false;
  } catch (e) {
    erreurEdition.value = messageErreur(e);
  }
}

// --- Saisie d'un mouvement -----------------------------------------------

type SensMouvement = "entree" | "sortie";
const sensMouvement = ref<SensMouvement>("entree");
const formulaireMouvementOuvert = ref(false);
const formulaireMouvement = reactive({
  date_mouvement: new Date().toISOString().slice(0, 10),
  quantite: "",
  cout_unitaire: "",
  reference: "",
  libelle: "",
});
const erreurMouvement = ref<string | null>(null);

async function soumettreMouvement(): Promise<void> {
  erreurMouvement.value = null;
  try {
    if (sensMouvement.value === "entree") {
      await creerEntree.mutateAsync({
        article_id: articleId.value,
        date_mouvement: formulaireMouvement.date_mouvement,
        quantite: formulaireMouvement.quantite,
        cout_unitaire: formulaireMouvement.cout_unitaire,
        reference: formulaireMouvement.reference || null,
        libelle: formulaireMouvement.libelle || null,
      });
    } else {
      await creerSortie.mutateAsync({
        article_id: articleId.value,
        date_mouvement: formulaireMouvement.date_mouvement,
        quantite: formulaireMouvement.quantite,
        reference: formulaireMouvement.reference || null,
        libelle: formulaireMouvement.libelle || null,
      });
    }
    formulaireMouvementOuvert.value = false;
    formulaireMouvement.quantite = "";
    formulaireMouvement.cout_unitaire = "";
    formulaireMouvement.reference = "";
    formulaireMouvement.libelle = "";
  } catch (e) {
    erreurMouvement.value = messageErreur(e);
  }
}

const colonnesMouvements: ColonneTable<MouvementStock>[] = [
  { cle: "date_mouvement", libelle: "Date" },
  { cle: "type_mouvement", libelle: "Sens" },
  { cle: "quantite", libelle: "Quantité" },
  { cle: "cout_unitaire", libelle: "Coût unitaire" },
  { cle: "cout_total", libelle: "Coût total" },
  { cle: "reference", libelle: "Référence" },
  { cle: "ecriture_id", libelle: "Écriture" },
];

// --- Lignes de consommation (FIFO) d'une sortie sélectionnée --------------

const mouvementSelectionneId = ref<string | null>(null);
const { data: lignesConsommation } = useLignesConsommation(entrepriseId, mouvementSelectionneId);

function voirConsommation(mouvement: MouvementStock): void {
  mouvementSelectionneId.value = mouvement.type_mouvement === "sortie" ? mouvement.id : null;
}

// --- Génération d'écriture --------------------------------------------------

const mouvementAGenererId = ref<string | null>(null);
const generation = reactive({ journal_id: "", compte_contrepartie_id: "" });
const erreurGeneration = ref<string | null>(null);

function ouvrirGeneration(mouvement: MouvementStock): void {
  mouvementAGenererId.value = mouvement.id;
  generation.journal_id = "";
  generation.compte_contrepartie_id = "";
  erreurGeneration.value = null;
}

async function soumettreGeneration(): Promise<void> {
  if (!mouvementAGenererId.value) return;
  erreurGeneration.value = null;
  try {
    await genererEcriture.mutateAsync({
      mouvementId: mouvementAGenererId.value,
      donnees: { ...generation },
    });
    mouvementAGenererId.value = null;
  } catch (e) {
    erreurGeneration.value = messageErreur(e);
  }
}

// --- Inventaire physique de fin d'exercice -------------------------------
//
// Le journal et le compte de contrepartie sont toujours affichés mais
// réellement optionnels : le backend ne les exige que si le comptage fait
// apparaître un écart (voir ServiceStocks.creer_inventaire_physique). On ne
// connaît l'écart qu'après soumission (il dépend du stock théorique au
// moment du comptage), donc pas de pré-affichage conditionnel ici — un 422
// explicite invite à les renseigner si besoin.

const inventaireOuvert = ref(false);
const inventaire = reactive({
  exercice_id: "",
  date_inventaire: new Date().toISOString().slice(0, 10),
  quantite_physique: "",
  journal_id: "",
  compte_contrepartie_id: "",
});
const erreurInventaire = ref<string | null>(null);

async function soumettreInventaire(): Promise<void> {
  erreurInventaire.value = null;
  try {
    await creerInventaire.mutateAsync({
      article_id: articleId.value,
      exercice_id: inventaire.exercice_id,
      date_inventaire: inventaire.date_inventaire,
      quantite_physique: inventaire.quantite_physique,
      journal_id: inventaire.journal_id || null,
      compte_contrepartie_id: inventaire.compte_contrepartie_id || null,
    });
    inventaireOuvert.value = false;
    inventaire.quantite_physique = "";
    inventaire.journal_id = "";
    inventaire.compte_contrepartie_id = "";
  } catch (e) {
    erreurInventaire.value = messageErreur(e);
  }
}

function libelleEcart(inv: InventairePhysique): string {
  if (inv.mouvement_ajustement_id === null) return "Aucun écart";
  return Number(inv.ecart) > 0 ? "Surplus" : "Manquant";
}
</script>

<template>
  <div v-if="article" class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-lg font-semibold text-text">{{ article.code }} — {{ article.libelle }}</h1>
        <p class="text-sm text-text-muted">
          Méthode de valorisation : {{ libellesMethode[article.methode_valorisation] }} (fixée à la création)
        </p>
      </div>
      <button
        v-if="aPermission('article.modifier')"
        type="button"
        class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted"
        @click="ouvrirEdition"
      >
        Modifier
      </button>
    </div>

    <div class="grid grid-cols-3 gap-4 rounded-lg border border-border bg-surface p-6">
      <div>
        <p class="text-xs text-text-muted">Quantité en stock</p>
        <p class="text-lg font-semibold text-text">{{ article.quantite_en_stock }} {{ article.unite }}</p>
      </div>
      <div>
        <p class="text-xs text-text-muted">Coût unitaire moyen</p>
        <p class="text-lg font-semibold text-text">{{ formaterMontant(article.cout_unitaire_moyen) }}</p>
      </div>
      <div>
        <p class="text-xs text-text-muted">Valeur du stock</p>
        <p class="text-lg font-semibold text-text">{{ formaterMontant(article.valeur_stock) }}</p>
      </div>
    </div>

    <form
      v-if="editionOuverte"
      class="space-y-4 rounded-lg border border-border bg-surface p-6"
      @submit.prevent="soumettreEdition"
    >
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Libellé</label>
          <input v-model="edition.libelle" required class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Unité</label>
          <input v-model="edition.unite" required class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
      </div>
      <p v-if="erreurEdition" class="text-sm text-danger">{{ erreurEdition }}</p>
      <div class="flex justify-end gap-2">
        <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted" @click="editionOuverte = false">
          Annuler
        </button>
        <button type="submit" :disabled="modifier.isPending.value" class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60">
          Enregistrer
        </button>
      </div>
    </form>

    <div class="flex items-center justify-between">
      <h2 class="text-base font-semibold text-text">Mouvements</h2>
      <div class="flex gap-2">
        <button
          v-if="aPermission('mouvement_stock.creer')"
          type="button"
          class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover"
          @click="sensMouvement = 'entree'; formulaireMouvementOuvert = true"
        >
          Nouvelle entrée
        </button>
        <button
          v-if="aPermission('mouvement_stock.creer')"
          type="button"
          class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted"
          @click="sensMouvement = 'sortie'; formulaireMouvementOuvert = true"
        >
          Nouvelle sortie
        </button>
      </div>
    </div>

    <form
      v-if="formulaireMouvementOuvert"
      class="space-y-4 rounded-lg border border-border bg-surface p-6"
      @submit.prevent="soumettreMouvement"
    >
      <h3 class="text-sm font-medium text-text">
        {{ sensMouvement === "entree" ? "Nouvelle entrée de stock" : "Nouvelle sortie de stock" }}
      </h3>
      <div class="grid grid-cols-4 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Date</label>
          <input v-model="formulaireMouvement.date_mouvement" type="date" required class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Quantité</label>
          <input v-model="formulaireMouvement.quantite" type="number" step="0.001" min="0.001" required class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div v-if="sensMouvement === 'entree'">
          <label class="mb-1 block text-sm font-medium text-text">Coût unitaire</label>
          <input v-model="formulaireMouvement.cout_unitaire" type="number" step="0.0001" min="0" required class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Référence</label>
          <input v-model="formulaireMouvement.reference" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
      </div>
      <div>
        <label class="mb-1 block text-sm font-medium text-text">Libellé</label>
        <input v-model="formulaireMouvement.libelle" class="w-full rounded-md border border-border px-3 py-2 text-text" />
      </div>
      <p v-if="sensMouvement === 'sortie'" class="text-xs text-text-muted">
        Le coût de la sortie est calculé automatiquement selon la méthode de valorisation de l'article
        ({{ libellesMethode[article.methode_valorisation] }}) ; une sortie dépassant le stock disponible est refusée.
      </p>
      <p v-if="erreurMouvement" class="text-sm text-danger">{{ erreurMouvement }}</p>
      <div class="flex justify-end gap-2">
        <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted" @click="formulaireMouvementOuvert = false">
          Annuler
        </button>
        <button
          type="submit"
          :disabled="creerEntree.isPending.value || creerSortie.isPending.value"
          class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60"
        >
          Enregistrer
        </button>
      </div>
    </form>

    <BaseDataTable
      :colonnes="colonnesMouvements"
      :lignes="mouvements ?? []"
      :chargement="chargementMouvements"
      message-vide="Aucun mouvement pour le moment."
      @ligne-cliquee="voirConsommation"
    >
      <template #cell-type_mouvement="{ valeur }">{{ valeur === "entree" ? "Entrée" : "Sortie" }}</template>
      <template #cell-cout_unitaire="{ valeur }">{{ formaterMontant(valeur as string) }}</template>
      <template #cell-cout_total="{ valeur }">{{ formaterMontant(valeur as string) }}</template>
      <template #cell-reference="{ valeur }">{{ valeur ?? "—" }}</template>
      <template #cell-ecriture_id="{ ligne, valeur }">
        <span v-if="valeur" class="text-sm text-success">Générée</span>
        <button
          v-else-if="aPermission('mouvement_stock.creer')"
          type="button"
          class="text-xs text-primary hover:underline"
          @click.stop="ouvrirGeneration(ligne)"
        >
          Générer l'écriture
        </button>
      </template>
    </BaseDataTable>

    <div
      v-if="mouvementSelectionneId && lignesConsommation && lignesConsommation.length > 0"
      class="space-y-2 rounded-lg border border-border bg-surface p-4"
    >
      <h3 class="text-sm font-medium text-text">Lots consommés (FIFO)</h3>
      <table class="w-full text-sm text-text">
        <thead>
          <tr class="text-left text-text-muted">
            <th class="pb-1">Lot</th>
            <th class="pb-1">Quantité consommée</th>
            <th class="pb-1">Coût unitaire du lot</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="l in lignesConsommation" :key="l.id">
            <td class="py-1">{{ l.lot_id }}</td>
            <td class="py-1">{{ l.quantite_consommee }}</td>
            <td class="py-1">{{ formaterMontant(l.cout_unitaire) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <form
      v-if="mouvementAGenererId"
      class="space-y-4 rounded-lg border border-border bg-surface p-6"
      @submit.prevent="soumettreGeneration"
    >
      <h3 class="text-sm font-medium text-text">Générer l'écriture comptable du mouvement</h3>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Journal</label>
          <select v-model="generation.journal_id" required class="w-full rounded-md border border-border px-3 py-2 text-text">
            <option value="" disabled>Choisir un journal</option>
            <option v-for="j in journaux ?? []" :key="j.id" :value="j.id">{{ j.code }} — {{ j.libelle }}</option>
          </select>
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Compte de contrepartie</label>
          <select v-model="generation.compte_contrepartie_id" required class="w-full rounded-md border border-border px-3 py-2 text-text">
            <option value="" disabled>Choisir un compte</option>
            <option v-for="c in comptes ?? []" :key="c.id" :value="c.id">{{ c.numero }} — {{ c.libelle }}</option>
          </select>
        </div>
      </div>
      <p v-if="erreurGeneration" class="text-sm text-danger">{{ erreurGeneration }}</p>
      <div class="flex justify-end gap-2">
        <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted" @click="mouvementAGenererId = null">
          Annuler
        </button>
        <button type="submit" :disabled="genererEcriture.isPending.value" class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60">
          Générer
        </button>
      </div>
    </form>

    <div class="flex items-center justify-between">
      <h2 class="text-base font-semibold text-text">Inventaire physique de fin d'exercice</h2>
      <button
        v-if="aPermission('inventaire_physique.creer') && !inventaireOuvert"
        type="button"
        class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted"
        @click="inventaireOuvert = true"
      >
        Nouveau comptage
      </button>
    </div>

    <form
      v-if="inventaireOuvert"
      class="space-y-4 rounded-lg border border-border bg-surface p-6"
      @submit.prevent="soumettreInventaire"
    >
      <p class="text-xs text-text-muted">
        Stock théorique actuel : {{ article.quantite_en_stock }} {{ article.unite }}. Si le comptage
        physique diffère, un mouvement de correction (et son écriture) sera généré automatiquement —
        le journal et le compte de contrepartie ne sont alors requis que dans ce cas.
      </p>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Exercice</label>
          <select v-model="inventaire.exercice_id" required class="w-full rounded-md border border-border px-3 py-2 text-text">
            <option value="" disabled>— Choisir —</option>
            <option v-for="e in exercices" :key="e.id" :value="e.id">{{ e.date_debut }} → {{ e.date_fin }}</option>
          </select>
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Date du comptage</label>
          <input v-model="inventaire.date_inventaire" type="date" required class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
      </div>
      <div>
        <label class="mb-1 block text-sm font-medium text-text">Quantité physique comptée</label>
        <input v-model="inventaire.quantite_physique" type="number" step="0.001" min="0" required class="w-full rounded-md border border-border px-3 py-2 text-text" />
      </div>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Journal (si écart)</label>
          <select v-model="inventaire.journal_id" class="w-full rounded-md border border-border px-3 py-2 text-text">
            <option value="">— Aucun —</option>
            <option v-for="j in journaux ?? []" :key="j.id" :value="j.id">{{ j.code }} — {{ j.libelle }}</option>
          </select>
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Compte de contrepartie (si écart)</label>
          <select v-model="inventaire.compte_contrepartie_id" class="w-full rounded-md border border-border px-3 py-2 text-text">
            <option value="">— Aucun —</option>
            <option v-for="c in comptes ?? []" :key="c.id" :value="c.id">{{ c.numero }} — {{ c.libelle }}</option>
          </select>
        </div>
      </div>
      <p v-if="erreurInventaire" class="text-sm text-danger">{{ erreurInventaire }}</p>
      <div class="flex justify-end gap-2">
        <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted" @click="inventaireOuvert = false">
          Annuler
        </button>
        <button type="submit" :disabled="creerInventaire.isPending.value" class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60">
          Enregistrer le comptage
        </button>
      </div>
    </form>

    <div class="overflow-hidden rounded-lg border border-border bg-surface">
      <table class="w-full text-sm">
        <thead class="bg-surface-muted text-left text-xs font-medium uppercase text-text-muted">
          <tr>
            <th class="px-3 py-2">Date</th>
            <th class="px-3 py-2 text-right">Théorique</th>
            <th class="px-3 py-2 text-right">Physique</th>
            <th class="px-3 py-2 text-right">Écart</th>
            <th class="px-3 py-2">Résultat</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-border">
          <tr v-if="chargementInventaires">
            <td colspan="5" class="px-3 py-6 text-center text-text-muted">Chargement…</td>
          </tr>
          <tr v-else-if="!inventaires || inventaires.length === 0">
            <td colspan="5" class="px-3 py-6 text-center text-text-muted">Aucun inventaire physique pour le moment.</td>
          </tr>
          <tr v-for="inv in inventaires" v-else :key="inv.id">
            <td class="px-3 py-2 text-text">{{ inv.date_inventaire }}</td>
            <td class="px-3 py-2 text-right text-text">{{ inv.quantite_theorique }}</td>
            <td class="px-3 py-2 text-right text-text">{{ inv.quantite_physique }}</td>
            <td class="px-3 py-2 text-right text-text">{{ inv.ecart }}</td>
            <td class="px-3 py-2 text-text">{{ libelleEcart(inv) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>