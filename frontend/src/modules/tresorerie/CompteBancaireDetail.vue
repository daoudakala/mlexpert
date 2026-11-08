<script setup lang="ts">
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useAuth } from "@/core/auth/useAuth";
import ConfirmDialog from "@/core/ui/ConfirmDialog.vue";
import { formaterMontant } from "@/core/ui/formatage";
import StatutBadge from "@/core/ui/StatutBadge.vue";
import { useCompteBancaire, useListeReleves, useMutationsComptesBancaires } from "./api";

const route = useRoute();
const router = useRouter();
const { contexteActif, aPermission } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const compteBancaireId = computed(() => route.params.id as string);

const { data: compte } = useCompteBancaire(entrepriseId, compteBancaireId);
const { data: releves, isLoading: chargementReleves } = useListeReleves(entrepriseId, compteBancaireId);
const { desactiver } = useMutationsComptesBancaires(entrepriseId);

const confirmationDesactivation = ref(false);

async function confirmerDesactivation(): Promise<void> {
  await desactiver.mutateAsync(compteBancaireId.value);
}
</script>

<template>
  <div v-if="compte" class="max-w-3xl space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-lg font-semibold text-text">{{ compte.libelle }}</h1>
      <StatutBadge
        :libelle="compte.actif ? 'Actif' : 'Désactivé'"
        :tonalite="compte.actif ? 'succes' : 'neutre'"
      />
    </div>

    <div class="grid grid-cols-2 gap-4 rounded-lg border border-border bg-surface p-6 text-sm">
      <div>
        <p class="text-text-muted">Banque</p>
        <p class="text-text">{{ compte.banque ?? "—" }}</p>
      </div>
      <div>
        <p class="text-text-muted">N° de compte</p>
        <p class="text-text">{{ compte.numero_compte ?? "—" }}</p>
      </div>
      <div>
        <p class="text-text-muted">IBAN</p>
        <p class="text-text">{{ compte.iban ?? "—" }}</p>
      </div>
      <div>
        <p class="text-text-muted">Solde initial</p>
        <p class="text-text">{{ formaterMontant(compte.solde_initial) }}</p>
      </div>
    </div>

    <div class="flex items-center justify-between rounded-lg border border-border bg-surface p-6">
      <div class="flex gap-2">
        <router-link
          v-if="aPermission('releve.consulter')"
          :to="{ name: 'tresorerie.rapprochement', params: { id: compteBancaireId } }"
          class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted"
        >
          Rapprochement
        </router-link>
      </div>
      <button
        v-if="compte.actif && aPermission('compte_bancaire.archiver')"
        type="button"
        class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted"
        @click="confirmationDesactivation = true"
      >
        Désactiver
      </button>
    </div>

    <div class="space-y-3">
      <div class="flex items-center justify-between">
        <h2 class="text-base font-semibold text-text">Relevés</h2>
        <router-link
          v-if="aPermission('releve.creer')"
          :to="{ name: 'tresorerie.releve.nouveau', params: { id: compteBancaireId } }"
          class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover"
        >
          Nouveau relevé
        </router-link>
      </div>

      <div class="overflow-hidden rounded-lg border border-border bg-surface">
        <table class="w-full text-sm">
          <thead class="bg-surface-muted text-left text-xs font-medium uppercase text-text-muted">
            <tr>
              <th class="px-4 py-2">Période</th>
              <th class="px-4 py-2">Solde début</th>
              <th class="px-4 py-2">Solde fin</th>
              <th class="px-4 py-2">Référence</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            <tr v-if="chargementReleves">
              <td colspan="4" class="px-4 py-6 text-center text-text-muted">Chargement...</td>
            </tr>
            <tr v-else-if="!releves || releves.length === 0">
              <td colspan="4" class="px-4 py-6 text-center text-text-muted">Aucun relevé pour le moment.</td>
            </tr>
            <tr
              v-for="r in releves"
              v-else
              :key="r.id"
              class="cursor-pointer hover:bg-surface-muted"
              @click="router.push({ name: 'tresorerie.releve', params: { releveId: r.id } })"
            >
              <td class="px-4 py-2 text-text">{{ r.date_debut }} → {{ r.date_fin }}</td>
              <td class="px-4 py-2 text-text">{{ formaterMontant(r.solde_debut) }}</td>
              <td class="px-4 py-2 text-text">{{ formaterMontant(r.solde_fin) }}</td>
              <td class="px-4 py-2 text-text">{{ r.reference ?? "—" }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <ConfirmDialog
      v-model:ouvert="confirmationDesactivation"
      titre="Désactiver ce compte bancaire ?"
      message="Il n'apparaîtra plus dans les listes actives, mais reste consultable."
      libelle-confirmer="Désactiver"
      dangereux
      @confirmer="confirmerDesactivation"
    />
  </div>
</template>
