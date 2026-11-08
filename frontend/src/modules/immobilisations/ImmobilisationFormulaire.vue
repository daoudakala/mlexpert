<script setup lang="ts">
/**
 * Création uniquement : la modification (ImmobilisationMiseAJour) se fait
 * depuis la page de détail et ne porte que sur les champs descriptifs
 * (libellé, catégorie, n° inventaire, fournisseur) — tout le reste
 * (valeurs, méthode, comptes) est figé après création côté backend.
 */
import { computed, reactive, ref } from "vue";
import { useRouter } from "vue-router";

import { useAuth } from "@/core/auth/useAuth";
import { useComptesEntreprise } from "@/modules/comptabilite/api";
import { useListeTiers } from "@/modules/tiers/api";
import { messageErreur } from "@/core/api/erreurs";
import BaseFormulaire from "@/core/ui/BaseFormulaire.vue";
import MontantInput from "@/core/ui/MontantInput.vue";
import { useMutationsImmobilisations } from "./api";
import type { MethodeAmortissement } from "./types";

const router = useRouter();
const { contexteActif } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const { data: comptes } = useComptesEntreprise(entrepriseId);
const comptesImmobilisation = computed(() => comptes.value?.filter((c) => c.classe === 2) ?? []);
const comptesAmortissement = computed(() => comptes.value?.filter((c) => c.classe === 2) ?? []);
const comptesDotation = computed(() => comptes.value?.filter((c) => c.classe === 6) ?? []);

const { data: fournisseurs } = useListeTiers(
  entrepriseId,
  computed(() => ({ actifsSeulement: true, fournisseurSeulement: true })),
);

const { creer } = useMutationsImmobilisations(entrepriseId);

const formulaire = reactive({
  libelle: "",
  categorie: "",
  numero_inventaire: "",
  date_acquisition: "",
  date_mise_en_service: "",
  valeur_origine: 0 as number,
  valeur_residuelle: 0 as number,
  duree_amortissement_annees: 5 as number,
  methode_amortissement: "lineaire" as MethodeAmortissement,
  taux_degressif: null as number | null,
  compte_immobilisation_id: "",
  compte_amortissement_id: "",
  compte_dotation_id: "",
  fournisseur_id: "",
});

const erreur = ref<string | null>(null);
const enEnvoi = computed(() => creer.isPending.value);

async function soumettre(): Promise<void> {
  erreur.value = null;
  try {
    const immobilisation = await creer.mutateAsync({
      libelle: formulaire.libelle,
      categorie: formulaire.categorie || null,
      numero_inventaire: formulaire.numero_inventaire || null,
      date_acquisition: formulaire.date_acquisition,
      date_mise_en_service: formulaire.date_mise_en_service,
      valeur_origine: formulaire.valeur_origine,
      valeur_residuelle: formulaire.valeur_residuelle,
      duree_amortissement_annees: formulaire.duree_amortissement_annees,
      methode_amortissement: formulaire.methode_amortissement,
      taux_degressif: formulaire.methode_amortissement === "degressif" ? formulaire.taux_degressif : null,
      compte_immobilisation_id: formulaire.compte_immobilisation_id,
      compte_amortissement_id: formulaire.compte_amortissement_id,
      compte_dotation_id: formulaire.compte_dotation_id,
      fournisseur_id: formulaire.fournisseur_id || null,
    });
    router.push({ name: "immobilisations.detail", params: { id: immobilisation.id } });
  } catch (e) {
    erreur.value = messageErreur(e);
  }
}
</script>

<template>
  <div class="max-w-2xl space-y-6">
    <h1 class="text-lg font-semibold text-text">Nouvelle immobilisation</h1>

    <BaseFormulaire
      titre="Informations"
      :erreur="erreur"
      :en-envoi="enEnvoi"
      @soumettre="soumettre"
      @annuler="router.push({ name: 'immobilisations.liste' })"
    >
      <div>
        <label class="mb-1 block text-sm font-medium text-text">Libellé</label>
        <input v-model="formulaire.libelle" required minlength="2" class="w-full rounded-md border border-border px-3 py-2 text-text" />
      </div>

      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Catégorie</label>
          <input v-model="formulaire.categorie" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">N° inventaire</label>
          <input v-model="formulaire.numero_inventaire" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
      </div>

      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Date d'acquisition</label>
          <input v-model="formulaire.date_acquisition" type="date" required class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Date de mise en service</label>
          <input v-model="formulaire.date_mise_en_service" type="date" required class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
      </div>

      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Valeur d'origine</label>
          <MontantInput v-model="formulaire.valeur_origine" required />
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
          <label class="mb-1 block text-sm font-medium text-text">Compte immobilisation</label>
          <select v-model="formulaire.compte_immobilisation_id" required class="w-full rounded-md border border-border px-3 py-2 text-text">
            <option value="" disabled>— Choisir —</option>
            <option v-for="c in comptesImmobilisation" :key="c.id" :value="c.id">{{ c.numero }} — {{ c.libelle }}</option>
          </select>
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Compte amortissement</label>
          <select v-model="formulaire.compte_amortissement_id" required class="w-full rounded-md border border-border px-3 py-2 text-text">
            <option value="" disabled>— Choisir —</option>
            <option v-for="c in comptesAmortissement" :key="c.id" :value="c.id">{{ c.numero }} — {{ c.libelle }}</option>
          </select>
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Compte dotation</label>
          <select v-model="formulaire.compte_dotation_id" required class="w-full rounded-md border border-border px-3 py-2 text-text">
            <option value="" disabled>— Choisir —</option>
            <option v-for="c in comptesDotation" :key="c.id" :value="c.id">{{ c.numero }} — {{ c.libelle }}</option>
          </select>
        </div>
      </div>

      <div>
        <label class="mb-1 block text-sm font-medium text-text">Fournisseur (optionnel)</label>
        <select v-model="formulaire.fournisseur_id" class="w-full rounded-md border border-border px-3 py-2 text-text">
          <option value="">— Aucun —</option>
          <option v-for="t in fournisseurs" :key="t.id" :value="t.id">{{ t.code }} — {{ t.raison_sociale }}</option>
        </select>
      </div>
    </BaseFormulaire>
  </div>
</template>
