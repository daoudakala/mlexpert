<script setup lang="ts">
/**
 * Administration de plateforme : rôles et permissions. `GET /droits/roles`
 * renvoie désormais le jeu de permissions de chaque rôle
 * (RoleAvecPermissions) et `PATCH /droits/roles/{id}` permet de le modifier
 * après coup (voir ServiceDroits.modifier_role côté backend) — jusqu'ici un
 * rôle créé restait figé avec son jeu de permissions initial.
 *
 * Les permissions se résolvent par RÔLE, jamais par utilisateur individuel
 * (pas de table d'association directe utilisateur-permission) : pour
 * ajouter ou retirer un droit à un utilisateur, on édite le rôle qui lui
 * est affecté (ou on lui affecte un rôle différent depuis la page
 * Affectations) — un changement ici s'applique à tous les utilisateurs
 * qui partagent ce rôle, dès leur prochaine connexion/rafraîchissement de
 * contexte.
 */
import { reactive, ref } from "vue";

import { messageErreur } from "@/core/api/erreurs";
import BaseDataTable, { type ColonneTable } from "@/core/ui/BaseDataTable.vue";
import BaseFormulaire from "@/core/ui/BaseFormulaire.vue";
import StatutBadge from "@/core/ui/StatutBadge.vue";
import { useMutationsRoles, usePermissions, useRoles } from "./api";
import type { RoleAvecPermissions } from "./types";

const { data: roles, isLoading } = useRoles();
const { data: permissions } = usePermissions();
const { creer, modifier } = useMutationsRoles();

const colonnes: ColonneTable<RoleAvecPermissions>[] = [
  { cle: "code", libelle: "Code" },
  { cle: "libelle", libelle: "Libellé" },
  { cle: "est_role_plateforme", libelle: "Portée" },
  { cle: "permissions", libelle: "Permissions" },
];

// --- Création ----------------------------------------------------------

const afficherFormulaireCreation = ref(false);
const formulaire = reactive({
  code: "",
  libelle: "",
  est_role_plateforme: false,
  codesPermissionsSelectionnes: [] as string[],
});
const erreurCreation = ref<string | null>(null);

async function soumettreCreation(): Promise<void> {
  erreurCreation.value = null;
  try {
    await creer.mutateAsync({
      code: formulaire.code,
      libelle: formulaire.libelle,
      est_role_plateforme: formulaire.est_role_plateforme,
      codes_permissions: formulaire.codesPermissionsSelectionnes,
    });
    formulaire.code = "";
    formulaire.libelle = "";
    formulaire.est_role_plateforme = false;
    formulaire.codesPermissionsSelectionnes = [];
    afficherFormulaireCreation.value = false;
  } catch (e) {
    erreurCreation.value = messageErreur(e);
  }
}

// --- Édition (code, libellé, jeu de permissions) ------------------------
// `est_role_plateforme` n'est volontairement pas modifiable ici (voir la
// docstring de ServiceDroits.modifier_role côté backend).

const roleEnEdition = ref<RoleAvecPermissions | null>(null);
const formulaireEdition = reactive({
  code: "",
  libelle: "",
  codesPermissionsSelectionnes: [] as string[],
});
const erreurEdition = ref<string | null>(null);

function ouvrirEdition(role: RoleAvecPermissions): void {
  roleEnEdition.value = role;
  formulaireEdition.code = role.code;
  formulaireEdition.libelle = role.libelle;
  formulaireEdition.codesPermissionsSelectionnes = role.permissions.map((p) => p.code);
  erreurEdition.value = null;
  afficherFormulaireCreation.value = false;
}

async function soumettreEdition(): Promise<void> {
  if (!roleEnEdition.value) return;
  erreurEdition.value = null;
  try {
    await modifier.mutateAsync({
      id: roleEnEdition.value.id,
      donnees: {
        code: formulaireEdition.code,
        libelle: formulaireEdition.libelle,
        codes_permissions: formulaireEdition.codesPermissionsSelectionnes,
      },
    });
    roleEnEdition.value = null;
  } catch (e) {
    erreurEdition.value = messageErreur(e);
  }
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-lg font-semibold text-text">Rôles &amp; permissions</h1>
      <button
        type="button"
        class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover"
        @click="
          afficherFormulaireCreation = !afficherFormulaireCreation;
          roleEnEdition = null;
        "
      >
        Nouveau rôle
      </button>
    </div>

    <BaseFormulaire
      v-if="afficherFormulaireCreation"
      titre="Créer un rôle"
      libelle-enregistrer="Créer"
      :erreur="erreurCreation"
      :en-envoi="creer.isPending.value"
      @soumettre="soumettreCreation"
      @annuler="afficherFormulaireCreation = false"
    >
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Code</label>
          <input v-model="formulaire.code" required minlength="2" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Libellé</label>
          <input v-model="formulaire.libelle" required minlength="2" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
      </div>
      <label class="flex items-center gap-2 text-sm text-text">
        <input v-model="formulaire.est_role_plateforme" type="checkbox" />
        Rôle de plateforme (ne peut pas être affecté sur une entreprise)
      </label>
      <div>
        <p class="mb-2 text-sm font-medium text-text">Permissions</p>
        <div class="grid max-h-64 grid-cols-2 gap-1 overflow-y-auto rounded-md border border-border p-3">
          <label v-for="p in permissions ?? []" :key="p.id" class="flex items-center gap-2 text-sm text-text">
            <input v-model="formulaire.codesPermissionsSelectionnes" type="checkbox" :value="p.code" />
            {{ p.libelle }}
          </label>
        </div>
      </div>
    </BaseFormulaire>

    <BaseFormulaire
      v-if="roleEnEdition"
      :titre="`Modifier le rôle « ${roleEnEdition.libelle} »`"
      libelle-enregistrer="Enregistrer"
      :erreur="erreurEdition"
      :en-envoi="modifier.isPending.value"
      @soumettre="soumettreEdition"
      @annuler="roleEnEdition = null"
    >
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Code</label>
          <input v-model="formulaireEdition.code" required minlength="2" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Libellé</label>
          <input v-model="formulaireEdition.libelle" required minlength="2" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
      </div>
      <p v-if="roleEnEdition.est_role_plateforme" class="text-xs text-text-muted">
        Rôle de plateforme — la portée (plateforme/entreprise) ne se change pas après création.
      </p>
      <div>
        <p class="mb-2 text-sm font-medium text-text">Permissions</p>
        <div class="grid max-h-64 grid-cols-2 gap-1 overflow-y-auto rounded-md border border-border p-3">
          <label v-for="p in permissions ?? []" :key="p.id" class="flex items-center gap-2 text-sm text-text">
            <input v-model="formulaireEdition.codesPermissionsSelectionnes" type="checkbox" :value="p.code" />
            {{ p.libelle }}
          </label>
        </div>
      </div>
    </BaseFormulaire>

    <BaseDataTable :colonnes="colonnes" :lignes="roles ?? []" :chargement="isLoading" message-vide="Aucun rôle.">
      <template #cell-est_role_plateforme="{ valeur }">
        <StatutBadge
          :libelle="valeur ? 'Plateforme' : 'Entreprise'"
          :tonalite="valeur ? 'info' : 'neutre'"
        />
      </template>
      <template #cell-permissions="{ ligne }">
        <div class="flex flex-wrap items-center gap-2">
          <span class="text-xs text-text-muted">{{ ligne.permissions.length }} permission(s)</span>
          <button type="button" class="text-xs text-primary hover:underline" @click="ouvrirEdition(ligne)">
            Modifier
          </button>
        </div>
      </template>
    </BaseDataTable>
  </div>
</template>