<script setup lang="ts">
/**
 * Sert à la fois pour la création et la modification : la route porte un
 * `:id` optionnel (voir router/index.ts). En édition, `code` n'est pas
 * modifiable (identifiant stable, cf. ServiceTiers.modifier_tiers) et les
 * comptes collectifs se gèrent via leur propre bloc, parce que c'est une
 * route PUT séparée côté backend qui remplace toujours les deux valeurs
 * ensemble.
 */
import { computed, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useComptesCollectifs } from "@/modules/comptabilite/api";
import { useAuth } from "@/core/auth/useAuth";
import { messageErreur } from "@/core/api/erreurs";
import BaseFormulaire from "@/core/ui/BaseFormulaire.vue";
import ConfirmDialog from "@/core/ui/ConfirmDialog.vue";
import MontantInput from "@/core/ui/MontantInput.vue";
import { useMutationsTiers, useTiers } from "./api";
import type { DoublonNif } from "./types";
import { erreurApi } from "@/core/api/erreurs";

const route = useRoute();
const router = useRouter();
const { contexteActif } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const tiersId = computed(() => (route.params.id as string) || null);
const enEdition = computed(() => tiersId.value !== null);

const { data: tiersExistant } = useTiers(entrepriseId, tiersId);
const { data: comptesCollectifs } = useComptesCollectifs(entrepriseId);
const { creer, modifier, modifierComptesCollectifs, desactiver, reactiver } =
  useMutationsTiers(entrepriseId);

const formulaire = reactive({
  code: "",
  raison_sociale: "",
  nif: "",
  rccm: "",
  adresse: "",
  email: "",
  telephone: "",
  delai_paiement_jours: null as number | null,
  plafond_credit: null as number | null,
  compte_collectif_client_id: "" as string,
  compte_collectif_fournisseur_id: "" as string,
});

watch(
  tiersExistant,
  (t) => {
    if (!t) return;
    formulaire.code = t.code;
    formulaire.raison_sociale = t.raison_sociale;
    formulaire.nif = t.nif ?? "";
    formulaire.rccm = t.rccm ?? "";
    formulaire.adresse = t.adresse ?? "";
    formulaire.email = t.email ?? "";
    formulaire.telephone = t.telephone ?? "";
    formulaire.delai_paiement_jours = t.delai_paiement_jours;
    formulaire.plafond_credit = t.plafond_credit ? Number(t.plafond_credit) : null;
    formulaire.compte_collectif_client_id = t.compte_collectif_client_id ?? "";
    formulaire.compte_collectif_fournisseur_id = t.compte_collectif_fournisseur_id ?? "";
  },
  { immediate: true },
);

const erreur = ref<string | null>(null);
const doublonsNif = ref<DoublonNif["tiers_existants"] | null>(null);
const enEnvoi = computed(() => creer.isPending.value || modifier.isPending.value);

function champsOptionnels() {
  return {
    nif: formulaire.nif || null,
    rccm: formulaire.rccm || null,
    adresse: formulaire.adresse || null,
    email: formulaire.email || null,
    telephone: formulaire.telephone || null,
    delai_paiement_jours: formulaire.delai_paiement_jours,
    plafond_credit: formulaire.plafond_credit,
  };
}

async function soumettre(confirmerMalgreDoublon = false): Promise<void> {
  erreur.value = null;

  if (!enEdition.value && !formulaire.compte_collectif_client_id && !formulaire.compte_collectif_fournisseur_id) {
    erreur.value = "Un tiers doit être client, fournisseur, ou les deux.";
    return;
  }

  try {
    if (enEdition.value) {
      await modifier.mutateAsync({ id: tiersId.value!, donnees: champsOptionnels() });
    } else {
      await creer.mutateAsync({
        code: formulaire.code,
        raison_sociale: formulaire.raison_sociale,
        ...champsOptionnels(),
        compte_collectif_client_id: formulaire.compte_collectif_client_id || null,
        compte_collectif_fournisseur_id: formulaire.compte_collectif_fournisseur_id || null,
        confirmer_malgre_doublon: confirmerMalgreDoublon,
      });
    }
    router.push({ name: "tiers.liste" });
  } catch (e) {
    const err = erreurApi(e);
    if (err?.code === "conflit" && err.details?.tiers_existants) {
      doublonsNif.value = err.details.tiers_existants as DoublonNif["tiers_existants"];
      return;
    }
    erreur.value = messageErreur(e);
  }
}

async function confirmerMalgreDoublon(): Promise<void> {
  doublonsNif.value = null;
  await soumettre(true);
}

const enEnvoiComptes = computed(() => modifierComptesCollectifs.isPending.value);
const erreurComptes = ref<string | null>(null);

async function enregistrerComptesCollectifs(): Promise<void> {
  erreurComptes.value = null;
  if (!formulaire.compte_collectif_client_id && !formulaire.compte_collectif_fournisseur_id) {
    erreurComptes.value = "Un tiers doit être client, fournisseur, ou les deux.";
    return;
  }
  try {
    await modifierComptesCollectifs.mutateAsync({
      id: tiersId.value!,
      donnees: {
        compte_collectif_client_id: formulaire.compte_collectif_client_id || null,
        compte_collectif_fournisseur_id: formulaire.compte_collectif_fournisseur_id || null,
      },
    });
  } catch (e) {
    erreurComptes.value = messageErreur(e);
  }
}

const confirmationArchivage = ref(false);

async function basculerActivation(): Promise<void> {
  if (!tiersExistant.value) return;
  if (tiersExistant.value.actif) {
    confirmationArchivage.value = true;
  } else {
    await reactiver.mutateAsync(tiersId.value!);
  }
}

async function confirmerDesactivation(): Promise<void> {
  await desactiver.mutateAsync(tiersId.value!);
}
</script>

<template>
  <div class="max-w-2xl space-y-6">
    <h1 class="text-lg font-semibold text-text">
      {{ enEdition ? `Tiers ${tiersExistant?.code ?? ""}` : "Nouveau tiers" }}
    </h1>

    <BaseFormulaire
      :titre="enEdition ? 'Informations' : 'Créer un tiers'"
      :erreur="erreur"
      :en-envoi="enEnvoi"
      @soumettre="soumettre(false)"
      @annuler="router.push({ name: 'tiers.liste' })"
    >
      <div v-if="!enEdition">
        <label class="mb-1 block text-sm font-medium text-text">Code</label>
        <input
          v-model="formulaire.code"
          required
          maxlength="30"
          class="w-full rounded-md border border-border px-3 py-2 text-text"
        />
      </div>

      <div>
        <label class="mb-1 block text-sm font-medium text-text">Raison sociale</label>
        <input
          v-model="formulaire.raison_sociale"
          required
          minlength="2"
          class="w-full rounded-md border border-border px-3 py-2 text-text"
        />
      </div>

      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">NIF</label>
          <input v-model="formulaire.nif" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">RCCM</label>
          <input v-model="formulaire.rccm" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
      </div>

      <div>
        <label class="mb-1 block text-sm font-medium text-text">Adresse</label>
        <textarea v-model="formulaire.adresse" rows="2" class="w-full rounded-md border border-border px-3 py-2 text-text" />
      </div>

      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Email</label>
          <input v-model="formulaire.email" type="email" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Téléphone</label>
          <input v-model="formulaire.telephone" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
      </div>

      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Délai de paiement (jours)</label>
          <input
            v-model.number="formulaire.delai_paiement_jours"
            type="number"
            min="0"
            class="w-full rounded-md border border-border px-3 py-2 text-text"
          />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Plafond de crédit</label>
          <MontantInput v-model="formulaire.plafond_credit" />
        </div>
      </div>

      <template v-if="!enEdition">
        <p class="text-sm text-text-muted">
          Un tiers doit être client, fournisseur, ou les deux — renseigne au moins un compte collectif.
        </p>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="mb-1 block text-sm font-medium text-text">Compte collectif client</label>
            <select
              v-model="formulaire.compte_collectif_client_id"
              class="w-full rounded-md border border-border px-3 py-2 text-text"
            >
              <option value="">— Aucun —</option>
              <option v-for="c in comptesCollectifs" :key="c.id" :value="c.id">
                {{ c.numero }} — {{ c.libelle }}
              </option>
            </select>
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-text">Compte collectif fournisseur</label>
            <select
              v-model="formulaire.compte_collectif_fournisseur_id"
              class="w-full rounded-md border border-border px-3 py-2 text-text"
            >
              <option value="">— Aucun —</option>
              <option v-for="c in comptesCollectifs" :key="c.id" :value="c.id">
                {{ c.numero }} — {{ c.libelle }}
              </option>
            </select>
          </div>
        </div>
      </template>
    </BaseFormulaire>

    <template v-if="enEdition && tiersExistant">
      <div class="space-y-4 rounded-lg border border-border bg-surface p-6">
        <h2 class="text-base font-semibold text-text">Comptes collectifs</h2>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="mb-1 block text-sm font-medium text-text">Compte collectif client</label>
            <select
              v-model="formulaire.compte_collectif_client_id"
              class="w-full rounded-md border border-border px-3 py-2 text-text"
            >
              <option value="">— Aucun —</option>
              <option v-for="c in comptesCollectifs" :key="c.id" :value="c.id">
                {{ c.numero }} — {{ c.libelle }}
              </option>
            </select>
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-text">Compte collectif fournisseur</label>
            <select
              v-model="formulaire.compte_collectif_fournisseur_id"
              class="w-full rounded-md border border-border px-3 py-2 text-text"
            >
              <option value="">— Aucun —</option>
              <option v-for="c in comptesCollectifs" :key="c.id" :value="c.id">
                {{ c.numero }} — {{ c.libelle }}
              </option>
            </select>
          </div>
        </div>
        <p v-if="erreurComptes" class="text-sm text-danger">{{ erreurComptes }}</p>
        <div class="flex justify-end">
          <button
            type="button"
            :disabled="enEnvoiComptes"
            class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60"
            @click="enregistrerComptesCollectifs"
          >
            Enregistrer les comptes collectifs
          </button>
        </div>
      </div>

      <div class="flex items-center justify-between rounded-lg border border-border bg-surface p-6">
        <div>
          <p class="text-sm font-medium text-text">Statut</p>
          <p class="text-sm text-text-muted">
            {{ tiersExistant.actif ? "Ce tiers est actif." : "Ce tiers est désactivé." }}
          </p>
        </div>
        <button
          type="button"
          class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted"
          @click="basculerActivation"
        >
          {{ tiersExistant.actif ? "Désactiver" : "Réactiver" }}
        </button>
      </div>
    </template>

    <ConfirmDialog
      v-model:ouvert="confirmationArchivage"
      titre="Désactiver ce tiers ?"
      message="Il n'apparaîtra plus dans les listes actives, mais reste consultable."
      libelle-confirmer="Désactiver"
      dangereux
      @confirmer="confirmerDesactivation"
    />

    <div v-if="doublonsNif" class="rounded-lg border border-warning bg-warning-bg p-4 text-sm">
      <p class="font-medium text-text">Ce NIF correspond déjà à :</p>
      <ul class="mt-1 list-inside list-disc text-text-muted">
        <li v-for="t in doublonsNif" :key="t.id">{{ t.code }} — {{ t.raison_sociale }}</li>
      </ul>
      <div class="mt-3 flex gap-2">
        <button
          type="button"
          class="rounded-md border border-border px-3 py-1.5 text-text hover:bg-surface-muted"
          @click="doublonsNif = null"
        >
          Annuler
        </button>
        <button
          type="button"
          class="rounded-md bg-primary px-3 py-1.5 text-primary-foreground hover:bg-primary-hover"
          @click="confirmerMalgreDoublon"
        >
          Créer quand même
        </button>
      </div>
    </div>
  </div>
</template>
