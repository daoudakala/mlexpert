<script setup lang="ts">
/**
 * Acquisitions à confirmer : les lignes d'écriture validées qui débitent un
 * compte d'immobilisation (21 à 27) et n'ont pas encore de fiche dans le
 * module Immobilisations. Pour chacune, on confirme la fiche (la date
 * d'acquisition, la valeur d'origine et le compte viennent de l'écriture ;
 * durée, méthode, comptes 28/68 sont proposés puis confirmés) ou on
 * l'ignore (ex. petit matériel passé en charge). À la confirmation, le plan
 * d'amortissement est généré sur les exercices déjà ouverts ; les écritures
 * de dotation se comptabilisent ensuite depuis la fiche.
 */
import { computed, reactive, ref } from "vue";
import { useRouter } from "vue-router";

import { useAuth } from "@/core/auth/useAuth";
import { messageErreur } from "@/core/api/erreurs";
import { formaterMontant } from "@/core/ui/formatage";
import MontantInput from "@/core/ui/MontantInput.vue";
import { useComptesEntreprise } from "@/modules/comptabilite/api";
import { useListeTiers } from "@/modules/tiers/api";
import { useAcquisitionsAConfirmer, useMutationsAcquisitions } from "./api";
import type { AcquisitionAConfirmer, MethodeAmortissement } from "./types";

const router = useRouter();
const { contexteActif, aPermission } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const { data: acquisitions, isLoading } = useAcquisitionsAConfirmer(entrepriseId);
const { data: comptes } = useComptesEntreprise(entrepriseId, computed(() => ({ limite: 5000 })));
const comptesAmortissement = computed(() => (comptes.value ?? []).filter((c) => c.classe === 2));
const comptesDotation = computed(() => (comptes.value ?? []).filter((c) => c.classe === 6));
const { data: fournisseurs } = useListeTiers(
  entrepriseId,
  computed(() => ({ actifsSeulement: true, fournisseurSeulement: true })),
);
const { confirmer, ignorer } = useMutationsAcquisitions(entrepriseId);

const ligneEnCours = ref<AcquisitionAConfirmer | null>(null);
const formulaire = reactive({
  libelle: "",
  categorie: "",
  numero_inventaire: "",
  date_mise_en_service: "",
  valeur_residuelle: 0 as number,
  duree_amortissement_annees: 5 as number,
  methode_amortissement: "lineaire" as MethodeAmortissement,
  taux_degressif: null as number | null,
  compte_amortissement_id: "",
  compte_dotation_id: "",
  fournisseur_id: "",
  generer_plan: true,
});
const erreur = ref<string | null>(null);
const message = ref<{ texte: string; id: string; avertissement: string | null } | null>(null);

function ouvrir(a: AcquisitionAConfirmer): void {
  ligneEnCours.value = a;
  erreur.value = null;
  formulaire.libelle = a.libelle;
  formulaire.categorie = "";
  formulaire.numero_inventaire = "";
  formulaire.date_mise_en_service = a.date_acquisition;
  formulaire.valeur_residuelle = 0;
  formulaire.duree_amortissement_annees = 5;
  formulaire.methode_amortissement = "lineaire";
  formulaire.taux_degressif = null;
  formulaire.compte_amortissement_id = a.compte_amortissement_suggere_id ?? "";
  formulaire.compte_dotation_id = a.compte_dotation_suggere_id ?? "";
  formulaire.fournisseur_id = a.tiers_id ?? "";
  formulaire.generer_plan = true;
}

async function soumettre(): Promise<void> {
  if (!ligneEnCours.value) return;
  erreur.value = null;
  try {
    const resultat = await confirmer.mutateAsync({
      ligneId: ligneEnCours.value.ligne_ecriture_id,
      donnees: {
        libelle: formulaire.libelle,
        categorie: formulaire.categorie || null,
        numero_inventaire: formulaire.numero_inventaire || null,
        date_mise_en_service: formulaire.date_mise_en_service || null,
        valeur_residuelle: formulaire.valeur_residuelle,
        duree_amortissement_annees: formulaire.duree_amortissement_annees,
        methode_amortissement: formulaire.methode_amortissement,
        taux_degressif: formulaire.methode_amortissement === "degressif" ? formulaire.taux_degressif : null,
        compte_amortissement_id: formulaire.compte_amortissement_id,
        compte_dotation_id: formulaire.compte_dotation_id,
        fournisseur_id: formulaire.fournisseur_id || null,
        generer_plan: formulaire.generer_plan,
      },
    });
    message.value = {
      texte: `Immobilisation « ${resultat.immobilisation.libelle} » créée — ${resultat.lignes_generees} ligne(s) de plan d'amortissement générée(s).`,
      id: resultat.immobilisation.id,
      avertissement: resultat.avertissement,
    };
    ligneEnCours.value = null;
  } catch (e) {
    erreur.value = messageErreur(e);
  }
}

const erreurIgnorer = ref<string | null>(null);
async function ignorerLigne(a: AcquisitionAConfirmer): Promise<void> {
  erreurIgnorer.value = null;
  try {
    await ignorer.mutateAsync(a.ligne_ecriture_id);
    if (ligneEnCours.value?.ligne_ecriture_id === a.ligne_ecriture_id) ligneEnCours.value = null;
  } catch (e) {
    erreurIgnorer.value = messageErreur(e);
  }
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-lg font-semibold text-text">Acquisitions à confirmer</h1>
      <router-link :to="{ name: 'immobilisations.liste' }" class="text-sm text-primary hover:underline">
        ← Immobilisations
      </router-link>
    </div>
    <p class="text-sm text-text-muted">
      Écritures validées qui débitent un compte d'immobilisation (21 à 27). Confirme chaque acquisition pour
      créer sa fiche et son plan d'amortissement, ou ignore-la si ce n'est pas une immobilisation. Les
      à-nouveaux (journal de report) ne sont pas proposés.
    </p>

    <div v-if="message" class="space-y-1 rounded-lg border border-success bg-success/10 px-4 py-3 text-sm text-text">
      <p>
        {{ message.texte }}
        <router-link :to="{ name: 'immobilisations.detail', params: { id: message.id } }" class="text-primary hover:underline">
          Ouvrir la fiche
        </router-link>
      </p>
      <p v-if="message.avertissement" class="text-text-muted">{{ message.avertissement }}</p>
    </div>
    <p v-if="erreurIgnorer" class="text-sm text-danger">{{ erreurIgnorer }}</p>

    <div class="overflow-hidden rounded-lg border border-border bg-surface">
      <table class="w-full text-sm">
        <thead class="bg-surface-muted text-left text-xs font-medium uppercase text-text-muted">
          <tr>
            <th class="px-3 py-2">Date</th>
            <th class="px-3 py-2">Pièce</th>
            <th class="px-3 py-2">Compte</th>
            <th class="px-3 py-2">Libellé</th>
            <th class="px-3 py-2 text-right">Valeur d'origine</th>
            <th class="px-3 py-2"></th>
          </tr>
        </thead>
        <tbody class="divide-y divide-border">
          <tr v-if="isLoading">
            <td colspan="6" class="px-3 py-6 text-center text-text-muted">Chargement…</td>
          </tr>
          <tr v-else-if="!acquisitions || acquisitions.length === 0">
            <td colspan="6" class="px-3 py-6 text-center text-text-muted">Aucune acquisition à confirmer.</td>
          </tr>
          <tr v-for="a in acquisitions" v-else :key="a.ligne_ecriture_id">
            <td class="px-3 py-2 text-text">{{ a.date_acquisition }}</td>
            <td class="px-3 py-2 text-text">{{ a.numero_ecriture ?? "—" }}</td>
            <td class="px-3 py-2 text-text">{{ a.compte_numero }} — {{ a.compte_libelle }}</td>
            <td class="px-3 py-2 text-text">{{ a.libelle }}</td>
            <td class="px-3 py-2 text-right text-text">{{ formaterMontant(a.montant) }}</td>
            <td class="px-3 py-2 text-right">
              <div v-if="aPermission('immobilisation.creer')" class="flex justify-end gap-3">
                <button type="button" class="text-xs text-primary hover:underline" @click="ouvrir(a)">Confirmer</button>
                <button type="button" class="text-xs text-text-muted hover:underline" @click="ignorerLigne(a)">Ignorer</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <form
      v-if="ligneEnCours"
      class="space-y-4 rounded-lg border border-border bg-surface p-6"
      @submit.prevent="soumettre"
    >
      <h2 class="text-base font-semibold text-text">
        Confirmer l'immobilisation — {{ ligneEnCours.compte_numero }}, {{ formaterMontant(ligneEnCours.montant) }}
        au {{ ligneEnCours.date_acquisition }}
      </h2>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Libellé</label>
          <input v-model="formulaire.libelle" required minlength="2" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Catégorie</label>
          <input v-model="formulaire.categorie" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
      </div>
      <div class="grid grid-cols-3 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">N° inventaire</label>
          <input v-model="formulaire.numero_inventaire" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Mise en service</label>
          <input v-model="formulaire.date_mise_en_service" type="date" :min="ligneEnCours.date_acquisition" required class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Valeur résiduelle</label>
          <MontantInput v-model="formulaire.valeur_residuelle" />
        </div>
      </div>
      <div class="grid grid-cols-3 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Durée (années)</label>
          <input v-model.number="formulaire.duree_amortissement_annees" type="number" min="1" max="100" required class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Méthode</label>
          <select v-model="formulaire.methode_amortissement" class="w-full rounded-md border border-border px-3 py-2 text-text">
            <option value="lineaire">Linéaire</option>
            <option value="degressif">Dégressif</option>
          </select>
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Taux dégressif (%)</label>
          <input
            v-model.number="formulaire.taux_degressif"
            type="number"
            step="0.01"
            min="0.01"
            max="100"
            :disabled="formulaire.methode_amortissement !== 'degressif'"
            :required="formulaire.methode_amortissement === 'degressif'"
            class="w-full rounded-md border border-border px-3 py-2 text-text disabled:opacity-60"
          />
        </div>
      </div>
      <div class="grid grid-cols-3 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Compte d'amortissement (28x)</label>
          <select v-model="formulaire.compte_amortissement_id" required class="w-full rounded-md border border-border px-3 py-2 text-text">
            <option value="" disabled>— Choisir —</option>
            <option v-for="c in comptesAmortissement" :key="c.id" :value="c.id">{{ c.numero }} — {{ c.libelle }}</option>
          </select>
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Compte de dotation (68x)</label>
          <select v-model="formulaire.compte_dotation_id" required class="w-full rounded-md border border-border px-3 py-2 text-text">
            <option value="" disabled>— Choisir —</option>
            <option v-for="c in comptesDotation" :key="c.id" :value="c.id">{{ c.numero }} — {{ c.libelle }}</option>
          </select>
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Fournisseur (optionnel)</label>
          <select v-model="formulaire.fournisseur_id" class="w-full rounded-md border border-border px-3 py-2 text-text">
            <option value="">— Aucun —</option>
            <option v-for="t in fournisseurs" :key="t.id" :value="t.id">{{ t.code }} — {{ t.raison_sociale }}</option>
          </select>
        </div>
      </div>
      <label class="flex items-center gap-2 text-sm text-text">
        <input v-model="formulaire.generer_plan" type="checkbox" />
        Générer le plan d'amortissement sur les exercices déjà ouverts
      </label>
      <p v-if="erreur" class="text-sm text-danger">{{ erreur }}</p>
      <div class="flex justify-end gap-2">
        <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted" @click="ligneEnCours = null">
          Annuler
        </button>
        <button type="submit" :disabled="confirmer.isPending.value" class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60">
          Créer l'immobilisation
        </button>
      </div>
    </form>
  </div>
</template>