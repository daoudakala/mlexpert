<script setup lang="ts">
/**
 * Création d'un compte bancaire uniquement : il n'existe pas de route de
 * modification côté backend (router.py n'a que creer/lister/lire/
 * desactiver) — une fois créé, seuls le libellé affiché ailleurs et le
 * statut actif/désactivé peuvent encore bouger, et la désactivation se
 * fait depuis la page de détail.
 */
import { computed, reactive, ref } from "vue";
import { useRouter } from "vue-router";

import { useAuth } from "@/core/auth/useAuth";
import { useComptesEntreprise, useJournaux } from "@/modules/comptabilite/api";
import { messageErreur } from "@/core/api/erreurs";
import BaseFormulaire from "@/core/ui/BaseFormulaire.vue";
import MontantInput from "@/core/ui/MontantInput.vue";
import { useMutationsComptesBancaires } from "./api";

const router = useRouter();
const { contexteActif } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const { data: journaux } = useJournaux(entrepriseId);
const { data: comptes } = useComptesEntreprise(entrepriseId);
// Un compte bancaire s'appuie sur un journal de type banque ou caisse
// (TypeJournal, voir comptabilite/models.py) : filtrer la liste évite de
// pouvoir en choisir un d'achats ou de ventes par erreur.
const journauxEligibles = computed(
  () => journaux.value?.filter((j) => j.type_journal === "banque" || j.type_journal === "caisse") ?? [],
);

const { creer } = useMutationsComptesBancaires(entrepriseId);

const formulaire = reactive({
  libelle: "",
  banque: "",
  numero_compte: "",
  iban: "",
  journal_id: "",
  compte_comptable_id: "",
  solde_initial: 0 as number,
});

const erreur = ref<string | null>(null);
const enEnvoi = computed(() => creer.isPending.value);

async function soumettre(): Promise<void> {
  erreur.value = null;
  try {
    const compte = await creer.mutateAsync({
      libelle: formulaire.libelle,
      banque: formulaire.banque || null,
      numero_compte: formulaire.numero_compte || null,
      iban: formulaire.iban || null,
      journal_id: formulaire.journal_id,
      compte_comptable_id: formulaire.compte_comptable_id,
      solde_initial: formulaire.solde_initial,
    });
    router.push({ name: "tresorerie.compte-bancaire", params: { id: compte.id } });
  } catch (e) {
    erreur.value = messageErreur(e);
  }
}
</script>

<template>
  <div class="max-w-2xl space-y-6">
    <h1 class="text-lg font-semibold text-text">Nouveau compte bancaire</h1>

    <BaseFormulaire
      titre="Informations"
      :erreur="erreur"
      :en-envoi="enEnvoi"
      @soumettre="soumettre"
      @annuler="router.push({ name: 'tresorerie.comptes-bancaires' })"
    >
      <div>
        <label class="mb-1 block text-sm font-medium text-text">Libellé</label>
        <input
          v-model="formulaire.libelle"
          required
          minlength="2"
          class="w-full rounded-md border border-border px-3 py-2 text-text"
        />
      </div>

      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Banque</label>
          <input v-model="formulaire.banque" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">N° de compte</label>
          <input
            v-model="formulaire.numero_compte"
            class="w-full rounded-md border border-border px-3 py-2 text-text"
          />
        </div>
      </div>

      <div>
        <label class="mb-1 block text-sm font-medium text-text">IBAN</label>
        <input v-model="formulaire.iban" class="w-full rounded-md border border-border px-3 py-2 text-text" />
      </div>

      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Journal</label>
          <select
            v-model="formulaire.journal_id"
            required
            class="w-full rounded-md border border-border px-3 py-2 text-text"
          >
            <option value="" disabled>— Choisir —</option>
            <option v-for="j in journauxEligibles" :key="j.id" :value="j.id">
              {{ j.code }} — {{ j.libelle }}
            </option>
          </select>
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Compte comptable</label>
          <select
            v-model="formulaire.compte_comptable_id"
            required
            class="w-full rounded-md border border-border px-3 py-2 text-text"
          >
            <option value="" disabled>— Choisir —</option>
            <option v-for="c in comptes" :key="c.id" :value="c.id">
              {{ c.numero }} — {{ c.libelle }}
            </option>
          </select>
        </div>
      </div>

      <div>
        <label class="mb-1 block text-sm font-medium text-text">Solde initial</label>
        <MontantInput v-model="formulaire.solde_initial" />
      </div>
    </BaseFormulaire>
  </div>
</template>
