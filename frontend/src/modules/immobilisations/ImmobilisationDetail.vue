<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { useRoute } from "vue-router";

import { useAuth } from "@/core/auth/useAuth";
import { useComptesEntreprise, useJournaux } from "@/modules/comptabilite/api";
import { useExercices } from "@/modules/exercices/api";
import { useListeTiers } from "@/modules/tiers/api";
import { messageErreur } from "@/core/api/erreurs";
import { formaterMontant } from "@/core/ui/formatage";
import MontantInput from "@/core/ui/MontantInput.vue";
import StatutBadge from "@/core/ui/StatutBadge.vue";
import {
  useImmobilisation,
  useLignesAmortissement,
  useMutationsImmobilisations,
} from "./api";

const route = useRoute();
const { contexteActif, aPermission } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);
const immobilisationId = computed(() => route.params.id as string);

const { data: immobilisation } = useImmobilisation(entrepriseId, immobilisationId);
const { data: lignes } = useLignesAmortissement(entrepriseId, immobilisationId);
const { data: comptes } = useComptesEntreprise(entrepriseId);
const { data: exercices } = useExercices(entrepriseId);
const { data: journaux } = useJournaux(entrepriseId);
const { data: fournisseurs } = useListeTiers(
  entrepriseId,
  computed(() => ({ actifsSeulement: true, fournisseurSeulement: true })),
);

const {
  modifier,
  genererLigneAmortissement,
  genererEcritureAmortissement,
  ceder,
  reformer,
} = useMutationsImmobilisations(entrepriseId);

function libelleCompte(id: string | null): string {
  if (!id) return "—";
  const c = comptes.value?.find((c) => c.id === id);
  return c ? `${c.numero} — ${c.libelle}` : id;
}

// --- Édition des champs descriptifs ---

const formulaireEdition = reactive({ libelle: "", categorie: "", numero_inventaire: "", fournisseur_id: "" });
const editionOuverte = ref(false);
watch(
  immobilisation,
  (i) => {
    if (!i) return;
    formulaireEdition.libelle = i.libelle;
    formulaireEdition.categorie = i.categorie ?? "";
    formulaireEdition.numero_inventaire = i.numero_inventaire ?? "";
    formulaireEdition.fournisseur_id = i.fournisseur_id ?? "";
  },
  { immediate: true },
);
const erreurEdition = ref<string | null>(null);
async function enregistrerEdition(): Promise<void> {
  erreurEdition.value = null;
  try {
    await modifier.mutateAsync({
      id: immobilisationId.value,
      donnees: {
        libelle: formulaireEdition.libelle,
        categorie: formulaireEdition.categorie || null,
        numero_inventaire: formulaireEdition.numero_inventaire || null,
        fournisseur_id: formulaireEdition.fournisseur_id || null,
      },
    });
    editionOuverte.value = false;
  } catch (e) {
    erreurEdition.value = messageErreur(e);
  }
}

// --- Plan d'amortissement ---

const exerciceChoisi = ref("");
const erreurGeneration = ref<string | null>(null);
async function genererLigne(): Promise<void> {
  erreurGeneration.value = null;
  try {
    await genererLigneAmortissement.mutateAsync({
      immobilisationId: immobilisationId.value,
      exerciceId: exerciceChoisi.value,
    });
    exerciceChoisi.value = "";
  } catch (e) {
    erreurGeneration.value = messageErreur(e);
  }
}

const ligneEnEcriture = ref<string | null>(null);
const journalEcriture = ref("");
const erreurEcriture = ref<string | null>(null);
async function genererEcriture(ligneId: string): Promise<void> {
  erreurEcriture.value = null;
  try {
    await genererEcritureAmortissement.mutateAsync({
      ligneId,
      donnees: { journal_id: journalEcriture.value },
    });
    ligneEnEcriture.value = null;
    journalEcriture.value = "";
  } catch (e) {
    erreurEcriture.value = messageErreur(e);
  }
}

// --- Cession ---

const cessionOuverte = ref(false);
const cession = reactive({
  date_sortie: "",
  prix_cession: 0 as number,
  journal_id: "",
  compte_tresorerie_id: "",
  compte_produit_cession_id: "",
  compte_valeur_comptable_sortie_id: "",
});
const erreurCession = ref<string | null>(null);
async function soumettreCession(): Promise<void> {
  erreurCession.value = null;
  try {
    await ceder.mutateAsync({ id: immobilisationId.value, donnees: { ...cession } });
    cessionOuverte.value = false;
  } catch (e) {
    erreurCession.value = messageErreur(e);
  }
}

// --- Réforme ---

const reformeOuverte = ref(false);
const reforme = reactive({ date_sortie: "", journal_id: "", compte_valeur_comptable_sortie_id: "" });
const erreurReforme = ref<string | null>(null);
async function soumettreReforme(): Promise<void> {
  erreurReforme.value = null;
  try {
    await reformer.mutateAsync({ id: immobilisationId.value, donnees: { ...reforme } });
    reformeOuverte.value = false;
  } catch (e) {
    erreurReforme.value = messageErreur(e);
  }
}

const libellesStatut: Record<string, string> = {
  en_service: "En service",
  cedee: "Cédée",
  reformee: "Réformée",
};
const tonalitesStatut: Record<string, "succes" | "info" | "neutre"> = {
  en_service: "succes",
  cedee: "info",
  reformee: "neutre",
};
</script>

<template>
  <div v-if="immobilisation" class="max-w-4xl space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-lg font-semibold text-text">{{ immobilisation.libelle }}</h1>
      <StatutBadge
        :libelle="libellesStatut[immobilisation.statut]"
        :tonalite="tonalitesStatut[immobilisation.statut]"
      />
    </div>

    <div class="space-y-4 rounded-lg border border-border bg-surface p-6">
      <div class="flex items-center justify-between">
        <h2 class="text-base font-semibold text-text">Informations</h2>
        <button
          v-if="aPermission('immobilisation.modifier') && !editionOuverte"
          type="button"
          class="text-sm text-primary hover:underline"
          @click="editionOuverte = true"
        >
          Modifier
        </button>
      </div>

      <form v-if="editionOuverte" class="space-y-4" @submit.prevent="enregistrerEdition">
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="mb-1 block text-sm font-medium text-text">Libellé</label>
            <input v-model="formulaireEdition.libelle" required minlength="2" class="w-full rounded-md border border-border px-3 py-2 text-text" />
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-text">Catégorie</label>
            <input v-model="formulaireEdition.categorie" class="w-full rounded-md border border-border px-3 py-2 text-text" />
          </div>
        </div>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="mb-1 block text-sm font-medium text-text">N° inventaire</label>
            <input v-model="formulaireEdition.numero_inventaire" class="w-full rounded-md border border-border px-3 py-2 text-text" />
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-text">Fournisseur</label>
            <select v-model="formulaireEdition.fournisseur_id" class="w-full rounded-md border border-border px-3 py-2 text-text">
              <option value="">— Aucun —</option>
              <option v-for="t in fournisseurs" :key="t.id" :value="t.id">{{ t.code }} — {{ t.raison_sociale }}</option>
            </select>
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

      <div v-else class="grid grid-cols-2 gap-4 text-sm">
        <div><p class="text-text-muted">Catégorie</p><p class="text-text">{{ immobilisation.categorie ?? "—" }}</p></div>
        <div><p class="text-text-muted">N° inventaire</p><p class="text-text">{{ immobilisation.numero_inventaire ?? "—" }}</p></div>
        <div><p class="text-text-muted">Date d'acquisition</p><p class="text-text">{{ immobilisation.date_acquisition }}</p></div>
        <div><p class="text-text-muted">Date de mise en service</p><p class="text-text">{{ immobilisation.date_mise_en_service }}</p></div>
        <div><p class="text-text-muted">Valeur d'origine</p><p class="text-text">{{ formaterMontant(immobilisation.valeur_origine) }}</p></div>
        <div><p class="text-text-muted">Valeur résiduelle</p><p class="text-text">{{ formaterMontant(immobilisation.valeur_residuelle) }}</p></div>
        <div><p class="text-text-muted">Durée</p><p class="text-text">{{ immobilisation.duree_amortissement_annees }} ans</p></div>
        <div>
          <p class="text-text-muted">Méthode</p>
          <p class="text-text">
            {{ immobilisation.methode_amortissement === "degressif" ? `Dégressif (${immobilisation.taux_degressif}%)` : "Linéaire" }}
          </p>
        </div>
        <div><p class="text-text-muted">Compte immobilisation</p><p class="text-text">{{ libelleCompte(immobilisation.compte_immobilisation_id) }}</p></div>
        <div><p class="text-text-muted">Compte amortissement</p><p class="text-text">{{ libelleCompte(immobilisation.compte_amortissement_id) }}</p></div>
        <div><p class="text-text-muted">Compte dotation</p><p class="text-text">{{ libelleCompte(immobilisation.compte_dotation_id) }}</p></div>
      </div>
    </div>

    <div v-if="immobilisation.statut !== 'en_service'" class="space-y-2 rounded-lg border border-border bg-surface p-6 text-sm">
      <h2 class="text-base font-semibold text-text">Sortie du patrimoine</h2>
      <div class="grid grid-cols-2 gap-4">
        <div><p class="text-text-muted">Date de sortie</p><p class="text-text">{{ immobilisation.date_sortie }}</p></div>
        <div v-if="immobilisation.statut === 'cedee'"><p class="text-text-muted">Prix de cession</p><p class="text-text">{{ formaterMontant(immobilisation.prix_cession) }}</p></div>
        <div><p class="text-text-muted">Valeur nette comptable de sortie</p><p class="text-text">{{ formaterMontant(immobilisation.valeur_nette_comptable_sortie) }}</p></div>
        <div v-if="immobilisation.statut === 'cedee'"><p class="text-text-muted">Plus ou moins-value</p><p class="text-text">{{ formaterMontant(immobilisation.plus_ou_moins_value) }}</p></div>
      </div>
    </div>

    <div class="space-y-3">
      <div class="flex items-center justify-between">
        <h2 class="text-base font-semibold text-text">Plan d'amortissement</h2>
        <div v-if="aPermission('immobilisation.valider')" class="flex items-center gap-2">
          <select v-model="exerciceChoisi" class="rounded-md border border-border px-2 py-1.5 text-sm text-text">
            <option value="" disabled>— Exercice —</option>
            <option v-for="e in exercices" :key="e.id" :value="e.id">{{ e.date_debut }} → {{ e.date_fin }}</option>
          </select>
          <button
            type="button"
            :disabled="!exerciceChoisi || genererLigneAmortissement.isPending.value"
            class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60"
            @click="genererLigne"
          >
            Générer la ligne
          </button>
        </div>
      </div>
      <p v-if="erreurGeneration" class="text-sm text-danger">{{ erreurGeneration }}</p>

      <div class="overflow-hidden rounded-lg border border-border bg-surface">
        <table class="w-full text-sm">
          <thead class="bg-surface-muted text-left text-xs font-medium uppercase text-text-muted">
            <tr>
              <th class="px-3 py-2">Exercice</th>
              <th class="px-3 py-2 text-right">Base</th>
              <th class="px-3 py-2 text-right">Taux</th>
              <th class="px-3 py-2 text-right">Dotation</th>
              <th class="px-3 py-2 text-right">Cumul</th>
              <th class="px-3 py-2 text-right">VNC</th>
              <th class="px-3 py-2">Statut</th>
              <th class="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            <tr v-if="!lignes || lignes.length === 0">
              <td colspan="8" class="px-3 py-6 text-center text-text-muted">Aucune ligne générée.</td>
            </tr>
            <tr v-for="l in lignes" v-else :key="l.id">
              <td class="px-3 py-2 text-text">{{ exercices?.find((e) => e.id === l.exercice_id)?.date_debut }}</td>
              <td class="px-3 py-2 text-right text-text">{{ formaterMontant(l.base_amortissable) }}</td>
              <td class="px-3 py-2 text-right text-text">{{ l.taux_applique }}%</td>
              <td class="px-3 py-2 text-right text-text">{{ formaterMontant(l.dotation) }}</td>
              <td class="px-3 py-2 text-right text-text">{{ formaterMontant(l.cumul_amortissements) }}</td>
              <td class="px-3 py-2 text-right text-text">{{ formaterMontant(l.valeur_nette_comptable) }}</td>
              <td class="px-3 py-2">
                <StatutBadge
                  :libelle="l.statut === 'comptabilise' ? 'Comptabilisée' : 'Prévue'"
                  :tonalite="l.statut === 'comptabilise' ? 'succes' : 'avertissement'"
                />
              </td>
              <td class="px-3 py-2">
                <button
                  v-if="l.statut === 'prevu' && aPermission('immobilisation.valider') && ligneEnEcriture !== l.id"
                  type="button"
                  class="text-xs text-primary hover:underline"
                  @click="ligneEnEcriture = l.id"
                >
                  Générer l'écriture
                </button>
                <div v-else-if="ligneEnEcriture === l.id" class="flex items-center gap-1">
                  <select v-model="journalEcriture" class="rounded-md border border-border px-1 py-1 text-xs text-text">
                    <option value="" disabled>— Journal —</option>
                    <option v-for="j in journaux" :key="j.id" :value="j.id">{{ j.code }}</option>
                  </select>
                  <button type="button" :disabled="!journalEcriture" class="text-xs text-primary hover:underline" @click="genererEcriture(l.id)">
                    OK
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-if="erreurEcriture" class="text-sm text-danger">{{ erreurEcriture }}</p>
    </div>

    <template v-if="immobilisation.statut === 'en_service' && aPermission('immobilisation.ceder')">
      <div class="flex gap-2">
        <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted" @click="cessionOuverte = !cessionOuverte">
          Céder
        </button>
        <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted" @click="reformeOuverte = !reformeOuverte">
          Réformer (mise au rebut)
        </button>
      </div>

      <form v-if="cessionOuverte" class="space-y-4 rounded-lg border border-border bg-surface p-6" @submit.prevent="soumettreCession">
        <h2 class="text-base font-semibold text-text">Céder l'immobilisation</h2>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="mb-1 block text-sm font-medium text-text">Date de sortie</label>
            <input v-model="cession.date_sortie" type="date" required class="w-full rounded-md border border-border px-3 py-2 text-text" />
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-text">Prix de cession</label>
            <MontantInput v-model="cession.prix_cession" required />
          </div>
        </div>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="mb-1 block text-sm font-medium text-text">Journal</label>
            <select v-model="cession.journal_id" required class="w-full rounded-md border border-border px-3 py-2 text-text">
              <option value="" disabled>— Choisir —</option>
              <option v-for="j in journaux" :key="j.id" :value="j.id">{{ j.code }} — {{ j.libelle }}</option>
            </select>
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-text">Compte de trésorerie</label>
            <select v-model="cession.compte_tresorerie_id" required class="w-full rounded-md border border-border px-3 py-2 text-text">
              <option value="" disabled>— Choisir —</option>
              <option v-for="c in comptes" :key="c.id" :value="c.id">{{ c.numero }} — {{ c.libelle }}</option>
            </select>
          </div>
        </div>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="mb-1 block text-sm font-medium text-text">Compte produit de cession</label>
            <select v-model="cession.compte_produit_cession_id" required class="w-full rounded-md border border-border px-3 py-2 text-text">
              <option value="" disabled>— Choisir —</option>
              <option v-for="c in comptes" :key="c.id" :value="c.id">{{ c.numero }} — {{ c.libelle }}</option>
            </select>
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-text">Compte VNC des sorties</label>
            <select v-model="cession.compte_valeur_comptable_sortie_id" required class="w-full rounded-md border border-border px-3 py-2 text-text">
              <option value="" disabled>— Choisir —</option>
              <option v-for="c in comptes" :key="c.id" :value="c.id">{{ c.numero }} — {{ c.libelle }}</option>
            </select>
          </div>
        </div>
        <p v-if="erreurCession" class="text-sm text-danger">{{ erreurCession }}</p>
        <div class="flex justify-end gap-2">
          <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted" @click="cessionOuverte = false">Annuler</button>
          <button type="submit" :disabled="ceder.isPending.value" class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60">Céder</button>
        </div>
      </form>

      <form v-if="reformeOuverte" class="space-y-4 rounded-lg border border-border bg-surface p-6" @submit.prevent="soumettreReforme">
        <h2 class="text-base font-semibold text-text">Réformer l'immobilisation</h2>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="mb-1 block text-sm font-medium text-text">Date de sortie</label>
            <input v-model="reforme.date_sortie" type="date" required class="w-full rounded-md border border-border px-3 py-2 text-text" />
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-text">Journal</label>
            <select v-model="reforme.journal_id" required class="w-full rounded-md border border-border px-3 py-2 text-text">
              <option value="" disabled>— Choisir —</option>
              <option v-for="j in journaux" :key="j.id" :value="j.id">{{ j.code }} — {{ j.libelle }}</option>
            </select>
          </div>
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Compte VNC des sorties</label>
          <select v-model="reforme.compte_valeur_comptable_sortie_id" required class="w-full rounded-md border border-border px-3 py-2 text-text">
            <option value="" disabled>— Choisir —</option>
            <option v-for="c in comptes" :key="c.id" :value="c.id">{{ c.numero }} — {{ c.libelle }}</option>
          </select>
        </div>
        <p v-if="erreurReforme" class="text-sm text-danger">{{ erreurReforme }}</p>
        <div class="flex justify-end gap-2">
          <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted" @click="reformeOuverte = false">Annuler</button>
          <button type="submit" :disabled="reformer.isPending.value" class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60">Réformer</button>
        </div>
      </form>
    </template>
  </div>
</template>
