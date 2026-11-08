<script setup lang="ts">
/**
 * Affectations de rôle sur l'entreprise active — `droits.administrer`
 * pour inviter/retirer, `droits.consulter` pour la liste (voir
 * router.py). Depuis l'Étape 6 (auto-gestion des entreprises), les deux
 * actions sont scopées à l'entreprise : plus besoin d'être administrateur
 * de plateforme, ni de connaître l'identifiant technique de la personne
 * à inviter (remplacé par une invitation par email, qui crée le compte
 * si besoin).
 */
import { computed, reactive, ref } from "vue";

import { useAuth } from "@/core/auth/useAuth";
import { messageErreur } from "@/core/api/erreurs";
import BaseDataTable, { type ColonneTable } from "@/core/ui/BaseDataTable.vue";
import BaseFormulaire from "@/core/ui/BaseFormulaire.vue";
import ConfirmDialog from "@/core/ui/ConfirmDialog.vue";
import StatutBadge from "@/core/ui/StatutBadge.vue";
import { useAffectations, useMutationsAffectations, useRolesDisponibles } from "./api";
import type { Affectation, InvitationResultat } from "./types";

const { contexteActif, aPermission } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const { data: affectations, isLoading } = useAffectations(entrepriseId);
const { data: rolesDisponibles } = useRolesDisponibles(entrepriseId);
const { retirer, inviter } = useMutationsAffectations(entrepriseId);

const colonnes: ColonneTable<Affectation>[] = [
  { cle: "utilisateur_id", libelle: "Utilisateur (id)" },
  { cle: "role_id", libelle: "Rôle" },
  { cle: "actif", libelle: "Statut" },
];

function libelleRole(roleId: string): string {
  return rolesDisponibles.value?.find((r) => r.id === roleId)?.libelle ?? roleId;
}

// --- Invitation (self-service, Étape 6) -------------------------------------

const afficherFormulaireInvitation = ref(false);
const formulaire = reactive({
  email: "",
  nom: "",
  prenom: "",
  telephone: "",
  role_id: "",
});
const erreurInvitation = ref<string | null>(null);
// Résultat affiché une seule fois : le mot de passe temporaire n'est pas
// récupérable après coup (voir InvitationResultat côté backend).
const resultatInvitation = ref<InvitationResultat | null>(null);

async function soumettreInvitation(): Promise<void> {
  erreurInvitation.value = null;
  try {
    const resultat = await inviter.mutateAsync({
      email: formulaire.email,
      nom: formulaire.nom,
      prenom: formulaire.prenom,
      telephone: formulaire.telephone || null,
      role_id: formulaire.role_id,
    });
    formulaire.email = "";
    formulaire.nom = "";
    formulaire.prenom = "";
    formulaire.telephone = "";
    formulaire.role_id = "";
    afficherFormulaireInvitation.value = false;
    resultatInvitation.value = resultat;
  } catch (e) {
    erreurInvitation.value = messageErreur(e);
  }
}

// --- Retrait -----------------------------------------------------------------

const affectationCible = ref<Affectation | null>(null);
const confirmationRetrait = ref(false);

function demanderRetrait(a: Affectation): void {
  affectationCible.value = a;
  confirmationRetrait.value = true;
}

async function confirmerRetrait(): Promise<void> {
  if (affectationCible.value) await retirer.mutateAsync(affectationCible.value.id);
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-lg font-semibold text-text">Affectations</h1>
      <button
        v-if="aPermission('droits.administrer')"
        type="button"
        class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover"
        @click="afficherFormulaireInvitation = !afficherFormulaireInvitation"
      >
        Inviter un utilisateur
      </button>
    </div>

    <div
      v-if="resultatInvitation"
      class="space-y-2 rounded-lg border border-border bg-surface-muted p-4"
    >
      <p class="text-sm font-medium text-text">
        {{ resultatInvitation.compte_existant ? "Compte existant réutilisé" : "Compte créé" }}
        — {{ resultatInvitation.email }}
      </p>
      <p v-if="resultatInvitation.mot_de_passe_temporaire" class="text-sm text-text">
        Mot de passe temporaire (à transmettre vous-même, il ne sera plus affiché ensuite) :
        <code class="rounded bg-surface px-2 py-1 font-mono text-sm">{{
          resultatInvitation.mot_de_passe_temporaire
        }}</code>
      </p>
      <button
        type="button"
        class="text-xs text-text-muted hover:underline"
        @click="resultatInvitation = null"
      >
        Fermer
      </button>
    </div>

    <BaseFormulaire
      v-if="afficherFormulaireInvitation"
      titre="Inviter un collaborateur ou un client"
      libelle-enregistrer="Inviter"
      :erreur="erreurInvitation"
      :en-envoi="inviter.isPending.value"
      @soumettre="soumettreInvitation"
      @annuler="afficherFormulaireInvitation = false"
    >
      <p class="text-sm text-text-muted">
        Si cet email correspond déjà à un compte (un collaborateur d'une autre entreprise, par
        exemple), il est simplement affecté à celle-ci — nom/prénom/téléphone sont alors ignorés.
      </p>
      <div>
        <label class="mb-1 block text-sm font-medium text-text">Email</label>
        <input
          v-model="formulaire.email"
          type="email"
          required
          class="w-full rounded-md border border-border px-3 py-2 text-text"
        />
      </div>
      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Nom</label>
          <input v-model="formulaire.nom" required class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Prénom</label>
          <input v-model="formulaire.prenom" required class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
      </div>
      <div>
        <label class="mb-1 block text-sm font-medium text-text">Téléphone (optionnel)</label>
        <input v-model="formulaire.telephone" class="w-full rounded-md border border-border px-3 py-2 text-text" />
      </div>
      <div>
        <label class="mb-1 block text-sm font-medium text-text">Rôle</label>
        <select v-model="formulaire.role_id" required class="w-full rounded-md border border-border px-3 py-2 text-text">
          <option value="" disabled>— Choisir —</option>
          <option v-for="r in rolesDisponibles ?? []" :key="r.id" :value="r.id">{{ r.libelle }}</option>
        </select>
      </div>
    </BaseFormulaire>

    <BaseDataTable :colonnes="colonnes" :lignes="affectations ?? []" :chargement="isLoading" message-vide="Aucune affectation.">
      <template #cell-role_id="{ valeur }">
        {{ libelleRole(valeur as string) }}
      </template>
      <template #cell-actif="{ ligne, valeur }">
        <div class="flex items-center justify-between gap-2">
          <StatutBadge :libelle="valeur ? 'Active' : 'Inactive'" :tonalite="valeur ? 'succes' : 'neutre'" />
          <button
            v-if="aPermission('droits.administrer')"
            type="button"
            class="text-xs text-danger hover:underline"
            @click.stop="demanderRetrait(ligne)"
          >
            Retirer
          </button>
        </div>
      </template>
    </BaseDataTable>

    <ConfirmDialog
      v-model:ouvert="confirmationRetrait"
      titre="Retirer cette affectation ?"
      message="L'utilisateur perdra immédiatement l'accès à cette entreprise via ce rôle. Il pourra être ré-invité plus tard si besoin."
      libelle-confirmer="Retirer"
      dangereux
      @confirmer="confirmerRetrait"
    />
  </div>
</template>