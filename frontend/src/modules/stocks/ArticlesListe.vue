<script setup lang="ts">
/**
 * Liste des articles en stock de l'entreprise : création + navigation
 * vers la fiche détail (mouvements, génération d'écriture). Désactivation/
 * réactivation faites depuis cette page, comme le plan comptable.
 */
import { computed, reactive, ref } from "vue";
import { useRouter } from "vue-router";

import { useAuth } from "@/core/auth/useAuth";
import { messageErreur } from "@/core/api/erreurs";
import BaseDataTable, { type ColonneTable } from "@/core/ui/BaseDataTable.vue";
import ConfirmDialog from "@/core/ui/ConfirmDialog.vue";
import { formaterMontant } from "@/core/ui/formatage";
import StatutBadge from "@/core/ui/StatutBadge.vue";
import { useComptesEntreprise } from "@/modules/comptabilite/api";
import { useListeArticles, useMutationsArticles } from "./api";
import type { Article, MethodeValorisation } from "./types";

const router = useRouter();
const { contexteActif, aPermission } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const actifsSeulement = ref(false);
const { data: articles, isLoading } = useListeArticles(entrepriseId, actifsSeulement);
const { creer, desactiver, reactiver } = useMutationsArticles(entrepriseId);

const { data: comptes } = useComptesEntreprise(entrepriseId);
const comptesStock = computed(() => (comptes.value ?? []).filter((c) => c.classe === 3));

const colonnes: ColonneTable<Article>[] = [
  { cle: "code", libelle: "Code" },
  { cle: "libelle", libelle: "Libellé" },
  { cle: "unite", libelle: "Unité" },
  { cle: "methode_valorisation", libelle: "Méthode" },
  { cle: "quantite_en_stock", libelle: "Quantité en stock" },
  { cle: "valeur_stock", libelle: "Valeur du stock" },
  { cle: "actif", libelle: "Statut" },
];

const formulaireOuvert = ref(false);
const formulaire = reactive({
  code: "",
  libelle: "",
  unite: "",
  methode_valorisation: "cmup" as MethodeValorisation,
  compte_stock_id: "",
});
const erreur = ref<string | null>(null);

async function soumettre(): Promise<void> {
  erreur.value = null;
  try {
    await creer.mutateAsync({ ...formulaire });
    formulaireOuvert.value = false;
    formulaire.code = "";
    formulaire.libelle = "";
    formulaire.unite = "";
    formulaire.methode_valorisation = "cmup";
    formulaire.compte_stock_id = "";
  } catch (e) {
    erreur.value = messageErreur(e);
  }
}

function ouvrir(ligne: Article): void {
  router.push({ name: "stocks.article", params: { id: ligne.id } });
}

async function reactiverArticle(article: Article): Promise<void> {
  await reactiver.mutateAsync(article.id);
}

// Deux refs distincts (voir le commentaire équivalent dans ComptesListe.vue) :
// ConfirmDialog émet update:ouvert=false AVANT confirmer, donc un seul ref
// portant à la fois la cible et la visibilité perdrait la cible trop tôt.
const articleADesactiver = ref<Article | null>(null);
const confirmationOuverte = ref(false);
function demanderDesactivation(article: Article): void {
  articleADesactiver.value = article;
  confirmationOuverte.value = true;
}

async function confirmerDesactivation(): Promise<void> {
  if (!articleADesactiver.value) return;
  await desactiver.mutateAsync(articleADesactiver.value.id);
  articleADesactiver.value = null;
}

const libellesMethode: Record<string, string> = { cmup: "CMUP", fifo: "FIFO" };
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-lg font-semibold text-text">Articles en stock</h1>
      <button
        v-if="aPermission('article.creer')"
        type="button"
        class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover"
        @click="formulaireOuvert = !formulaireOuvert"
      >
        Nouvel article
      </button>
    </div>

    <label class="flex items-center gap-2 text-sm text-text-muted">
      <input v-model="actifsSeulement" type="checkbox" />
      Actifs seulement
    </label>

    <form
      v-if="formulaireOuvert"
      class="space-y-4 rounded-lg border border-border bg-surface p-6"
      @submit.prevent="soumettre"
    >
      <div class="grid grid-cols-3 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Code</label>
          <input v-model="formulaire.code" required maxlength="30" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div class="col-span-2">
          <label class="mb-1 block text-sm font-medium text-text">Libellé</label>
          <input v-model="formulaire.libelle" required minlength="1" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
      </div>
      <div class="grid grid-cols-3 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Unité</label>
          <input v-model="formulaire.unite" required placeholder="ex: kg, unité, carton" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Méthode de valorisation</label>
          <select v-model="formulaire.methode_valorisation" class="w-full rounded-md border border-border px-3 py-2 text-text">
            <option value="cmup">CMUP (coût moyen pondéré)</option>
            <option value="fifo">FIFO (premier entré, premier sorti)</option>
          </select>
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Compte de stock (classe 3)</label>
          <select v-model="formulaire.compte_stock_id" required class="w-full rounded-md border border-border px-3 py-2 text-text">
            <option value="" disabled>Choisir un compte</option>
            <option v-for="c in comptesStock" :key="c.id" :value="c.id">{{ c.numero }} — {{ c.libelle }}</option>
          </select>
        </div>
      </div>
      <p class="text-xs text-text-muted">
        La méthode de valorisation et le compte de stock ne pourront plus être modifiés après la création.
      </p>
      <p v-if="erreur" class="text-sm text-danger">{{ erreur }}</p>
      <div class="flex justify-end gap-2">
        <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted" @click="formulaireOuvert = false">
          Annuler
        </button>
        <button type="submit" :disabled="creer.isPending.value" class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60">
          Créer
        </button>
      </div>
    </form>

    <BaseDataTable
      :colonnes="colonnes"
      :lignes="articles ?? []"
      :chargement="isLoading"
      message-vide="Aucun article pour le moment."
      @ligne-cliquee="ouvrir"
    >
      <template #cell-methode_valorisation="{ valeur }">{{ libellesMethode[valeur as string] }}</template>
      <template #cell-valeur_stock="{ valeur }">{{ formaterMontant(valeur as string) }}</template>
      <template #cell-actif="{ ligne }">
        <div class="flex items-center gap-2">
          <StatutBadge :libelle="ligne.actif ? 'Actif' : 'Désactivé'" :tonalite="ligne.actif ? 'succes' : 'neutre'" />
          <button
            v-if="ligne.actif && aPermission('article.archiver')"
            type="button"
            class="text-xs text-danger hover:underline"
            @click.stop="demanderDesactivation(ligne)"
          >
            Désactiver
          </button>
          <button
            v-else-if="!ligne.actif && aPermission('article.archiver')"
            type="button"
            class="text-xs text-primary hover:underline"
            @click.stop="reactiverArticle(ligne)"
          >
            Réactiver
          </button>
        </div>
      </template>
    </BaseDataTable>

    <ConfirmDialog
      v-model:ouvert="confirmationOuverte"
      titre="Désactiver cet article ?"
      :message="`L'article ${articleADesactiver?.code} n'apparaîtra plus dans les listes actives.`"
      libelle-confirmer="Désactiver"
      dangereux
      @confirmer="confirmerDesactivation"
    />
  </div>
</template>
