<script setup lang="ts">
/**
 * Plan comptable de l'entreprise : référentiel global (entreprise_id nul,
 * non modifiable ici) + comptes propres à l'entreprise (créés, désactivés
 * ou supprimés depuis cette page).
 *
 * - Neuf classes SYSCOHADA (1 à 9) : la classe 9 (engagements hors bilan /
 *   analytique) est consultable et saisissable, mais n'entre pas dans les
 *   totaux de la balance ni du tableau de bord.
 * - Vue par classe (pastilles) + recherche texte sur numéro OU libellé.
 * - Comptes divisionnaires : bouton « + Sous-compte » sur chaque ligne
 *   (formulaire prérempli : parent, classe, début de numéro) ; la
 *   hiérarchie s'affiche en retrait sous le compte parent.
 * - Suppression : seulement pour un compte propre à l'entreprise et jamais
 *   utilisé ; le backend refuse sinon en donnant la raison (écritures,
 *   sous-comptes, tiers...) — la désactivation reste alors possible.
 * - Classe 2 : les comptes d'immobilisations (21 à 27) portent un repère
 *   « Immobilisable » ; la création automatique de la fiche immobilisation
 *   à la saisie d'une écriture viendra avec le module Immobilisations.
 * - Import en masse CSV/Excel (numéro, libellé) : classe et parent déduits
 *   du numéro (voir `ServiceComptabilite.importer_comptes`).
 *
 * Le tableau est paginé (le backend ne renvoie pas de total) ; la liste
 * complète `tousLesComptes` sert à résoudre les parents et à calculer le
 * retrait hiérarchique, indépendamment de la page affichée.
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

const CLASSES: { numero: number; libelle: string }[] = [
  { numero: 1, libelle: "Ressources durables" },
  { numero: 2, libelle: "Actif immobilisé" },
  { numero: 3, libelle: "Stocks" },
  { numero: 4, libelle: "Tiers" },
  { numero: 5, libelle: "Trésorerie" },
  { numero: 6, libelle: "Charges" },
  { numero: 7, libelle: "Produits" },
  { numero: 8, libelle: "Autres charges et produits" },
  { numero: 9, libelle: "Hors bilan / analytique" },
];

// Liste complète : résolution des parents + retrait hiérarchique.
const { data: tousLesComptes } = useComptesEntreprise(
  entrepriseId,
  computed(() => ({ limite: 5000 })),
);
const comptesParId = computed(() => {
  const table = new Map<string, Compte>();
  for (const c of tousLesComptes.value ?? []) table.set(c.id, c);
  return table;
});

function profondeur(compte: Compte): number {
  let niveau = 0;
  let courant: Compte | undefined = compte;
  while (courant?.compte_parent_id && niveau < 10) {
    courant = comptesParId.value.get(courant.compte_parent_id);
    if (courant) niveau += 1;
  }
  return niveau;
}

function estImmobilisable(compte: Compte): boolean {
  return compte.classe === 2 && /^2[1-7]/.test(compte.numero);
}

// Liste affichée : paginée + recherche + classe.
const TAILLE_PAGE = 100;
const filtres = reactive<FiltresComptes>({ recherche: "", classe: null, limite: TAILLE_PAGE, decalage: 0 });
const rechercheSaisie = ref("");
const { data: comptes, isLoading } = useComptesEntreprise(entrepriseId, computed(() => filtres));
const { creer, desactiver, supprimer, importer } = useMutationsComptes(entrepriseId);

let delaiRecherche: ReturnType<typeof setTimeout> | undefined;
watch(rechercheSaisie, (valeur) => {
  clearTimeout(delaiRecherche);
  delaiRecherche = setTimeout(() => {
    filtres.recherche = valeur.trim();
    filtres.decalage = 0;
  }, 300);
});

function choisirClasse(numero: number | null): void {
  filtres.classe = numero;
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
  { cle: "lettrable", libelle: "Lettrable" },
  { cle: "est_collectif", libelle: "Collectif" },
  { cle: "entreprise_id", libelle: "Origine" },
  { cle: "actif", libelle: "Statut / actions" },
];

// --- Création (compte ou sous-compte) -------------------------------------

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

const parentsEligibles = computed(() =>
  (tousLesComptes.value ?? []).filter((c) => c.actif && c.classe === formulaire.classe),
);

function radical(numero: string): string {
  return numero.replace(/0+$/, "") || numero;
}

// Choisir un parent aligne la classe et propose le début du numéro.
watch(
  () => formulaire.compte_parent_id,
  (id) => {
    const parent = id ? comptesParId.value.get(id) : undefined;
    if (!parent) return;
    formulaire.classe = parent.classe;
    if (!formulaire.numero.startsWith(radical(parent.numero))) {
      formulaire.numero = radical(parent.numero);
    }
  },
);

function reinitialiserFormulaire(): void {
  formulaire.numero = "";
  formulaire.libelle = "";
  formulaire.classe = filtres.classe ?? 4;
  formulaire.lettrable = false;
  formulaire.est_collectif = false;
  formulaire.compte_parent_id = "";
}

function ouvrirNouveau(): void {
  reinitialiserFormulaire();
  erreur.value = null;
  formulaireOuvert.value = true;
  importOuvert.value = false;
}

function ouvrirSousCompte(parent: Compte): void {
  reinitialiserFormulaire();
  erreur.value = null;
  formulaire.classe = parent.classe;
  formulaire.compte_parent_id = parent.id;
  formulaire.numero = radical(parent.numero);
  formulaire.lettrable = parent.lettrable;
  formulaireOuvert.value = true;
  importOuvert.value = false;
}

async function soumettre(): Promise<void> {
  erreur.value = null;
  try {
    await creer.mutateAsync({ ...formulaire, compte_parent_id: formulaire.compte_parent_id || null });
    formulaireOuvert.value = false;
    reinitialiserFormulaire();
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

// --- Désactivation / suppression ---------------------------------------
// `compteCible` garde la ligne ciblée, les booléens ne pilotent que
// l'affichage : ConfirmDialog ferme le dialogue AVANT d'émettre "confirmer".

const compteADesactiver = ref<Compte | null>(null);
const desactivationOuverte = ref(false);
const compteASupprimer = ref<Compte | null>(null);
const suppressionOuverte = ref(false);
const erreurAction = ref<string | null>(null);

function demanderDesactivation(compte: Compte): void {
  compteADesactiver.value = compte;
  desactivationOuverte.value = true;
}

async function confirmerDesactivation(): Promise<void> {
  if (!compteADesactiver.value) return;
  erreurAction.value = null;
  try {
    await desactiver.mutateAsync(compteADesactiver.value.id);
  } catch (e) {
    erreurAction.value = messageErreur(e);
  }
  compteADesactiver.value = null;
}

function demanderSuppression(compte: Compte): void {
  compteASupprimer.value = compte;
  suppressionOuverte.value = true;
}

async function confirmerSuppression(): Promise<void> {
  if (!compteASupprimer.value) return;
  erreurAction.value = null;
  try {
    await supprimer.mutateAsync(compteASupprimer.value.id);
  } catch (e) {
    // Ex. « Le compte 601100 est utilisé dans 12 ligne(s) d'écriture… »
    erreurAction.value = messageErreur(e);
  }
  compteASupprimer.value = null;
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
          @click="formulaireOuvert ? (formulaireOuvert = false) : ouvrirNouveau()"
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
          Deux colonnes par ligne : numéro de compte, puis libellé. La classe (1 à 9) est déduite du
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
      <h2 class="text-sm font-semibold text-text">
        {{ formulaire.compte_parent_id ? "Nouveau sous-compte (compte divisionnaire)" : "Nouveau compte" }}
      </h2>
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
          <select v-model.number="formulaire.classe" required class="w-full rounded-md border border-border px-3 py-2 text-text">
            <option v-for="c in CLASSES" :key="c.numero" :value="c.numero">{{ c.numero }} — {{ c.libelle }}</option>
          </select>
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
          commencer par celui du parent choisi (ex. 411 → 4111001).
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

    <!-- Vue par classe -->
    <div class="flex flex-wrap gap-2">
      <button
        type="button"
        class="rounded-full border px-3 py-1 text-xs font-medium"
        :class="filtres.classe === null ? 'border-primary bg-primary text-primary-foreground' : 'border-border text-text hover:bg-surface-muted'"
        @click="choisirClasse(null)"
      >
        Toutes
      </button>
      <button
        v-for="c in CLASSES"
        :key="c.numero"
        type="button"
        class="rounded-full border px-3 py-1 text-xs font-medium"
        :class="filtres.classe === c.numero ? 'border-primary bg-primary text-primary-foreground' : 'border-border text-text hover:bg-surface-muted'"
        :title="c.libelle"
        @click="choisirClasse(c.numero)"
      >
        {{ c.numero }} · {{ c.libelle }}
      </button>
    </div>

    <input
      v-model="rechercheSaisie"
      type="search"
      placeholder="Rechercher par numéro ou libellé…"
      class="w-full max-w-sm rounded-md border border-border px-3 py-2 text-sm text-text"
    />

    <p v-if="filtres.classe === 9" class="rounded-md border border-border bg-surface-muted px-3 py-2 text-xs text-text-muted">
      La classe 9 (engagements hors bilan, comptabilité analytique) n'entre pas dans les totaux de la
      balance ni du tableau de bord.
    </p>
    <p v-if="erreurAction" class="rounded-md border border-danger px-3 py-2 text-sm text-danger">
      {{ erreurAction }}
    </p>

    <BaseDataTable :colonnes="colonnes" :lignes="comptes ?? []" :chargement="isLoading" message-vide="Aucun compte.">
      <template #cell-numero="{ ligne }">
        <span class="font-mono" :style="{ paddingLeft: `${profondeur(ligne) * 16}px` }">
          <span v-if="profondeur(ligne) > 0" class="text-text-muted">└ </span>{{ ligne.numero }}
        </span>
      </template>
      <template #cell-libelle="{ ligne }">
        <span>{{ ligne.libelle }}</span>
        <StatutBadge v-if="estImmobilisable(ligne)" class="ml-2" libelle="Immobilisable" tonalite="info" />
      </template>
      <template #cell-lettrable="{ valeur }">{{ valeur ? "Oui" : "Non" }}</template>
      <template #cell-est_collectif="{ valeur }">{{ valeur ? "Oui" : "Non" }}</template>
      <template #cell-entreprise_id="{ valeur }">
        <StatutBadge :libelle="valeur ? 'Propre à l\'entreprise' : 'Référentiel global'" tonalite="info" />
      </template>
      <template #cell-actif="{ ligne }">
        <div class="flex flex-wrap items-center gap-2">
          <StatutBadge :libelle="ligne.actif ? 'Actif' : 'Désactivé'" :tonalite="ligne.actif ? 'succes' : 'neutre'" />
          <button
            v-if="ligne.actif && aPermission('compte.creer')"
            type="button"
            class="text-xs text-primary hover:underline"
            @click="ouvrirSousCompte(ligne)"
          >
            + Sous-compte
          </button>
          <button
            v-if="ligne.actif && ligne.entreprise_id && aPermission('compte.archiver')"
            type="button"
            class="text-xs text-danger hover:underline"
            @click="demanderDesactivation(ligne)"
          >
            Désactiver
          </button>
          <button
            v-if="ligne.entreprise_id && aPermission('compte.archiver')"
            type="button"
            class="text-xs text-danger hover:underline"
            @click="demanderSuppression(ligne)"
          >
            Supprimer
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
      v-model:ouvert="desactivationOuverte"
      titre="Désactiver ce compte ?"
      :message="`Le compte ${compteADesactiver?.numero} n'apparaîtra plus dans les listes actives ; son historique est conservé.`"
      libelle-confirmer="Désactiver"
      dangereux
      @confirmer="confirmerDesactivation"
    />
    <ConfirmDialog
      v-model:ouvert="suppressionOuverte"
      titre="Supprimer ce compte ?"
      :message="`Le compte ${compteASupprimer?.numero} sera supprimé définitivement. Impossible s'il est déjà utilisé (écritures, sous-comptes, tiers) : désactivez-le alors.`"
      libelle-confirmer="Supprimer"
      dangereux
      @confirmer="confirmerSuppression"
    />
  </div>
</template>