<script setup lang="ts">
/**
 * Création/modification d'une fiche employé. Même convention que
 * TiersFormulaire.vue : route avec `:id` optionnel. Le matricule et la
 * date d'embauche ne sont pas modifiables une fois créés (identifiants
 * stables, cf. ServicePaie.modifier_employe qui n'accepte pas ces champs).
 */
import { computed, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { messageErreur } from "@/core/api/erreurs";
import { useAuth } from "@/core/auth/useAuth";
import BaseFormulaire from "@/core/ui/BaseFormulaire.vue";
import MontantInput from "@/core/ui/MontantInput.vue";
import { useEmploye, useMutationsEmployes } from "./api";

const route = useRoute();
const router = useRouter();
const { contexteActif } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const employeId = computed(() => (route.params.id as string) || null);
const enEdition = computed(() => employeId.value !== null);

const { data: employeExistant } = useEmploye(entrepriseId, employeId);
const { creer, modifier, desactiver, reactiver } = useMutationsEmployes(entrepriseId);

const formulaire = reactive({
  matricule: "",
  nom: "",
  prenom: "",
  poste: "",
  date_embauche: "",
  salaire_base: null as number | null,
});

watch(
  employeExistant,
  (e) => {
    if (!e) return;
    formulaire.matricule = e.matricule;
    formulaire.nom = e.nom;
    formulaire.prenom = e.prenom;
    formulaire.poste = e.poste ?? "";
    formulaire.date_embauche = e.date_embauche;
    formulaire.salaire_base = Number(e.salaire_base);
  },
  { immediate: true },
);

const erreur = ref<string | null>(null);
const enEnvoi = computed(() => creer.isPending.value || modifier.isPending.value);

async function soumettre(): Promise<void> {
  erreur.value = null;
  try {
    if (enEdition.value) {
      await modifier.mutateAsync({
        id: employeId.value!,
        donnees: {
          nom: formulaire.nom,
          prenom: formulaire.prenom,
          poste: formulaire.poste || null,
          salaire_base: formulaire.salaire_base ?? undefined,
        },
      });
    } else {
      await creer.mutateAsync({
        matricule: formulaire.matricule,
        nom: formulaire.nom,
        prenom: formulaire.prenom,
        poste: formulaire.poste || null,
        date_embauche: formulaire.date_embauche,
        salaire_base: formulaire.salaire_base ?? 0,
      });
    }
    router.push({ name: "paie.employes" });
  } catch (e) {
    erreur.value = messageErreur(e);
  }
}

const confirmationDesactivation = ref(false);
const dateSortie = ref("");

async function confirmerDesactivation(): Promise<void> {
  if (employeId.value) await desactiver.mutateAsync({ id: employeId.value, date_sortie: dateSortie.value });
}

async function reactiverEmploye(): Promise<void> {
  if (employeId.value) await reactiver.mutateAsync(employeId.value);
}
</script>

<template>
  <div class="max-w-2xl space-y-6">
    <h1 class="text-lg font-semibold text-text">
      {{ enEdition ? `${employeExistant?.prenom ?? ""} ${employeExistant?.nom ?? ""}` : "Nouvel employé" }}
    </h1>

    <BaseFormulaire
      :titre="enEdition ? 'Informations' : 'Créer un employé'"
      :erreur="erreur"
      :en-envoi="enEnvoi"
      @soumettre="soumettre"
      @annuler="router.push({ name: 'paie.employes' })"
    >
      <div v-if="!enEdition">
        <label class="mb-1 block text-sm font-medium text-text">Matricule</label>
        <input v-model="formulaire.matricule" required maxlength="30" class="w-full rounded-md border border-border px-3 py-2 text-text" />
      </div>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Prénom</label>
          <input v-model="formulaire.prenom" required class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Nom</label>
          <input v-model="formulaire.nom" required class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
      </div>
      <div>
        <label class="mb-1 block text-sm font-medium text-text">Poste</label>
        <input v-model="formulaire.poste" class="w-full rounded-md border border-border px-3 py-2 text-text" />
      </div>
      <div class="grid grid-cols-2 gap-4">
        <div v-if="!enEdition">
          <label class="mb-1 block text-sm font-medium text-text">Date d'embauche</label>
          <input v-model="formulaire.date_embauche" type="date" required class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Salaire de base</label>
          <MontantInput v-model="formulaire.salaire_base" required />
        </div>
      </div>
    </BaseFormulaire>

    <template v-if="enEdition && employeExistant">
      <div class="flex items-center justify-between rounded-lg border border-border bg-surface p-6">
        <div>
          <p class="text-sm font-medium text-text">Statut</p>
          <p class="text-sm text-text-muted">
            {{ employeExistant.statut === "actif" ? "Cet employé est actif." : `Sorti le ${employeExistant.date_sortie}.` }}
          </p>
        </div>
        <button
          v-if="employeExistant.statut === 'actif'"
          type="button"
          class="rounded-md border border-border px-3 py-1.5 text-sm text-danger hover:bg-surface-muted"
          @click="confirmationDesactivation = true"
        >
          Désactiver
        </button>
        <button
          v-else
          type="button"
          class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted"
          @click="reactiverEmploye"
        >
          Réactiver
        </button>
      </div>
    </template>

    <div
      v-if="confirmationDesactivation"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      @click.self="confirmationDesactivation = false"
    >
      <div class="w-full max-w-sm rounded-lg bg-surface p-6 shadow-lg">
        <h2 class="text-base font-semibold text-text">Désactiver cet employé ?</h2>
        <label class="mt-3 block text-sm font-medium text-text">Date de sortie</label>
        <input v-model="dateSortie" type="date" required class="mt-1 w-full rounded-md border border-border px-3 py-2 text-text" />
        <div class="mt-4 flex justify-end gap-2">
          <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted" @click="confirmationDesactivation = false">
            Annuler
          </button>
          <button
            type="button"
            :disabled="!dateSortie || desactiver.isPending.value"
            class="rounded-md bg-danger px-3 py-1.5 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
            @click="confirmerDesactivation(); confirmationDesactivation = false"
          >
            Désactiver
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
