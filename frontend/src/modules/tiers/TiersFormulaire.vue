<script setup lang="ts">
/**
 * Création et modification d'un tiers (la route porte un `:id` optionnel).
 *
 * Un tiers est un client, un fournisseur, ou les deux, et il est TOUJOURS
 * rattaché à un compte général de regroupement : 41x pour un client (ex.
 * 411), 40x pour un fournisseur (ex. 401). Ce lien est obligatoire à la
 * création : c'est lui qui fait alimenter le compte collectif par les
 * écritures du tiers et qui permet de rapprocher la balance auxiliaire de
 * la balance générale.
 *
 * Fiche volontairement réduite : code et raison sociale seulement (NIF,
 * RCCM, adresse, email, téléphone, délai de paiement et plafond de crédit
 * ne sont plus saisis ici).
 *
 * En édition, `code` n'est pas modifiable (identifiant stable) et les
 * comptes de regroupement s'enregistrent via leur propre bloc (route PUT
 * séparée côté backend, qui remplace toujours les deux valeurs ensemble).
 */
import { computed, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useComptesEntreprise } from "@/modules/comptabilite/api";
import { useAuth } from "@/core/auth/useAuth";
import { messageErreur } from "@/core/api/erreurs";
import BaseFormulaire from "@/core/ui/BaseFormulaire.vue";
import ConfirmDialog from "@/core/ui/ConfirmDialog.vue";
import { useMutationsTiers, useTiers } from "./api";

const route = useRoute();
const router = useRouter();
const { contexteActif } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const tiersId = computed(() => (route.params.id as string) || null);
const enEdition = computed(() => tiersId.value !== null);

const { data: tiersExistant } = useTiers(entrepriseId, tiersId);
const { data: comptes } = useComptesEntreprise(entrepriseId, computed(() => ({ limite: 5000 })));
const { creer, modifier, modifierComptesCollectifs, desactiver, reactiver } =
  useMutationsTiers(entrepriseId);

const formulaire = reactive({
  code: "",
  raison_sociale: "",
  est_client: true,
  est_fournisseur: false,
  compte_client_id: "" as string,
  compte_fournisseur_id: "" as string,
});

// --- Comptes de regroupement proposés -----------------------------------------

function comptesDeLaFamille(prefixe: string, idActuel: string) {
  return (comptes.value ?? [])
    .filter((c) => c.numero.startsWith(prefixe) && (c.actif || c.id === idActuel))
    .sort((a, b) => a.numero.localeCompare(b.numero));
}

const comptesClients = computed(() => comptesDeLaFamille("41", formulaire.compte_client_id));
const comptesFournisseurs = computed(() => comptesDeLaFamille("40", formulaire.compte_fournisseur_id));

// Présélection : le premier compte de la famille (le plus général, ex. 411
// ou 401), dès qu'un rôle est coché et qu'aucun compte n'est choisi.
watch(
  [() => formulaire.est_client, comptesClients],
  () => {
    if (formulaire.est_client && !formulaire.compte_client_id && comptesClients.value.length > 0) {
      formulaire.compte_client_id = comptesClients.value[0].id;
    }
  },
  { immediate: true },
);
watch(
  [() => formulaire.est_fournisseur, comptesFournisseurs],
  () => {
    if (
      formulaire.est_fournisseur &&
      !formulaire.compte_fournisseur_id &&
      comptesFournisseurs.value.length > 0
    ) {
      formulaire.compte_fournisseur_id = comptesFournisseurs.value[0].id;
    }
  },
  { immediate: true },
);

watch(
  tiersExistant,
  (t) => {
    if (!t) return;
    formulaire.code = t.code;
    formulaire.raison_sociale = t.raison_sociale;
    formulaire.compte_client_id = t.compte_collectif_client_id ?? "";
    formulaire.compte_fournisseur_id = t.compte_collectif_fournisseur_id ?? "";
    formulaire.est_client = t.compte_collectif_client_id !== null;
    formulaire.est_fournisseur = t.compte_collectif_fournisseur_id !== null;
  },
  { immediate: true },
);

// --- Validation commune aux deux blocs ----------------------------------------

function erreurComptesRegroupement(): string | null {
  if (!formulaire.est_client && !formulaire.est_fournisseur) {
    return "Un tiers doit être client, fournisseur, ou les deux.";
  }
  if (formulaire.est_client && !formulaire.compte_client_id) {
    return "Choisissez le compte de regroupement client (41x, ex. 411).";
  }
  if (formulaire.est_fournisseur && !formulaire.compte_fournisseur_id) {
    return "Choisissez le compte de regroupement fournisseur (40x, ex. 401).";
  }
  return null;
}

function comptesChoisis() {
  return {
    compte_collectif_client_id: formulaire.est_client ? formulaire.compte_client_id || null : null,
    compte_collectif_fournisseur_id: formulaire.est_fournisseur
      ? formulaire.compte_fournisseur_id || null
      : null,
  };
}

// --- Enregistrement -------------------------------------------------------------

const erreur = ref<string | null>(null);
const enEnvoi = computed(() => creer.isPending.value || modifier.isPending.value);

async function soumettre(): Promise<void> {
  erreur.value = null;

  if (!enEdition.value) {
    const probleme = erreurComptesRegroupement();
    if (probleme) {
      erreur.value = probleme;
      return;
    }
  }

  try {
    if (enEdition.value) {
      await modifier.mutateAsync({
        id: tiersId.value!,
        donnees: { raison_sociale: formulaire.raison_sociale },
      });
    } else {
      await creer.mutateAsync({
        code: formulaire.code,
        raison_sociale: formulaire.raison_sociale,
        ...comptesChoisis(),
      });
    }
    router.push({ name: "tiers.liste" });
  } catch (e) {
    erreur.value = messageErreur(e);
  }
}

const enEnvoiComptes = computed(() => modifierComptesCollectifs.isPending.value);
const erreurComptes = ref<string | null>(null);
const confirmeComptes = ref(false);

async function enregistrerComptesCollectifs(): Promise<void> {
  erreurComptes.value = null;
  confirmeComptes.value = false;
  const probleme = erreurComptesRegroupement();
  if (probleme) {
    erreurComptes.value = probleme;
    return;
  }
  try {
    await modifierComptesCollectifs.mutateAsync({ id: tiersId.value!, donnees: comptesChoisis() });
    confirmeComptes.value = true;
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
      @soumettre="soumettre"
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

      <!-- Création : rôle et compte de regroupement (obligatoires) -->
      <fieldset v-if="!enEdition" class="space-y-4">
        <legend class="text-sm font-medium text-text">Compte de regroupement (obligatoire)</legend>
        <p class="text-sm text-text-muted">
          Le tiers est rattaché à un compte général : les écritures du tiers alimentent ce compte.
        </p>

        <div class="grid grid-cols-2 gap-4">
          <div class="space-y-2">
            <label class="flex items-center gap-2 text-sm text-text">
              <input v-model="formulaire.est_client" type="checkbox" />
              Client (compte 41x)
            </label>
            <select
              v-model="formulaire.compte_client_id"
              :disabled="!formulaire.est_client"
              class="w-full rounded-md border border-border px-3 py-2 text-text disabled:opacity-50"
            >
              <option value="" disabled>— Choisir —</option>
              <option v-for="c in comptesClients" :key="c.id" :value="c.id">
                {{ c.numero }} — {{ c.libelle }}
              </option>
            </select>
            <p v-if="formulaire.est_client && comptesClients.length === 0" class="text-xs text-danger">
              Aucun compte 41x dans le plan comptable : importez ou créez d'abord le compte 411.
            </p>
          </div>

          <div class="space-y-2">
            <label class="flex items-center gap-2 text-sm text-text">
              <input v-model="formulaire.est_fournisseur" type="checkbox" />
              Fournisseur (compte 40x)
            </label>
            <select
              v-model="formulaire.compte_fournisseur_id"
              :disabled="!formulaire.est_fournisseur"
              class="w-full rounded-md border border-border px-3 py-2 text-text disabled:opacity-50"
            >
              <option value="" disabled>— Choisir —</option>
              <option v-for="c in comptesFournisseurs" :key="c.id" :value="c.id">
                {{ c.numero }} — {{ c.libelle }}
              </option>
            </select>
            <p v-if="formulaire.est_fournisseur && comptesFournisseurs.length === 0" class="text-xs text-danger">
              Aucun compte 40x dans le plan comptable : importez ou créez d'abord le compte 401.
            </p>
          </div>
        </div>
      </fieldset>
    </BaseFormulaire>

    <template v-if="enEdition && tiersExistant">
      <div class="space-y-4 rounded-lg border border-border bg-surface p-6">
        <h2 class="text-base font-semibold text-text">Compte de regroupement</h2>
        <div class="grid grid-cols-2 gap-4">
          <div class="space-y-2">
            <label class="flex items-center gap-2 text-sm text-text">
              <input v-model="formulaire.est_client" type="checkbox" />
              Client (compte 41x)
            </label>
            <select
              v-model="formulaire.compte_client_id"
              :disabled="!formulaire.est_client"
              class="w-full rounded-md border border-border px-3 py-2 text-text disabled:opacity-50"
            >
              <option value="" disabled>— Choisir —</option>
              <option v-for="c in comptesClients" :key="c.id" :value="c.id">
                {{ c.numero }} — {{ c.libelle }}
              </option>
            </select>
          </div>
          <div class="space-y-2">
            <label class="flex items-center gap-2 text-sm text-text">
              <input v-model="formulaire.est_fournisseur" type="checkbox" />
              Fournisseur (compte 40x)
            </label>
            <select
              v-model="formulaire.compte_fournisseur_id"
              :disabled="!formulaire.est_fournisseur"
              class="w-full rounded-md border border-border px-3 py-2 text-text disabled:opacity-50"
            >
              <option value="" disabled>— Choisir —</option>
              <option v-for="c in comptesFournisseurs" :key="c.id" :value="c.id">
                {{ c.numero }} — {{ c.libelle }}
              </option>
            </select>
          </div>
        </div>
        <p v-if="erreurComptes" class="text-sm text-danger">{{ erreurComptes }}</p>
        <p v-else-if="confirmeComptes" class="text-sm text-success">Compte de regroupement enregistré.</p>
        <div class="flex justify-end">
          <button
            type="button"
            :disabled="enEnvoiComptes"
            class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60"
            @click="enregistrerComptesCollectifs"
          >
            Enregistrer le compte de regroupement
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
  </div>
</template>