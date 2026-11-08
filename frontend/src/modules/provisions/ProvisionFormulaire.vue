<script setup lang="ts">
/**
 * Création uniquement : la modification (ProvisionMiseAJour) se fait
 * depuis la page de détail et ne porte que sur les champs descriptifs
 * (libellé, tiers) — les comptes et le type sont figés après création
 * côté backend, même raisonnement que ImmobilisationFormulaire.vue.
 */
import { computed, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";

import { useAuth } from "@/core/auth/useAuth";
import { useComptesEntreprise } from "@/modules/comptabilite/api";
import { useListeTiers } from "@/modules/tiers/api";
import { messageErreur } from "@/core/api/erreurs";
import BaseFormulaire from "@/core/ui/BaseFormulaire.vue";
import { useMutationsProvisions } from "./api";
import type { TypeProvision } from "./types";

const router = useRouter();
const { contexteActif } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const { data: comptes } = useComptesEntreprise(entrepriseId);
const comptesDotation = computed(() => comptes.value?.filter((c) => c.classe === 6) ?? []);
const comptesReprise = computed(() => comptes.value?.filter((c) => c.classe === 7) ?? []);

// Classe de compte de provision attendue selon le type — même mapping
// que CLASSE_PROVISION_PAR_TYPE côté backend (service.py).
const classeProvisionParType: Record<TypeProvision, number> = {
  depreciation_creance: 4,
  depreciation_stock: 3,
  risque_charge: 1,
};

const { data: clients } = useListeTiers(
  entrepriseId,
  computed(() => ({ actifsSeulement: true, clientSeulement: true })),
);

const { creer } = useMutationsProvisions(entrepriseId);

const formulaire = reactive({
  libelle: "",
  type_provision: "depreciation_creance" as TypeProvision,
  tiers_id: "",
  compte_dotation_id: "",
  compte_provision_id: "",
  compte_reprise_id: "",
});

const comptesProvision = computed(
  () => comptes.value?.filter((c) => c.classe === classeProvisionParType[formulaire.type_provision]) ?? [],
);

// Le compte de provision choisi dépend du type : si le type change, un
// compte déjà sélectionné d'une autre classe n'a plus de sens.
watch(
  () => formulaire.type_provision,
  () => {
    formulaire.compte_provision_id = "";
  },
);

const erreur = ref<string | null>(null);
const enEnvoi = computed(() => creer.isPending.value);

async function soumettre(): Promise<void> {
  erreur.value = null;
  try {
    const provision = await creer.mutateAsync({
      libelle: formulaire.libelle,
      type_provision: formulaire.type_provision,
      tiers_id: formulaire.tiers_id || null,
      compte_dotation_id: formulaire.compte_dotation_id,
      compte_provision_id: formulaire.compte_provision_id,
      compte_reprise_id: formulaire.compte_reprise_id,
    });
    router.push({ name: "provisions.detail", params: { id: provision.id } });
  } catch (e) {
    erreur.value = messageErreur(e);
  }
}
</script>

<template>
  <div class="max-w-2xl space-y-6">
    <h1 class="text-lg font-semibold text-text">Nouvelle provision</h1>

    <BaseFormulaire
      titre="Informations"
      :erreur="erreur"
      :en-envoi="enEnvoi"
      @soumettre="soumettre"
      @annuler="router.push({ name: 'provisions.liste' })"
    >
      <div>
        <label class="mb-1 block text-sm font-medium text-text">Libellé</label>
        <input v-model="formulaire.libelle" required minlength="2" class="w-full rounded-md border border-border px-3 py-2 text-text" />
      </div>

      <div>
        <label class="mb-1 block text-sm font-medium text-text">Type de provision</label>
        <select v-model="formulaire.type_provision" class="w-full rounded-md border border-border px-3 py-2 text-text">
          <option value="depreciation_creance">Dépréciation de créance</option>
          <option value="depreciation_stock">Dépréciation de stock</option>
          <option value="risque_charge">Risques et charges</option>
        </select>
      </div>

      <div v-if="formulaire.type_provision === 'depreciation_creance'">
        <label class="mb-1 block text-sm font-medium text-text">Client concerné (optionnel)</label>
        <select v-model="formulaire.tiers_id" class="w-full rounded-md border border-border px-3 py-2 text-text">
          <option value="">— Aucun —</option>
          <option v-for="t in clients" :key="t.id" :value="t.id">{{ t.code }} — {{ t.raison_sociale }}</option>
        </select>
      </div>

      <div class="grid grid-cols-3 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Compte de dotation (charge)</label>
          <select v-model="formulaire.compte_dotation_id" required class="w-full rounded-md border border-border px-3 py-2 text-text">
            <option value="" disabled>— Choisir —</option>
            <option v-for="c in comptesDotation" :key="c.id" :value="c.id">{{ c.numero }} — {{ c.libelle }}</option>
          </select>
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Compte de provision</label>
          <select v-model="formulaire.compte_provision_id" required class="w-full rounded-md border border-border px-3 py-2 text-text">
            <option value="" disabled>— Choisir —</option>
            <option v-for="c in comptesProvision" :key="c.id" :value="c.id">{{ c.numero }} — {{ c.libelle }}</option>
          </select>
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Compte de reprise (produit)</label>
          <select v-model="formulaire.compte_reprise_id" required class="w-full rounded-md border border-border px-3 py-2 text-text">
            <option value="" disabled>— Choisir —</option>
            <option v-for="c in comptesReprise" :key="c.id" :value="c.id">{{ c.numero }} — {{ c.libelle }}</option>
          </select>
        </div>
      </div>
    </BaseFormulaire>
  </div>
</template>