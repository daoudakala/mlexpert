<script setup lang="ts">
/**
 * Création, édition d'un brouillon, et consultation d'un bulletin validé
 * (route unique .../bulletins/nouveau ou .../bulletins/:id) — même
 * convention que EcritureFormulaire.vue : un bulletin validé devient en
 * lecture seule (le backend refuse toute modification), avec les actions
 * Générer l'écriture quand il n'en a pas encore.
 */
import { computed, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useAuth } from "@/core/auth/useAuth";
import { messageErreur } from "@/core/api/erreurs";
import { useComptesEntreprise, useJournaux } from "@/modules/comptabilite/api";
import { useExercices } from "@/modules/exercices/api";
import BaseFormulaire from "@/core/ui/BaseFormulaire.vue";
import ConfirmDialog from "@/core/ui/ConfirmDialog.vue";
import { formaterMontant } from "@/core/ui/formatage";
import MontantInput from "@/core/ui/MontantInput.vue";
import StatutBadge from "@/core/ui/StatutBadge.vue";
import {
  useBulletin,
  useLignesBulletin,
  useListeEmployes,
  useListeRubriques,
  useMutationsBulletins,
} from "./api";

const route = useRoute();
const router = useRouter();
const { contexteActif } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const bulletinId = computed(() => (route.params.id as string) || null);
const enEdition = computed(() => bulletinId.value !== null);

const { data: bulletinExistant } = useBulletin(entrepriseId, bulletinId);
const { data: lignesExistantes } = useLignesBulletin(entrepriseId, bulletinId);
const estValide = computed(() => bulletinExistant.value?.statut === "valide");
const lectureSeule = computed(() => enEdition.value && estValide.value);

const { data: employes } = useListeEmployes(entrepriseId, computed(() => ({ actifsSeulement: true })));
const { data: exercices } = useExercices(entrepriseId);
const { data: rubriques } = useListeRubriques(entrepriseId);
const { data: journaux } = useJournaux(entrepriseId);
const { data: comptes } = useComptesEntreprise(entrepriseId);

const { creer, modifier, supprimer, valider, genererEcriture } = useMutationsBulletins(entrepriseId);

interface LigneFormulaire {
  rubrique_id: string;
  montant: number;
  libelle: string;
}

function ligneVide(): LigneFormulaire {
  return { rubrique_id: "", montant: 0, libelle: "" };
}

const formulaire = reactive({
  employe_id: "",
  exercice_id: "",
  periode_debut: "",
  periode_fin: "",
  lignes: [ligneVide()] as LigneFormulaire[],
});

watch(
  () => [bulletinExistant.value, lignesExistantes.value] as const,
  ([b, lignes]) => {
    if (!b) return;
    formulaire.employe_id = b.employe_id;
    formulaire.exercice_id = b.exercice_id;
    formulaire.periode_debut = b.periode_debut;
    formulaire.periode_fin = b.periode_fin;
    if (lignes) {
      formulaire.lignes = lignes.map((l) => ({
        rubrique_id: l.rubrique_id,
        montant: Number(l.montant),
        libelle: l.libelle ?? "",
      }));
    }
  },
  { immediate: true },
);

function libelleRubrique(rubriqueId: string): string {
  const r = rubriques.value?.find((x) => x.id === rubriqueId);
  return r ? `${r.libelle} (${r.type_rubrique === "gain" ? "gain" : "retenue"})` : rubriqueId;
}

function ajouterLigne(): void {
  formulaire.lignes.push(ligneVide());
}
function retirerLigne(index: number): void {
  formulaire.lignes.splice(index, 1);
}

function lignesSaisies() {
  return formulaire.lignes.map((l) => ({
    rubrique_id: l.rubrique_id,
    montant: l.montant,
    libelle: l.libelle || null,
  }));
}

const erreur = ref<string | null>(null);
const enEnvoi = computed(() => creer.isPending.value || modifier.isPending.value);

async function soumettre(): Promise<void> {
  erreur.value = null;
  try {
    if (enEdition.value) {
      await modifier.mutateAsync({ id: bulletinId.value!, donnees: { lignes: lignesSaisies() } });
    } else {
      const bulletin = await creer.mutateAsync({
        employe_id: formulaire.employe_id,
        exercice_id: formulaire.exercice_id,
        periode_debut: formulaire.periode_debut,
        periode_fin: formulaire.periode_fin,
        lignes: lignesSaisies(),
      });
      router.push({ name: "paie.bulletin", params: { id: bulletin.id } });
    }
  } catch (e) {
    erreur.value = messageErreur(e);
  }
}

const confirmationSuppression = ref(false);
async function confirmerSuppression(): Promise<void> {
  await supprimer.mutateAsync(bulletinId.value!);
  router.push({ name: "paie.bulletins" });
}

const erreurValidation = ref<string | null>(null);
async function validerBulletin(): Promise<void> {
  erreurValidation.value = null;
  try {
    await valider.mutateAsync(bulletinId.value!);
  } catch (e) {
    erreurValidation.value = messageErreur(e);
  }
}

const genererOuvert = ref(false);
const generation = reactive({ journal_id: "", compte_net_a_payer_id: "" });
const erreurGeneration = ref<string | null>(null);

async function soumettreGeneration(): Promise<void> {
  erreurGeneration.value = null;
  try {
    const ecriture = await genererEcriture.mutateAsync({
      id: bulletinId.value!,
      donnees: { ...generation },
    });
    genererOuvert.value = false;
    router.push({ name: "comptabilite.ecriture", params: { id: ecriture.id } });
  } catch (e) {
    erreurGeneration.value = messageErreur(e);
  }
}
</script>

<template>
  <div class="max-w-3xl space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-lg font-semibold text-text">
        {{ enEdition ? "Bulletin de paie" : "Nouveau bulletin" }}
      </h1>
      <StatutBadge
        v-if="enEdition"
        :libelle="estValide ? 'Validé' : 'Brouillon'"
        :tonalite="estValide ? 'succes' : 'avertissement'"
      />
    </div>

    <BaseFormulaire
      v-if="!lectureSeule"
      titre="Informations"
      :erreur="erreur"
      :en-envoi="enEnvoi"
      :libelle-enregistrer="enEdition ? 'Enregistrer les modifications' : 'Créer en brouillon'"
      @soumettre="soumettre"
      @annuler="router.push({ name: 'paie.bulletins' })"
    >
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Employé</label>
          <select v-model="formulaire.employe_id" required :disabled="enEdition" class="w-full rounded-md border border-border px-3 py-2 text-text disabled:opacity-60">
            <option value="" disabled>— Choisir —</option>
            <option v-for="e in employes ?? []" :key="e.id" :value="e.id">{{ e.prenom }} {{ e.nom }}</option>
          </select>
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Exercice</label>
          <select v-model="formulaire.exercice_id" required :disabled="enEdition" class="w-full rounded-md border border-border px-3 py-2 text-text disabled:opacity-60">
            <option value="" disabled>— Choisir —</option>
            <option v-for="ex in exercices ?? []" :key="ex.id" :value="ex.id">{{ ex.date_debut }} → {{ ex.date_fin }}</option>
          </select>
        </div>
      </div>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Période — début</label>
          <input v-model="formulaire.periode_debut" type="date" required :disabled="enEdition" class="w-full rounded-md border border-border px-3 py-2 text-text disabled:opacity-60" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Période — fin</label>
          <input v-model="formulaire.periode_fin" type="date" required :disabled="enEdition" class="w-full rounded-md border border-border px-3 py-2 text-text disabled:opacity-60" />
        </div>
      </div>

      <div class="space-y-3">
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-semibold text-text">Lignes</h3>
          <button type="button" class="text-sm text-primary hover:underline" @click="ajouterLigne">+ Ajouter une ligne</button>
        </div>

        <div v-for="(ligne, index) in formulaire.lignes" :key="index" class="grid grid-cols-12 items-end gap-2 rounded-md border border-border p-3">
          <div class="col-span-4">
            <label class="mb-1 block text-xs font-medium text-text-muted">Rubrique</label>
            <select v-model="ligne.rubrique_id" required class="w-full rounded-md border border-border px-2 py-1.5 text-sm text-text">
              <option value="" disabled>— Choisir —</option>
              <option v-for="r in rubriques ?? []" :key="r.id" :value="r.id">{{ r.libelle }} ({{ r.type_rubrique }})</option>
            </select>
          </div>
          <div class="col-span-4">
            <label class="mb-1 block text-xs font-medium text-text-muted">Libellé (optionnel)</label>
            <input v-model="ligne.libelle" class="w-full rounded-md border border-border px-2 py-1.5 text-sm text-text" />
          </div>
          <div class="col-span-3">
            <label class="mb-1 block text-xs font-medium text-text-muted">Montant</label>
            <MontantInput v-model="ligne.montant" required />
          </div>
          <div class="col-span-1">
            <button
              type="button"
              :disabled="formulaire.lignes.length <= 1"
              class="w-full rounded-md border border-border px-2 py-1.5 text-sm text-text hover:bg-surface-muted disabled:opacity-40"
              @click="retirerLigne(index)"
            >
              Retirer
            </button>
          </div>
        </div>
      </div>
    </BaseFormulaire>

    <div v-else class="space-y-4 rounded-lg border border-border bg-surface p-6 text-sm">
      <div class="grid grid-cols-2 gap-4">
        <div><p class="text-text-muted">Période</p><p class="text-text">{{ formulaire.periode_debut }} → {{ formulaire.periode_fin }}</p></div>
        <div><p class="text-text-muted">Employé</p><p class="text-text">{{ employes?.find((e) => e.id === formulaire.employe_id)?.prenom }} {{ employes?.find((e) => e.id === formulaire.employe_id)?.nom }}</p></div>
      </div>
      <div class="overflow-hidden rounded-lg border border-border">
        <table class="w-full text-sm">
          <thead class="bg-surface-muted text-left text-xs font-medium uppercase text-text-muted">
            <tr><th class="px-3 py-2">Rubrique</th><th class="px-3 py-2">Libellé</th><th class="px-3 py-2 text-right">Montant</th></tr>
          </thead>
          <tbody class="divide-y divide-border">
            <tr v-for="(l, i) in formulaire.lignes" :key="i">
              <td class="px-3 py-2 text-text">{{ libelleRubrique(l.rubrique_id) }}</td>
              <td class="px-3 py-2 text-text">{{ l.libelle || "—" }}</td>
              <td class="px-3 py-2 text-right text-text">{{ formaterMontant(l.montant) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <template v-if="enEdition && bulletinExistant">
      <div class="grid grid-cols-3 gap-4 rounded-lg border border-border bg-surface p-6 text-sm">
        <div><p class="text-text-muted">Salaire brut</p><p class="text-text">{{ formaterMontant(bulletinExistant.salaire_brut) }}</p></div>
        <div><p class="text-text-muted">Total retenues</p><p class="text-text">{{ formaterMontant(bulletinExistant.total_retenues) }}</p></div>
        <div><p class="text-text-muted">Net à payer</p><p class="font-medium text-text">{{ formaterMontant(bulletinExistant.net_a_payer) }}</p></div>
      </div>

      <div v-if="!estValide" class="flex items-center justify-between rounded-lg border border-border bg-surface p-6">
        <div>
          <p class="text-sm font-medium text-text">Validation</p>
          <p class="text-sm text-text-muted">Une fois validé, le bulletin ne peut plus être modifié ni supprimé.</p>
          <p v-if="erreurValidation" class="text-sm text-danger">{{ erreurValidation }}</p>
        </div>
        <div class="flex gap-2">
          <button type="button" class="rounded-md border border-danger px-3 py-1.5 text-sm text-danger hover:bg-danger/10" @click="confirmationSuppression = true">
            Supprimer
          </button>
          <button type="button" :disabled="valider.isPending.value" class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60" @click="validerBulletin">
            Valider
          </button>
        </div>
      </div>

      <div v-else-if="!bulletinExistant.ecriture_id" class="flex items-center justify-between rounded-lg border border-border bg-surface p-6">
        <div>
          <p class="text-sm font-medium text-text">Comptabilisation</p>
          <p class="text-sm text-text-muted">Génère l'écriture de paie (une ligne par rubrique, plus le net à payer).</p>
        </div>
        <button type="button" class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover" @click="genererOuvert = true">
          Générer l'écriture
        </button>
      </div>

      <div v-else class="rounded-lg border border-border bg-surface p-6 text-sm">
        <p class="text-text-muted">Écriture générée.</p>
        <router-link :to="{ name: 'comptabilite.ecriture', params: { id: bulletinExistant.ecriture_id } }" class="text-primary hover:underline">
          Voir l'écriture
        </router-link>
      </div>
    </template>

    <ConfirmDialog
      v-model:ouvert="confirmationSuppression"
      titre="Supprimer ce brouillon ?"
      message="Cette action est irréversible."
      libelle-confirmer="Supprimer"
      dangereux
      @confirmer="confirmerSuppression"
    />

    <div v-if="genererOuvert" class="rounded-lg border border-border bg-surface p-6">
      <h2 class="mb-3 text-base font-semibold text-text">Générer l'écriture de paie</h2>
      <form class="space-y-4" @submit.prevent="soumettreGeneration">
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="mb-1 block text-sm font-medium text-text">Journal</label>
            <select v-model="generation.journal_id" required class="w-full rounded-md border border-border px-3 py-2 text-sm text-text">
              <option value="" disabled>— Choisir —</option>
              <option v-for="j in journaux ?? []" :key="j.id" :value="j.id">{{ j.code }} — {{ j.libelle }}</option>
            </select>
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-text">Compte de net à payer</label>
            <select v-model="generation.compte_net_a_payer_id" required class="w-full rounded-md border border-border px-3 py-2 text-sm text-text">
              <option value="" disabled>— Choisir —</option>
              <option v-for="c in comptes ?? []" :key="c.id" :value="c.id">{{ c.numero }} — {{ c.libelle }}</option>
            </select>
          </div>
        </div>
        <p v-if="erreurGeneration" class="text-sm text-danger">{{ erreurGeneration }}</p>
        <div class="flex justify-end gap-2">
          <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted" @click="genererOuvert = false">
            Annuler
          </button>
          <button type="submit" :disabled="genererEcriture.isPending.value" class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60">
            Générer
          </button>
        </div>
      </form>
    </div>
  </div>
</template>
