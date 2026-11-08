<script setup lang="ts">
/**
 * Plan comptable de l'entreprise : référentiel global (entreprise_id nul,
 * non désactivable ici) + extensions propres à l'entreprise (créées et
 * désactivables depuis cette page). Pas de route de modification côté
 * backend (router.py n'a que creer_extension_compte/desactiver_extension_
 * compte) — même limitation assumée que pour les comptes bancaires.
 *
 * Deux façons d'alimenter le plan comptable : compte par compte (formulaire
 * "Nouveau compte", avec un compte parent optionnel pour créer un
 * sous-compte), ou en masse par import d'un fichier CSV/Excel à deux
 * colonnes (numéro, libellé) — le parent de chaque ligne importée est
 * déduit automatiquement du numéro (voir la note de
 * `ServiceComptabilite.importer_comptes` côté backend), jamais saisi.
 *
 * Le plan comptable d'un cabinet peut compter plusieurs centaines de
 * comptes une fois le référentiel importé : le tableau est donc paginé
 * (page suivante/précédente, comme `JournalActivitePage.vue` — pas de
 * numérotation de pages, le backend ne renvoie pas de total) et filtrable
 * par recherche texte sur le numéro OU le libellé, et par classe SYSCOHADA
 * (1 à 8). Ce filtrage porte sur `tousLesComptes` séparément de
 * l'affichage : un compte créé comme parent peut très bien ne pas
 * apparaître sur la page actuellement affichée, mais doit quand même
 * pouvoir être choisi dans le formulaire et être résolu par son numéro
 * dans la colonne "Compte parent".
 */
import { computed, reactive, ref, watch } from "vue";

import { useAuth } from "@/core/auth/useAuth";
import { messageErreur } from "@/core/api/erreurs";
import BaseDataTable, { type ColonneTable } from "@/core/ui/BaseDataTable.vue";
import ConfirmDialog from "@/core/ui/ConfirmDialog.vue";
import StatutBadge from "@/core/ui/StatutBadge.vue";
import { useComptesEntreprise, useMutationsComptes, type FiltresComptes } from "./api";
import type { Compte, CompteImportResultat } from "./types";

const { contexteActif, aPermission } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

// Liste complète (jusqu'à 1000 comptes, sans recherche ni pagination) :
// sert uniquement à résoudre un compte parent par son id (colonne "Compte
// parent", <select> du formulaire), jamais affichée telle quelle.
const { data: tousLesComptes } = useComptesEntreprise(entrepriseId);
const comptesParId = computed(() => {
  const table = new Map<string, Compte>();
  for (const c of tousLesComptes.value ?? []) table.set(c.id, c);
  return table;
});

// Liste affichée dans le tableau : paginée + recherche texte (numéro ou
// libellé) + classe, requête distincte de `tousLesComptes` ci-dessus.
const TAILLE_PAGE = 50;
const filtres = reactive<FiltresComptes>({ recherche: "", classe: null, limite: TAILLE_PAGE, decalage: 0 });
const rechercheSaisie = ref("");
const { data: comptes, isLoading } = useComptesEntreprise(entrepriseId, computed(() => filtres));
const { creer, desactiver, importer } = useMutationsComptes(entrepriseId);

// Recherche interactive (au fil de la saisie), avec un petit délai pour ne
// pas déclencher une requête à chaque frappe — seulement une fois que la
// personne a marqué une pause de 300 ms. `watch` plutôt qu'un gestionnaire
// @input : se redéclenche aussi si `rechercheSaisie` est vidé autrement
// (ex. un bouton "Effacer" ajouté plus tard).
let delaiRecherche: ReturnType<typeof setTimeout> | undefined;
watch(rechercheSaisie, (valeur) => {
  clearTimeout(delaiRecherche);
  delaiRecherche = setTimeout(() => {
    filtres.recherche = valeur.trim();
    filtres.decalage = 0;
  }, 300);
});

// Le filtre par classe s'applique immédiatement (un <select>, pas de
// saisie à tempériser).
function filtrerParClasse(e: Event): void {
  const valeur = (e.target as HTMLSelectElement).value;
  filtres.classe = valeur ? Number(valeur) : null;
  filtres.decalage = 0;
}

function pagePrecedente(): void {
  filtres.decalage = Math.max(0, (filtres.decalage ?? 0) - TAILLE_PAGE);
}

function pageSuivante(): void {
  if ((comptes.value ?? []).length < TAILLE_PAGE) return;
  filtres.decalage = (filtres.decalage ?? 0) + TAILLE_PAGE;
}

const colonnes: ColonneTable<Compte>[] = [
  { cle: "numero", libelle: "Numéro" },
  { cle: "libelle", libelle: "Libellé" },
  { cle: "classe", libelle: "Classe" },
  { cle: "compte_parent_id", libelle: "Compte parent" },
  { cle: "lettrable", libelle: "Lettrable" },
  { cle: "est_collectif", libelle: "Collectif" },
  { cle: "entreprise_id", libelle: "Origine" },
  { cle: "actif", libelle: "Statut" },
];

const formulaireOuvert = ref(false);
const formulaire = reactive({
  numero: "",
  libelle: "",
  classe: 4,
  lettrable: false,
  est_collectif: false,
  compte_parent_id: "" as string,
});
const erreur = ref<string | null>(null);

// Candidats au rôle de parent : seulement les comptes actifs de la même
// classe (voir la vérification équivalente côté service) — réduit la
// liste déroulante aux choix qui ont une chance d'être acceptés.
const parentsEligibles = computed(() =>
  (tousLesComptes.value ?? []).filter((c) => c.actif && c.classe === formulaire.classe),
);

async function soumettre(): Promise<void> {
  erreur.value = null;
  try {
    await creer.mutateAsync({ ...formulaire, compte_parent_id: formulaire.compte_parent_id || null });
    formulaireOuvert.value = false;
    formulaire.numero = "";
    formulaire.libelle = "";
    formulaire.classe = 4;
    formulaire.lettrable = false;
    formulaire.est_collectif = false;
    formulaire.compte_parent_id = "";
  } catch (e) {
    erreur.value = messageErreur(e);
  }
}

// --- Import du plan comptable (CSV/Excel) -------------------------------

const importOuvert = ref(false);
const fichierImport = ref<File | null>(null);
const erreurImport = ref<string | null>(null);
const resultatImport = ref<CompteImportResultat | null>(null);

function choisirFichier(e: Event): void {
  fichierImport.value = (e.target as HTMLInputElement).files?.[0] ?? null;
}

async function soumettreImport(): Promise<void> {
  if (!fichierImport.value) return;
  erreurImport.value = null;
  resultatImport.value = null;
  try {
    resultatImport.value = await importer.mutateAsync(fichierImport.value);
    fichierImport.value = null;
  } catch (e) {
    erreurImport.value = messageErreur(e);
  }
}

// `compteADesactiver` garde la ligne ciblée, `confirmationOuverte` ne
// pilote que l'affichage du dialogue : ConfirmDialog ferme le dialogue
// (émet update:ouvert=false) AVANT d'émettre "confirmer" — avec un seul
// ref portant les deux rôles, la cible serait effacée avant que le
// gestionnaire de confirmation ne la lise.
const compteADesactiver = ref<Compte | null>(null);
const confirmationOuverte = ref(false);
function demanderDesactivation(compte: Compte): void {
  compteADesactiver.value = compte;
  confirmationOuverte.value = true;
}

async function confirmerDesactivation(): Promise<void> {
  if (!compteADesactiver.value) return;
  await desactiver.mutateAsync(compteADesactiver.value.id);
  compteADesactiver.value = null;
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-lg font-semibold text-text">Plan comptable</h1>
      <div class="flex gap-2">
        <button
          v-if="aPermission('compte.creer')"
          type="button"
          class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted"
          @click="importOuvert = !importOuvert; formulaireOuvert = false"
        >
          Importer le plan comptable
        </button>
        <button
          v-if="aPermission('compte.creer')"
          type="button"
          class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover"
          @click="formulaireOuvert = !formulaireOuvert; importOuvert = false"
        >
          Nouveau compte
        </button>
      </div>
    </div>

    <form
      v-if="importOuvert"
      class="space-y-4 rounded-lg border border-border bg-surface p-6"
      @submit.prevent="soumettreImport"
    >
      <div>
        <label class="mb-1 block text-sm font-medium text-text">Fichier (CSV ou Excel)</label>
        <input
          type="file"
          accept=".csv,.xlsx,.xlsm,text/csv"
          required
          class="w-full rounded-md border border-border px-3 py-2 text-sm text-text"
          @change="choisirFichier"
        />
        <p class="mt-1 text-xs text-text-muted">
          Deux colonnes par ligne : numéro de compte, puis libellé. La classe est déduite du
          premier chiffre du numéro, et le compte parent (sous-compte) est déduit automatiquement
          du numéro lui-même — pas besoin de colonne supplémentaire.
        </p>
      </div>
      <p v-if="erreurImport" class="text-sm text-danger">{{ erreurImport }}</p>
      <div class="flex justify-end gap-2">
        <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted" @click="importOuvert = false">
          Fermer
        </button>
        <button
          type="submit"
          :disabled="importer.isPending.value || !fichierImport"
          class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60"
        >
          {{ importer.isPending.value ? "Import en cours…" : "Importer" }}
        </button>
      </div>

      <div v-if="resultatImport" class="space-y-2 rounded-md border border-border bg-surface-muted p-3 text-sm">
        <p class="font-medium text-text">
          {{ resultatImport.comptes_crees.length }} compte(s) créé(s), {{ resultatImport.ignores.length }} ignoré(s).
        </p>
        <ul v-if="resultatImport.ignores.length > 0" class="max-h-40 space-y-1 overflow-y-auto text-xs text-text-muted">
          <li v-for="(i, index) in resultatImport.ignores" :key="index">
            {{ i.numero || "(vide)" }} — {{ i.raison }}
          </li>
        </ul>
      </div>
    </form>

    <form
      v-if="formulaireOuvert"
      class="space-y-4 rounded-lg border border-border bg-surface p-6"
      @submit.prevent="soumettre"
    >
      <div class="grid grid-cols-4 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Numéro</label>
          <input v-model="formulaire.numero" required maxlength="20" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div class="col-span-2">
          <label class="mb-1 block text-sm font-medium text-text">Libellé</label>
          <input v-model="formulaire.libelle" required minlength="2" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Classe</label>
          <input v-model.number="formulaire.classe" type="number" min="1" max="8" required class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
      </div>
      <div>
        <label class="mb-1 block text-sm font-medium text-text">Compte parent (sous-compte, optionnel)</label>
        <select v-model="formulaire.compte_parent_id" class="w-full rounded-md border border-border px-3 py-2 text-text">
          <option value="">— Aucun —</option>
          <option v-for="c in parentsEligibles" :key="c.id" :value="c.id">{{ c.numero }} — {{ c.libelle }}</option>
        </select>
        <p class="mt-1 text-xs text-text-muted">
          Seuls les comptes actifs de la même classe sont proposés ; le numéro du sous-compte doit
          commencer par celui du parent choisi.
        </p>
      </div>
      <div class="flex gap-6 text-sm text-text">
        <label class="flex items-center gap-2">
          <input v-model="formulaire.lettrable" type="checkbox" />
          Lettrable
        </label>
        <label class="flex items-center gap-2">
          <input v-model="formulaire.est_collectif" type="checkbox" :disabled="!formulaire.lettrable" />
          Compte collectif (tiers)
        </label>
      </div>
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

    <div class="flex items-center gap-2">
      <input
        v-model="rechercheSaisie"
        type="search"
        placeholder="Rechercher par numéro ou libellé…"
        class="w-full max-w-sm rounded-md border border-border px-3 py-2 text-sm text-text"
      />
      <select
        :value="filtres.classe ?? ''"
        class="rounded-md border border-border px-3 py-2 text-sm text-text"
        @change="filtrerParClasse"
      >
        <option value="">Toutes les classes</option>
        <option v-for="n in 8" :key="n" :value="n">Classe {{ n }}</option>
      </select>
    </div>

    <BaseDataTable :colonnes="colonnes" :lignes="comptes ?? []" :chargement="isLoading" message-vide="Aucun compte.">
      <template #cell-lettrable="{ valeur }">{{ valeur ? "Oui" : "Non" }}</template>
      <template #cell-est_collectif="{ valeur }">{{ valeur ? "Oui" : "Non" }}</template>
      <template #cell-compte_parent_id="{ valeur }">
        {{ valeur ? comptesParId.get(valeur as string)?.numero ?? "—" : "—" }}
      </template>
      <template #cell-entreprise_id="{ valeur }">
        <StatutBadge :libelle="valeur ? 'Extension' : 'Référentiel global'" tonalite="info" />
      </template>
      <template #cell-actif="{ ligne }">
        <div class="flex items-center gap-2">
          <StatutBadge :libelle="ligne.actif ? 'Actif' : 'Désactivé'" :tonalite="ligne.actif ? 'succes' : 'neutre'" />
          <button
            v-if="ligne.actif && ligne.entreprise_id && aPermission('compte.archiver')"
            type="button"
            class="text-xs text-danger hover:underline"
            @click="demanderDesactivation(ligne)"
          >
            Désactiver
          </button>
        </div>
      </template>
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
        :disabled="(comptes ?? []).length < TAILLE_PAGE"
        @click="pageSuivante"
      >
        Suivant →
      </button>
    </div>

    <ConfirmDialog
      v-model:ouvert="confirmationOuverte"
      titre="Désactiver ce compte ?"
      :message="`Le compte ${compteADesactiver?.numero} n'apparaîtra plus dans les listes actives.`"
      libelle-confirmer="Désactiver"
      dangereux
      @confirmer="confirmerDesactivation"
    />
  </div>
</template>
