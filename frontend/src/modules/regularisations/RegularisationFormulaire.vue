<script setup lang="ts">
/**
 * Formulaire unique (pas de modification a posteriori, voir models.py) :
 * le choix du type détermine la classe attendue du compte d'origine —
 * charge (classe 6) pour une CCA ou une charge à payer, produit (classe 7)
 * pour une PCA ou un produit à recevoir — même mapping que
 * CLASSE_ORIGINE_PAR_TYPE côté backend (service.py). Le compte de
 * régularisation est toujours classe 4 (476/477/408/418), quel que soit
 * le type.
 */
import { computed, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";

import { useAuth } from "@/core/auth/useAuth";
import { useComptesEntreprise, useJournaux } from "@/modules/comptabilite/api";
import { useExercices } from "@/modules/exercices/api";
import { messageErreur } from "@/core/api/erreurs";
import BaseFormulaire from "@/core/ui/BaseFormulaire.vue";
import MontantInput from "@/core/ui/MontantInput.vue";
import { useMutationsRegularisations } from "./api";
import type { TypeRegularisation } from "./types";

const router = useRouter();
const { contexteActif } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const { data: comptes } = useComptesEntreprise(entrepriseId);
const { data: exercices } = useExercices(entrepriseId);
const { data: journaux } = useJournaux(entrepriseId);

const classeOrigineParType: Record<TypeRegularisation, number> = {
  charge_constatee_avance: 6,
  produit_constate_avance: 7,
  charge_a_payer: 6,
  produit_a_recevoir: 7,
};
const CLASSE_COMPTE_REGULARISATION = 4;

const libelleCompteOrigineParType: Record<TypeRegularisation, string> = {
  charge_constatee_avance: "charge",
  produit_constate_avance: "produit",
  charge_a_payer: "charge",
  produit_a_recevoir: "produit",
};

const { creer } = useMutationsRegularisations(entrepriseId);

const formulaire = reactive({
  libelle: "",
  type_regularisation: "charge_constatee_avance" as TypeRegularisation,
  exercice_id: "",
  compte_origine_id: "",
  compte_regularisation_id: "",
  journal_id: "",
  date_regularisation: "",
  montant: 0 as number,
});

const comptesOrigine = computed(
  () => comptes.value?.filter((c) => c.classe === classeOrigineParType[formulaire.type_regularisation]) ?? [],
);
const comptesRegularisation = computed(
  () => comptes.value?.filter((c) => c.classe === CLASSE_COMPTE_REGULARISATION) ?? [],
);

// Le compte d'origine choisi dépend du type : si le type change, un compte
// déjà sélectionné d'une autre classe n'a plus de sens.
watch(
  () => formulaire.type_regularisation,
  () => {
    formulaire.compte_origine_id = "";
  },
);

const erreur = ref<string | null>(null);
const enEnvoi = computed(() => creer.isPending.value);

async function soumettre(): Promise<void> {
  erreur.value = null;
  try {
    await creer.mutateAsync({ ...formulaire });
    router.push({ name: "regularisations.liste" });
  } catch (e) {
    erreur.value = messageErreur(e);
  }
}
</script>

<template>
  <div class="max-w-2xl space-y-6">
    <h1 class="text-lg font-semibold text-text">Nouvelle régularisation (CCA/PCA)</h1>

    <BaseFormulaire
      titre="Informations"
      :erreur="erreur"
      :en-envoi="enEnvoi"
      @soumettre="soumettre"
      @annuler="router.push({ name: 'regularisations.liste' })"
    >
      <div>
        <label class="mb-1 block text-sm font-medium text-text">Libellé</label>
        <input v-model="formulaire.libelle" required minlength="2" class="w-full rounded-md border border-border px-3 py-2 text-text" />
      </div>

      <div>
        <label class="mb-1 block text-sm font-medium text-text">Type de régularisation</label>
        <select v-model="formulaire.type_regularisation" class="w-full rounded-md border border-border px-3 py-2 text-text">
          <option value="charge_constatee_avance">Charge constatée d'avance (CCA)</option>
          <option value="produit_constate_avance">Produit constaté d'avance (PCA)</option>
          <option value="charge_a_payer">Charge à payer (FNP)</option>
          <option value="produit_a_recevoir">Produit à recevoir</option>
        </select>
      </div>

      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">
            Compte d'origine ({{ libelleCompteOrigineParType[formulaire.type_regularisation] }})
          </label>
          <select v-model="formulaire.compte_origine_id" required class="w-full rounded-md border border-border px-3 py-2 text-text">
            <option value="" disabled>— Choisir —</option>
            <option v-for="c in comptesOrigine" :key="c.id" :value="c.id">{{ c.numero }} — {{ c.libelle }}</option>
          </select>
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Compte de régularisation (476/477/408/418)</label>
          <select v-model="formulaire.compte_regularisation_id" required class="w-full rounded-md border border-border px-3 py-2 text-text">
            <option value="" disabled>— Choisir —</option>
            <option v-for="c in comptesRegularisation" :key="c.id" :value="c.id">{{ c.numero }} — {{ c.libelle }}</option>
          </select>
        </div>
      </div>

      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Exercice</label>
          <select v-model="formulaire.exercice_id" required class="w-full rounded-md border border-border px-3 py-2 text-text">
            <option value="" disabled>— Choisir —</option>
            <option v-for="e in exercices" :key="e.id" :value="e.id">{{ e.date_debut }} → {{ e.date_fin }}</option>
          </select>
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Journal</label>
          <select v-model="formulaire.journal_id" required class="w-full rounded-md border border-border px-3 py-2 text-text">
            <option value="" disabled>— Choisir —</option>
            <option v-for="j in journaux" :key="j.id" :value="j.id">{{ j.code }} — {{ j.libelle }}</option>
          </select>
        </div>
      </div>

      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Date</label>
          <input v-model="formulaire.date_regularisation" type="date" required class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Montant</label>
          <MontantInput v-model="formulaire.montant" required />
        </div>
      </div>
    </BaseFormulaire>
  </div>
</template>