<script setup lang="ts">
/**
 * Administration des comptes utilisateurs — réservée à l'administrateur
 * plateforme (meta.adminPlateforme sur la route, voir router/index.ts).
 * Pas de modification des informations d'un autre utilisateur ici (seul le
 * self-service via /moi le permet) : uniquement créer, désactiver/
 * réactiver, et réinitialiser un mot de passe oublié.
 */
import { ref } from "vue";

import { messageErreur } from "@/core/api/erreurs";
import BaseDataTable, { type ColonneTable } from "@/core/ui/BaseDataTable.vue";
import BaseFormulaire from "@/core/ui/BaseFormulaire.vue";
import ConfirmDialog from "@/core/ui/ConfirmDialog.vue";
import StatutBadge from "@/core/ui/StatutBadge.vue";
import { useListeUtilisateurs, useMutationsUtilisateurs } from "./api";
import type { Utilisateur } from "./types";

const { data: utilisateurs, isLoading } = useListeUtilisateurs();
const { creer, desactiver, reactiver, reinitialiserMotDePasse } = useMutationsUtilisateurs();

const colonnes: ColonneTable<Utilisateur>[] = [
  { cle: "prenom", libelle: "Prénom" },
  { cle: "nom", libelle: "Nom" },
  { cle: "email", libelle: "Email" },
  { cle: "actif", libelle: "Statut" },
];

// --- Création ----------------------------------------------------------

const afficherFormulaireCreation = ref(false);
const formulaire = ref({ email: "", mot_de_passe: "", nom: "", prenom: "", telephone: "" });
const erreurCreation = ref<string | null>(null);

async function soumettreCreation(): Promise<void> {
  erreurCreation.value = null;
  try {
    await creer.mutateAsync({
      email: formulaire.value.email,
      mot_de_passe: formulaire.value.mot_de_passe,
      nom: formulaire.value.nom,
      prenom: formulaire.value.prenom,
      telephone: formulaire.value.telephone || null,
    });
    formulaire.value = { email: "", mot_de_passe: "", nom: "", prenom: "", telephone: "" };
    afficherFormulaireCreation.value = false;
  } catch (e) {
    erreurCreation.value = messageErreur(e);
  }
}

// --- Activation / désactivation -----------------------------------------

const utilisateurCible = ref<Utilisateur | null>(null);
const confirmationDesactivation = ref(false);

function demanderDesactivation(u: Utilisateur): void {
  utilisateurCible.value = u;
  confirmationDesactivation.value = true;
}

async function confirmerDesactivation(): Promise<void> {
  if (utilisateurCible.value) await desactiver.mutateAsync(utilisateurCible.value.id);
}

async function reactiverUtilisateur(u: Utilisateur): Promise<void> {
  await reactiver.mutateAsync(u.id);
}

// --- Réinitialisation du mot de passe ------------------------------------

const utilisateurReinit = ref<Utilisateur | null>(null);
const nouveauMotDePasse = ref("");
const erreurReinit = ref<string | null>(null);
const succesReinit = ref(false);

function demanderReinitialisation(u: Utilisateur): void {
  utilisateurReinit.value = u;
  nouveauMotDePasse.value = "";
  erreurReinit.value = null;
  succesReinit.value = false;
}

async function confirmerReinitialisation(): Promise<void> {
  if (!utilisateurReinit.value) return;
  erreurReinit.value = null;
  try {
    await reinitialiserMotDePasse.mutateAsync({
      id: utilisateurReinit.value.id,
      donnees: { nouveau_mot_de_passe: nouveauMotDePasse.value },
    });
    succesReinit.value = true;
  } catch (e) {
    erreurReinit.value = messageErreur(e);
  }
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-lg font-semibold text-text">Utilisateurs</h1>
      <button
        type="button"
        class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover"
        @click="afficherFormulaireCreation = !afficherFormulaireCreation"
      >
        Nouvel utilisateur
      </button>
    </div>

    <BaseFormulaire
      v-if="afficherFormulaireCreation"
      titre="Créer un utilisateur"
      libelle-enregistrer="Créer"
      :erreur="erreurCreation"
      :en-envoi="creer.isPending.value"
      @soumettre="soumettreCreation"
      @annuler="afficherFormulaireCreation = false"
    >
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
        <label class="mb-1 block text-sm font-medium text-text">Email</label>
        <input v-model="formulaire.email" type="email" required class="w-full rounded-md border border-border px-3 py-2 text-text" />
      </div>
      <div>
        <label class="mb-1 block text-sm font-medium text-text">Mot de passe initial</label>
        <input
          v-model="formulaire.mot_de_passe"
          type="password"
          required
          minlength="8"
          class="w-full rounded-md border border-border px-3 py-2 text-text"
        />
      </div>
      <div>
        <label class="mb-1 block text-sm font-medium text-text">Téléphone</label>
        <input v-model="formulaire.telephone" class="w-full rounded-md border border-border px-3 py-2 text-text" />
      </div>
    </BaseFormulaire>

    <BaseDataTable :colonnes="colonnes" :lignes="utilisateurs ?? []" :chargement="isLoading" message-vide="Aucun utilisateur.">
      <template #cell-actif="{ ligne }">
        <StatutBadge :libelle="ligne.actif ? 'Actif' : 'Désactivé'" :tonalite="ligne.actif ? 'succes' : 'neutre'" />
      </template>
      <template #cell-email="{ ligne }">
        <div class="flex items-center justify-between gap-2">
          <span class="text-text">{{ ligne.email }}</span>
          <div class="flex gap-2">
            <button type="button" class="text-xs text-primary hover:underline" @click.stop="demanderReinitialisation(ligne)">
              Réinitialiser le mot de passe
            </button>
            <button
              v-if="ligne.actif"
              type="button"
              class="text-xs text-danger hover:underline"
              @click.stop="demanderDesactivation(ligne)"
            >
              Désactiver
            </button>
            <button v-else type="button" class="text-xs text-primary hover:underline" @click.stop="reactiverUtilisateur(ligne)">
              Réactiver
            </button>
          </div>
        </div>
      </template>
    </BaseDataTable>

    <ConfirmDialog
      v-model:ouvert="confirmationDesactivation"
      titre="Désactiver ce compte ?"
      :message="`${utilisateurCible?.prenom} ${utilisateurCible?.nom} ne pourra plus se connecter, et ses sessions actives seront révoquées immédiatement.`"
      libelle-confirmer="Désactiver"
      dangereux
      @confirmer="confirmerDesactivation"
    />

    <div
      v-if="utilisateurReinit"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      @click.self="utilisateurReinit = null"
    >
      <div class="w-full max-w-sm rounded-lg bg-surface p-6 shadow-lg">
        <h2 class="text-base font-semibold text-text">
          Réinitialiser le mot de passe de {{ utilisateurReinit.prenom }} {{ utilisateurReinit.nom }}
        </h2>
        <p v-if="succesReinit" class="mt-2 text-sm text-success">Mot de passe réinitialisé.</p>
        <template v-else>
          <input
            v-model="nouveauMotDePasse"
            type="password"
            minlength="8"
            placeholder="Nouveau mot de passe"
            class="mt-3 w-full rounded-md border border-border px-3 py-2 text-text"
          />
          <p v-if="erreurReinit" class="mt-2 text-sm text-danger">{{ erreurReinit }}</p>
        </template>
        <div class="mt-4 flex justify-end gap-2">
          <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted" @click="utilisateurReinit = null">
            Fermer
          </button>
          <button
            v-if="!succesReinit"
            type="button"
            :disabled="reinitialiserMotDePasse.isPending.value || nouveauMotDePasse.length < 8"
            class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60"
            @click="confirmerReinitialisation"
          >
            Réinitialiser
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
