<script setup lang="ts">
/**
 * Self-service, accessible à tout utilisateur connecté (pas de
 * meta.permission sur cette route) : modifier ses propres nom/prénom/
 * téléphone, et changer son mot de passe.
 */
import { reactive, ref, watch } from "vue";

import { useAuth } from "@/core/auth/useAuth";
import { messageErreur } from "@/core/api/erreurs";
import BaseFormulaire from "@/core/ui/BaseFormulaire.vue";
import { useMutationsMonProfil } from "./api";

const { utilisateur } = useAuth();
const { modifier, changerMotDePasse } = useMutationsMonProfil();

const formulaireProfil = reactive({ nom: "", prenom: "", telephone: "" });
watch(
  utilisateur,
  (u) => {
    if (!u) return;
    formulaireProfil.nom = u.nom;
    formulaireProfil.prenom = u.prenom;
    formulaireProfil.telephone = u.telephone ?? "";
  },
  { immediate: true },
);

const erreurProfil = ref<string | null>(null);
const succesProfil = ref(false);

async function soumettreProfil(): Promise<void> {
  erreurProfil.value = null;
  succesProfil.value = false;
  try {
    const resultat = await modifier.mutateAsync({
      nom: formulaireProfil.nom,
      prenom: formulaireProfil.prenom,
      telephone: formulaireProfil.telephone || null,
    });
    if (utilisateur.value) {
      utilisateur.value = { ...utilisateur.value, ...resultat };
    }
    succesProfil.value = true;
  } catch (e) {
    erreurProfil.value = messageErreur(e);
  }
}

const formulaireMotDePasse = reactive({ ancien_mot_de_passe: "", nouveau_mot_de_passe: "" });
const erreurMotDePasse = ref<string | null>(null);
const succesMotDePasse = ref(false);

async function soumettreMotDePasse(): Promise<void> {
  erreurMotDePasse.value = null;
  succesMotDePasse.value = false;
  try {
    await changerMotDePasse.mutateAsync({ ...formulaireMotDePasse });
    formulaireMotDePasse.ancien_mot_de_passe = "";
    formulaireMotDePasse.nouveau_mot_de_passe = "";
    succesMotDePasse.value = true;
  } catch (e) {
    erreurMotDePasse.value = messageErreur(e);
  }
}
</script>

<template>
  <div class="max-w-2xl space-y-6">
    <h1 class="text-lg font-semibold text-text">Mon profil</h1>

    <BaseFormulaire
      titre="Informations personnelles"
      :erreur="erreurProfil"
      :en-envoi="modifier.isPending.value"
      @soumettre="soumettreProfil"
      @annuler="() => {}"
    >
      <p v-if="succesProfil" class="text-sm text-success">Profil mis à jour.</p>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Prénom</label>
          <input v-model="formulaireProfil.prenom" required class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Nom</label>
          <input v-model="formulaireProfil.nom" required class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
      </div>
      <div>
        <label class="mb-1 block text-sm font-medium text-text">Téléphone</label>
        <input v-model="formulaireProfil.telephone" class="w-full rounded-md border border-border px-3 py-2 text-text" />
      </div>
      <div>
        <label class="mb-1 block text-sm font-medium text-text">Email</label>
        <input :value="utilisateur?.email" disabled class="w-full rounded-md border border-border bg-surface-muted px-3 py-2 text-text-muted" />
      </div>
    </BaseFormulaire>

    <BaseFormulaire
      titre="Changer de mot de passe"
      libelle-enregistrer="Changer le mot de passe"
      :erreur="erreurMotDePasse"
      :en-envoi="changerMotDePasse.isPending.value"
      @soumettre="soumettreMotDePasse"
      @annuler="() => {}"
    >
      <p v-if="succesMotDePasse" class="text-sm text-success">Mot de passe changé.</p>
      <div>
        <label class="mb-1 block text-sm font-medium text-text">Mot de passe actuel</label>
        <input
          v-model="formulaireMotDePasse.ancien_mot_de_passe"
          type="password"
          required
          class="w-full rounded-md border border-border px-3 py-2 text-text"
        />
      </div>
      <div>
        <label class="mb-1 block text-sm font-medium text-text">Nouveau mot de passe</label>
        <input
          v-model="formulaireMotDePasse.nouveau_mot_de_passe"
          type="password"
          required
          minlength="8"
          class="w-full rounded-md border border-border px-3 py-2 text-text"
        />
      </div>
    </BaseFormulaire>
  </div>
</template>
