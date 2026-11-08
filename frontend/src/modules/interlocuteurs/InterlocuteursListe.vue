<script setup lang="ts">
/**
 * Page unique pour tout le module : liste + création + édition +
 * désactivation/réactivation. Même gabarit que `documents/DocumentsListe.vue`
 * (une seule table, pas de sous-objets) — pas de route de détail séparée.
 */
import { computed, reactive, ref } from "vue";

import { useAuth } from "@/core/auth/useAuth";
import { messageErreur } from "@/core/api/erreurs";
import BaseDataTable, { type ColonneTable } from "@/core/ui/BaseDataTable.vue";
import StatutBadge from "@/core/ui/StatutBadge.vue";
import { useListeInterlocuteurs, useMutationsInterlocuteurs, type FiltresInterlocuteurs } from "./api";
import { ROLES_INTERLOCUTEUR, type Interlocuteur, type RoleInterlocuteur } from "./types";

const { contexteActif, aPermission } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const filtres = reactive<FiltresInterlocuteurs>({ role: null, actifsSeulement: true });
const { data: interlocuteurs, isLoading } = useListeInterlocuteurs(entrepriseId, computed(() => filtres));
const { creer, modifier, desactiver, reactiver } = useMutationsInterlocuteurs(entrepriseId);

function libelleRole(role: string): string {
  return ROLES_INTERLOCUTEUR.find((r) => r.valeur === role)?.libelle ?? role;
}

const colonnes: ColonneTable<Interlocuteur>[] = [
  { cle: "nom", libelle: "Nom" },
  { cle: "role", libelle: "Rôle" },
  { cle: "fonction", libelle: "Fonction" },
  { cle: "email", libelle: "Email" },
  { cle: "telephone", libelle: "Téléphone" },
  { cle: "pourcentage_detention", libelle: "% détention" },
  { cle: "actif", libelle: "Statut" },
];

// --- Création ---

const creationOuverte = ref(false);
const creation = reactive({
  nom: "",
  role: "dirigeant" as RoleInterlocuteur,
  fonction: "",
  email: "",
  telephone: "",
  pourcentage_detention: "" as string | number,
  notes: "",
});
const erreurCreation = ref<string | null>(null);

function reinitialiserCreation(): void {
  creation.nom = "";
  creation.role = "dirigeant";
  creation.fonction = "";
  creation.email = "";
  creation.telephone = "";
  creation.pourcentage_detention = "";
  creation.notes = "";
}

async function soumettreCreation(): Promise<void> {
  erreurCreation.value = null;
  try {
    await creer.mutateAsync({
      nom: creation.nom,
      role: creation.role,
      fonction: creation.fonction || null,
      email: creation.email || null,
      telephone: creation.telephone || null,
      pourcentage_detention:
        creation.role === "associe" && creation.pourcentage_detention !== ""
          ? Number(creation.pourcentage_detention)
          : null,
      notes: creation.notes || null,
    });
    creationOuverte.value = false;
    reinitialiserCreation();
  } catch (e) {
    erreurCreation.value = messageErreur(e);
  }
}

// --- Édition ---

const interlocuteurEnEdition = ref<Interlocuteur | null>(null);
const edition = reactive({
  nom: "",
  role: "dirigeant" as RoleInterlocuteur,
  fonction: "",
  email: "",
  telephone: "",
  pourcentage_detention: "" as string | number,
  notes: "",
});
const erreurEdition = ref<string | null>(null);

function ouvrirEdition(interlocuteur: Interlocuteur): void {
  interlocuteurEnEdition.value = interlocuteur;
  edition.nom = interlocuteur.nom;
  edition.role = interlocuteur.role;
  edition.fonction = interlocuteur.fonction ?? "";
  edition.email = interlocuteur.email ?? "";
  edition.telephone = interlocuteur.telephone ?? "";
  edition.pourcentage_detention = interlocuteur.pourcentage_detention ?? "";
  edition.notes = interlocuteur.notes ?? "";
  erreurEdition.value = null;
}

async function enregistrerEdition(): Promise<void> {
  if (!interlocuteurEnEdition.value) return;
  erreurEdition.value = null;
  try {
    await modifier.mutateAsync({
      id: interlocuteurEnEdition.value.id,
      donnees: {
        nom: edition.nom,
        role: edition.role,
        fonction: edition.fonction || null,
        email: edition.email || null,
        telephone: edition.telephone || null,
        pourcentage_detention:
          edition.role === "associe" && edition.pourcentage_detention !== ""
            ? Number(edition.pourcentage_detention)
            : null,
        notes: edition.notes || null,
      },
    });
    interlocuteurEnEdition.value = null;
  } catch (e) {
    erreurEdition.value = messageErreur(e);
  }
}

async function basculerActif(interlocuteur: Interlocuteur): Promise<void> {
  if (interlocuteur.actif) {
    await desactiver.mutateAsync(interlocuteur.id);
  } else {
    await reactiver.mutateAsync(interlocuteur.id);
  }
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-lg font-semibold text-text">Interlocuteurs</h1>
      <button
        v-if="aPermission('interlocuteur.creer')"
        type="button"
        class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover"
        @click="creationOuverte = !creationOuverte"
      >
        Ajouter un interlocuteur
      </button>
    </div>

    <div class="flex flex-wrap items-center gap-4">
      <select v-model="filtres.role" class="rounded-md border border-border px-3 py-2 text-sm text-text">
        <option :value="null">Tous les rôles</option>
        <option v-for="r in ROLES_INTERLOCUTEUR" :key="r.valeur" :value="r.valeur">{{ r.libelle }}</option>
      </select>
      <label class="flex items-center gap-2 text-sm text-text-muted">
        <input v-model="filtres.actifsSeulement" type="checkbox" />
        Actifs seulement
      </label>
    </div>

    <form
      v-if="creationOuverte"
      class="space-y-4 rounded-lg border border-border bg-surface p-6"
      @submit.prevent="soumettreCreation"
    >
      <h2 class="text-base font-semibold text-text">Ajouter un interlocuteur</h2>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Nom</label>
          <input v-model="creation.nom" required class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Rôle</label>
          <select v-model="creation.role" class="w-full rounded-md border border-border px-3 py-2 text-text">
            <option v-for="r in ROLES_INTERLOCUTEUR" :key="r.valeur" :value="r.valeur">{{ r.libelle }}</option>
          </select>
        </div>
      </div>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Fonction</label>
          <input v-model="creation.fonction" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div v-if="creation.role === 'associe'">
          <label class="mb-1 block text-sm font-medium text-text">% de détention</label>
          <input
            v-model="creation.pourcentage_detention"
            type="number"
            min="0"
            max="100"
            step="0.01"
            class="w-full rounded-md border border-border px-3 py-2 text-text"
          />
        </div>
      </div>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Email</label>
          <input v-model="creation.email" type="email" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Téléphone</label>
          <input v-model="creation.telephone" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
      </div>
      <div>
        <label class="mb-1 block text-sm font-medium text-text">Notes</label>
        <input v-model="creation.notes" class="w-full rounded-md border border-border px-3 py-2 text-text" />
      </div>
      <p v-if="erreurCreation" class="text-sm text-danger">{{ erreurCreation }}</p>
      <div class="flex justify-end gap-2">
        <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted" @click="creationOuverte = false">
          Annuler
        </button>
        <button type="submit" :disabled="creer.isPending.value" class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60">
          {{ creer.isPending.value ? "Ajout..." : "Ajouter" }}
        </button>
      </div>
    </form>

    <BaseDataTable
      :colonnes="colonnes"
      :lignes="interlocuteurs ?? []"
      :chargement="isLoading"
      message-vide="Aucun interlocuteur pour le moment."
      @ligne-cliquee="ouvrirEdition"
    >
      <template #cell-role="{ valeur }">{{ libelleRole(valeur as string) }}</template>
      <template #cell-pourcentage_detention="{ valeur }">{{ valeur != null ? `${valeur} %` : "—" }}</template>
      <template #cell-actif="{ ligne }">
        <button
          v-if="aPermission('interlocuteur.modifier')"
          type="button"
          class="text-xs"
          :class="ligne.actif ? 'text-success hover:underline' : 'text-text-muted hover:underline'"
          @click.stop="basculerActif(ligne)"
        >
          {{ ligne.actif ? "Actif" : "Désactivé" }}
        </button>
        <StatutBadge v-else :libelle="ligne.actif ? 'Actif' : 'Désactivé'" :tonalite="ligne.actif ? 'succes' : 'neutre'" />
      </template>
    </BaseDataTable>

    <form
      v-if="interlocuteurEnEdition"
      class="space-y-4 rounded-lg border border-border bg-surface p-6"
      @submit.prevent="enregistrerEdition"
    >
      <h2 class="text-base font-semibold text-text">Modifier — {{ interlocuteurEnEdition.nom }}</h2>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Nom</label>
          <input v-model="edition.nom" required class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Rôle</label>
          <select v-model="edition.role" class="w-full rounded-md border border-border px-3 py-2 text-text">
            <option v-for="r in ROLES_INTERLOCUTEUR" :key="r.valeur" :value="r.valeur">{{ r.libelle }}</option>
          </select>
        </div>
      </div>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Fonction</label>
          <input v-model="edition.fonction" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div v-if="edition.role === 'associe'">
          <label class="mb-1 block text-sm font-medium text-text">% de détention</label>
          <input
            v-model="edition.pourcentage_detention"
            type="number"
            min="0"
            max="100"
            step="0.01"
            class="w-full rounded-md border border-border px-3 py-2 text-text"
          />
        </div>
      </div>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Email</label>
          <input v-model="edition.email" type="email" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Téléphone</label>
          <input v-model="edition.telephone" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
      </div>
      <div>
        <label class="mb-1 block text-sm font-medium text-text">Notes</label>
        <input v-model="edition.notes" class="w-full rounded-md border border-border px-3 py-2 text-text" />
      </div>
      <p v-if="erreurEdition" class="text-sm text-danger">{{ erreurEdition }}</p>
      <div class="flex justify-end gap-2">
        <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted" @click="interlocuteurEnEdition = null">
          Annuler
        </button>
        <button type="submit" :disabled="modifier.isPending.value" class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60">
          Enregistrer
        </button>
      </div>
    </form>
  </div>
</template>
