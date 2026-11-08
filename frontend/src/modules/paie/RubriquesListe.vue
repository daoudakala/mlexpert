<script setup lang="ts">
/**
 * Référentiel des rubriques de paie (salaire de base, prime, retenue
 * CNPS...). Pas de modification du libellé/type une fois créée (pas de
 * route PATCH côté backend) : seuls le compte comptable et la
 * désactivation évoluent après création.
 */
import { computed, reactive, ref } from "vue";

import { useAuth } from "@/core/auth/useAuth";
import { messageErreur } from "@/core/api/erreurs";
import { useComptesEntreprise } from "@/modules/comptabilite/api";
import BaseDataTable, { type ColonneTable } from "@/core/ui/BaseDataTable.vue";
import BaseFormulaire from "@/core/ui/BaseFormulaire.vue";
import StatutBadge from "@/core/ui/StatutBadge.vue";
import { useListeRubriques, useMutationsRubriques } from "./api";
import type { RubriquePaie } from "./types";

const { contexteActif, aPermission } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const { data: rubriques, isLoading } = useListeRubriques(entrepriseId);
const { data: comptes } = useComptesEntreprise(entrepriseId);
const { creer, definirCompteComptable, desactiver } = useMutationsRubriques(entrepriseId);

const colonnes: ColonneTable<RubriquePaie>[] = [
  { cle: "code", libelle: "Code" },
  { cle: "libelle", libelle: "Libellé" },
  { cle: "type_rubrique", libelle: "Type" },
  { cle: "compte_comptable_id", libelle: "Compte comptable" },
  { cle: "actif", libelle: "Statut" },
];

function libelleCompte(compteId: string | null): string {
  if (!compteId) return "— non affecté —";
  const compte = comptes.value?.find((c) => c.id === compteId);
  return compte ? `${compte.numero} — ${compte.libelle}` : compteId;
}

const afficherFormulaireCreation = ref(false);
const formulaire = reactive({ code: "", libelle: "", type_rubrique: "gain" as "gain" | "retenue" });
const erreurCreation = ref<string | null>(null);

async function soumettreCreation(): Promise<void> {
  erreurCreation.value = null;
  try {
    await creer.mutateAsync({
      code: formulaire.code,
      libelle: formulaire.libelle,
      type_rubrique: formulaire.type_rubrique,
    });
    formulaire.code = "";
    formulaire.libelle = "";
    formulaire.type_rubrique = "gain";
    afficherFormulaireCreation.value = false;
  } catch (e) {
    erreurCreation.value = messageErreur(e);
  }
}

const rubriqueEnEditionCompte = ref<RubriquePaie | null>(null);
const compteChoisi = ref("");

function ouvrirSelectionCompte(r: RubriquePaie): void {
  rubriqueEnEditionCompte.value = r;
  compteChoisi.value = r.compte_comptable_id ?? "";
}

async function enregistrerCompteComptable(): Promise<void> {
  if (!rubriqueEnEditionCompte.value || !compteChoisi.value) return;
  await definirCompteComptable.mutateAsync({
    id: rubriqueEnEditionCompte.value.id,
    compteComptableId: compteChoisi.value,
  });
  rubriqueEnEditionCompte.value = null;
}

async function desactiverRubrique(r: RubriquePaie): Promise<void> {
  await desactiver.mutateAsync(r.id);
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-lg font-semibold text-text">Rubriques de paie</h1>
      <button
        v-if="aPermission('rubrique_paie.creer')"
        type="button"
        class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover"
        @click="afficherFormulaireCreation = !afficherFormulaireCreation"
      >
        Nouvelle rubrique
      </button>
    </div>

    <BaseFormulaire
      v-if="afficherFormulaireCreation"
      titre="Créer une rubrique"
      libelle-enregistrer="Créer"
      :erreur="erreurCreation"
      :en-envoi="creer.isPending.value"
      @soumettre="soumettreCreation"
      @annuler="afficherFormulaireCreation = false"
    >
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Code</label>
          <input v-model="formulaire.code" required maxlength="30" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Libellé</label>
          <input v-model="formulaire.libelle" required class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
      </div>
      <div>
        <label class="mb-1 block text-sm font-medium text-text">Type</label>
        <select v-model="formulaire.type_rubrique" class="w-full rounded-md border border-border px-3 py-2 text-text">
          <option value="gain">Gain</option>
          <option value="retenue">Retenue</option>
        </select>
      </div>
    </BaseFormulaire>

    <BaseDataTable :colonnes="colonnes" :lignes="rubriques ?? []" :chargement="isLoading" message-vide="Aucune rubrique.">
      <template #cell-type_rubrique="{ valeur }">
        <StatutBadge
          :libelle="valeur === 'gain' ? 'Gain' : 'Retenue'"
          :tonalite="valeur === 'gain' ? 'succes' : 'avertissement'"
        />
      </template>
      <template #cell-compte_comptable_id="{ ligne, valeur }">
        <button type="button" class="text-left text-sm text-primary hover:underline" @click="ouvrirSelectionCompte(ligne)">
          {{ libelleCompte(valeur as string | null) }}
        </button>
      </template>
      <template #cell-actif="{ ligne, valeur }">
        <div class="flex items-center justify-between gap-2">
          <StatutBadge :libelle="valeur ? 'Active' : 'Désactivée'" :tonalite="valeur ? 'succes' : 'neutre'" />
          <button
            v-if="valeur && aPermission('rubrique_paie.archiver')"
            type="button"
            class="text-xs text-danger hover:underline"
            @click.stop="desactiverRubrique(ligne)"
          >
            Désactiver
          </button>
        </div>
      </template>
    </BaseDataTable>

    <div
      v-if="rubriqueEnEditionCompte"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      @click.self="rubriqueEnEditionCompte = null"
    >
      <div class="w-full max-w-sm rounded-lg bg-surface p-6 shadow-lg">
        <h2 class="text-base font-semibold text-text">
          Compte comptable — {{ rubriqueEnEditionCompte.libelle }}
        </h2>
        <select v-model="compteChoisi" class="mt-3 w-full rounded-md border border-border px-3 py-2 text-sm text-text">
          <option value="" disabled>— Choisir —</option>
          <option v-for="c in comptes" :key="c.id" :value="c.id">{{ c.numero }} — {{ c.libelle }}</option>
        </select>
        <div class="mt-4 flex justify-end gap-2">
          <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted" @click="rubriqueEnEditionCompte = null">
            Annuler
          </button>
          <button
            type="button"
            :disabled="!compteChoisi || definirCompteComptable.isPending.value"
            class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60"
            @click="enregistrerCompteComptable"
          >
            Enregistrer
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
