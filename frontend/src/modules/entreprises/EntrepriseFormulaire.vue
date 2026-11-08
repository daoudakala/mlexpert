<script setup lang="ts">
/**
 * Création/modification d'une fiche entreprise + actions de statut
 * (archiver/suspendre/réactiver) — administrateur plateforme uniquement.
 * Même convention que TiersFormulaire.vue : route avec `:id` optionnel.
 */
import { computed, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { messageErreur } from "@/core/api/erreurs";
import BaseFormulaire from "@/core/ui/BaseFormulaire.vue";
import ConfirmDialog from "@/core/ui/ConfirmDialog.vue";
import StatutBadge from "@/core/ui/StatutBadge.vue";
import { useEntreprise, useMutationsEntreprises } from "./api";

const route = useRoute();
const router = useRouter();

const entrepriseId = computed(() => (route.params.id as string) || null);
const enEdition = computed(() => entrepriseId.value !== null);

const { data: entrepriseExistante } = useEntreprise(entrepriseId);
const { creer, modifier, archiver, suspendre, reactiver } = useMutationsEntreprises();

const formulaire = reactive({
  raison_sociale: "",
  sigle: "",
  forme_juridique: "",
  activite: "",
  adresse: "",
  email_contact: "",
  telephone_contact: "",
  referentiel_comptable: "SYSCOHADA",
  devise: "XOF",
  secteur: "",
  taille: "",
  niveau_risque: "",
  priorite: "",
  blocage_ecritures_cloture: true,
});

watch(
  entrepriseExistante,
  (e) => {
    if (!e) return;
    formulaire.raison_sociale = e.raison_sociale;
    formulaire.sigle = e.sigle ?? "";
    formulaire.forme_juridique = e.forme_juridique ?? "";
    formulaire.activite = e.activite ?? "";
    formulaire.adresse = e.adresse ?? "";
    formulaire.email_contact = e.email_contact ?? "";
    formulaire.telephone_contact = e.telephone_contact ?? "";
    formulaire.referentiel_comptable = e.referentiel_comptable;
    formulaire.devise = e.devise;
    formulaire.secteur = e.secteur ?? "";
    formulaire.taille = e.taille ?? "";
    formulaire.niveau_risque = e.niveau_risque ?? "";
    formulaire.priorite = e.priorite ?? "";
    formulaire.blocage_ecritures_cloture = e.blocage_ecritures_cloture;
  },
  { immediate: true },
);

const erreur = ref<string | null>(null);
const enEnvoi = computed(() => creer.isPending.value || modifier.isPending.value);

function champs() {
  return {
    raison_sociale: formulaire.raison_sociale,
    sigle: formulaire.sigle || null,
    forme_juridique: formulaire.forme_juridique || null,
    activite: formulaire.activite || null,
    adresse: formulaire.adresse || null,
    email_contact: formulaire.email_contact || null,
    telephone_contact: formulaire.telephone_contact || null,
    referentiel_comptable: formulaire.referentiel_comptable,
    devise: formulaire.devise,
    secteur: formulaire.secteur || null,
    taille: formulaire.taille || null,
    niveau_risque: formulaire.niveau_risque || null,
    priorite: formulaire.priorite || null,
    blocage_ecritures_cloture: formulaire.blocage_ecritures_cloture,
  };
}

async function soumettre(): Promise<void> {
  erreur.value = null;
  try {
    if (enEdition.value) {
      await modifier.mutateAsync({ id: entrepriseId.value!, donnees: champs() });
    } else {
      await creer.mutateAsync(champs());
    }
    router.push({ name: "entreprises.liste" });
  } catch (e) {
    erreur.value = messageErreur(e);
  }
}

const confirmationArchivage = ref(false);
const confirmationSuspension = ref(false);

async function confirmerArchivage(): Promise<void> {
  if (entrepriseId.value) await archiver.mutateAsync(entrepriseId.value);
}

async function confirmerSuspension(): Promise<void> {
  if (entrepriseId.value) await suspendre.mutateAsync(entrepriseId.value);
}

async function reactiverEntreprise(): Promise<void> {
  if (entrepriseId.value) await reactiver.mutateAsync(entrepriseId.value);
}
</script>

<template>
  <div class="max-w-2xl space-y-6">
    <h1 class="text-lg font-semibold text-text">
      {{ enEdition ? entrepriseExistante?.raison_sociale ?? "" : "Nouvelle entreprise" }}
    </h1>

    <BaseFormulaire
      :titre="enEdition ? 'Informations' : 'Créer une entreprise'"
      :erreur="erreur"
      :en-envoi="enEnvoi"
      @soumettre="soumettre"
      @annuler="router.push({ name: 'entreprises.liste' })"
    >
      <div>
        <label class="mb-1 block text-sm font-medium text-text">Raison sociale</label>
        <input v-model="formulaire.raison_sociale" required minlength="1" class="w-full rounded-md border border-border px-3 py-2 text-text" />
      </div>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Sigle</label>
          <input v-model="formulaire.sigle" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Forme juridique</label>
          <input v-model="formulaire.forme_juridique" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
      </div>
      <div>
        <label class="mb-1 block text-sm font-medium text-text">Activité</label>
        <input v-model="formulaire.activite" class="w-full rounded-md border border-border px-3 py-2 text-text" />
      </div>
      <div>
        <label class="mb-1 block text-sm font-medium text-text">Adresse</label>
        <textarea v-model="formulaire.adresse" rows="2" class="w-full rounded-md border border-border px-3 py-2 text-text" />
      </div>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Email de contact</label>
          <input v-model="formulaire.email_contact" type="email" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Téléphone de contact</label>
          <input v-model="formulaire.telephone_contact" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
      </div>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Référentiel comptable</label>
          <input v-model="formulaire.referentiel_comptable" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Devise</label>
          <input v-model="formulaire.devise" maxlength="3" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
      </div>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Secteur</label>
          <input v-model="formulaire.secteur" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Taille</label>
          <input v-model="formulaire.taille" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
      </div>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Niveau de risque</label>
          <input v-model="formulaire.niveau_risque" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Priorité</label>
          <input v-model="formulaire.priorite" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
      </div>
      <div>
        <label class="mb-1 block text-sm font-medium text-text">Options de clôture</label>
        <label class="flex items-center gap-2 text-sm text-text-muted">
          <input v-model="formulaire.blocage_ecritures_cloture" type="checkbox" />
          Bloquer la création/modification d'écritures sur un exercice clôturé
        </label>
      </div>
    </BaseFormulaire>

    <div v-if="enEdition && entrepriseExistante" class="flex items-center justify-between rounded-lg border border-border bg-surface p-6">
      <div class="flex items-center gap-3">
        <p class="text-sm font-medium text-text">Statut</p>
        <StatutBadge :libelle="entrepriseExistante.statut" />
      </div>
      <div class="flex gap-2">
        <button
          v-if="entrepriseExistante.statut === 'active'"
          type="button"
          class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted"
          @click="confirmationSuspension = true"
        >
          Suspendre
        </button>
        <button
          v-if="entrepriseExistante.statut === 'suspendue'"
          type="button"
          class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted"
          @click="reactiverEntreprise"
        >
          Réactiver
        </button>
        <button
          v-if="entrepriseExistante.statut !== 'archivee'"
          type="button"
          class="rounded-md border border-border px-3 py-1.5 text-sm text-danger hover:bg-surface-muted"
          @click="confirmationArchivage = true"
        >
          Archiver
        </button>
      </div>
    </div>

    <ConfirmDialog
      v-model:ouvert="confirmationSuspension"
      titre="Suspendre cette entreprise ?"
      message="Les utilisateurs affectés à cette entreprise ne pourront plus y accéder jusqu'à réactivation."
      libelle-confirmer="Suspendre"
      dangereux
      @confirmer="confirmerSuspension"
    />
    <ConfirmDialog
      v-model:ouvert="confirmationArchivage"
      titre="Archiver cette entreprise ?"
      message="L'entreprise ne sera plus accessible. Cette action reste réversible par un administrateur."
      libelle-confirmer="Archiver"
      dangereux
      @confirmer="confirmerArchivage"
    />
  </div>
</template>
