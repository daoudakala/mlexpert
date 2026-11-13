<script setup lang="ts">
/**
 * Sert à la création, à l'édition d'un brouillon et à la consultation
 * d'une écriture validée (route unique .../ecritures/nouvelle ou
 * .../ecritures/:id) :
 *   - nouvelle écriture : formulaire vide, lignes modifiables. À
 *     l'enregistrement, l'écriture est validée immédiatement (numéro de
 *     pièce généré par le logiciel) et le formulaire se vide pour enchaîner
 *     sur une nouvelle écriture, sans quitter l'écran.
 *     Avant toute saisie (sauf journal RAN), on choisit le MOIS DE TRAVAIL
 *     (période de l'exercice) : la date reste bornée à ce mois, un mois
 *     clôturé refuse la saisie. Pour un journal de caisse/banque, le solde
 *     initial, les totaux et le solde final du mois s'affichent. Le journal
 *     de report à nouveau (RAN) n'est pas saisissable : il est généré.
 *   - brouillon existant : mêmes champs, pré-remplis, modifiables
 *     (modifier_ecriture), avec bouton Valider et Supprimer.
 *   - écriture validée : champs en lecture seule (le backend refuse toute
 *     modification une fois validée), avec bouton Extourner et la liste
 *     des écritures qui l'extournent déjà, le cas échéant.
 */
import { computed, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useAuth } from "@/core/auth/useAuth";
import { messageErreur } from "@/core/api/erreurs";
import {
  useComptesEntreprise,
  useEcriture,
  useExournantes,
  useJournaux,
  useMutationGenererMois,
  useMutationsEcritures,
  usePeriodesExercice,
  useResumeJournal,
} from "./api";
import type { EcritureDuplication } from "./types";
import { useExercices } from "@/modules/exercices/api";
import { useListeTiers } from "@/modules/tiers/api";
import {
  telechargerDocument,
  useDocumentsPourEcriture,
  useListeDocuments,
  useMutationsDocuments,
} from "@/modules/documents/api";
import { CATEGORIES_DOCUMENT, type CategorieDocument } from "@/modules/documents/types";
import BaseFormulaire from "@/core/ui/BaseFormulaire.vue";
import CompteSelect from "./CompteSelect.vue";
import ConfirmDialog from "@/core/ui/ConfirmDialog.vue";
import { formaterMontant } from "@/core/ui/formatage";
import MontantInput from "@/core/ui/MontantInput.vue";
import StatutBadge from "@/core/ui/StatutBadge.vue";

const route = useRoute();
const router = useRouter();
const { contexteActif, aPermission } = useAuth();
const entrepriseId = computed(() => contexteActif.value?.entreprise.id);

const ecritureId = computed(() => (route.params.id as string) || null);
const enEdition = computed(() => ecritureId.value !== null);

const { data: ecritureExistante } = useEcriture(entrepriseId, ecritureId);
const estValidee = computed(() => ecritureExistante.value?.statut === "validee");
const lectureSeule = computed(() => enEdition.value && estValidee.value);

const { data: journaux } = useJournaux(entrepriseId);

const { data: exercices } = useExercices(entrepriseId);
// Plan comptable complet (jusqu'à 5000 comptes, au lieu des 1000 par défaut
// qui coupaient les classes élevées) — une seule requête, partagée par les
// sélecteurs de compte de toutes les lignes.
const { data: comptes } = useComptesEntreprise(entrepriseId, computed(() => ({ limite: 5000 })));
const { data: tiersListe } = useListeTiers(entrepriseId, computed(() => ({ actifsSeulement: true })));
const { data: extournantes } = useExournantes(entrepriseId, ecritureId);

const { creer, modifier, supprimer, valider, dupliquer, extourner } = useMutationsEcritures(entrepriseId);
const genererMois = useMutationGenererMois(entrepriseId);

interface LigneFormulaire {
  compte_id: string;
  sens: "debit" | "credit";
  montant: number;
  tiers_id: string;
  libelle: string;
}

function ligneVide(): LigneFormulaire {
  return { compte_id: "", sens: "debit", montant: 0, tiers_id: "", libelle: "" };
}

const formulaire = reactive({
  journal_id: "",
  exercice_id: "",
  date_ecriture: "",
  libelle: "",
  reference_piece: "",
  lignes: [ligneVide(), ligneVide()] as LigneFormulaire[],
});

// Venant d'un journal du menu latéral (?journal=BQ) : journal présélectionné.
watch(
  journaux,
  (liste) => {
    const code = route.query.journal;
    if (!liste || typeof code !== "string" || formulaire.journal_id) return;
    const trouve = liste.find((j) => j.code === code);
    if (trouve) formulaire.journal_id = trouve.id;
  },
  { immediate: true },
);

// --- Journal courant, mois de travail ---------------------------------------

// Le journal RAN (a_nouveaux) n'est jamais proposé à la saisie.
const journauxSaisie = computed(() =>
  enEdition.value ? (journaux.value ?? []) : (journaux.value ?? []).filter((j) => j.type_journal !== "a_nouveaux"),
);
const journalCourant = computed(() => (journaux.value ?? []).find((j) => j.id === formulaire.journal_id));
const estTresorerie = computed(
  () => journalCourant.value?.type_journal === "banque" || journalCourant.value?.type_journal === "caisse",
);

function aujourdhui(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const exerciceTravailId = ref("");
watch(
  exercices,
  (liste) => {
    if (exerciceTravailId.value || !liste || liste.length === 0) return;
    const jour = aujourdhui();
    const ouverts = liste.filter((e) => e.statut === "ouvert");
    const choisi =
      ouverts.find((e) => e.date_debut <= jour && jour <= e.date_fin) ??
      ouverts[ouverts.length - 1] ??
      liste[liste.length - 1];
    exerciceTravailId.value = choisi.id;
  },
  { immediate: true },
);

const { data: periodes } = usePeriodesExercice(entrepriseId, exerciceTravailId);
const moisId = ref("");
const moisChoisi = computed(() => (periodes.value ?? []).find((p) => p.id === moisId.value) ?? null);
const aDesMois = computed(() => (periodes.value ?? []).length > 0);

// Changement d'exercice : on repart sans mois choisi.
watch(exerciceTravailId, () => {
  moisId.value = "";
});
// Présélection : le mois ouvert qui contient aujourd'hui, sinon le premier ouvert.
watch(
  periodes,
  (liste) => {
    if (moisId.value || !liste || liste.length === 0) return;
    const jour = aujourdhui();
    const ouvertes = liste.filter((p) => p.statut === "ouverte");
    const choisi = ouvertes.find((p) => p.date_debut <= jour && jour <= p.date_fin) ?? ouvertes[0];
    if (choisi) moisId.value = choisi.id;
  },
  { immediate: true },
);

// La date reste cohérente avec le mois choisi.
watch(moisChoisi, (m) => {
  if (!m || enEdition.value) return;
  const d = formulaire.date_ecriture;
  if (d && d >= m.date_debut && d <= m.date_fin) return;
  const jour = aujourdhui();
  formulaire.date_ecriture = jour >= m.date_debut && jour <= m.date_fin ? jour : m.date_debut;
});

const estRan = computed(() => journalCourant.value?.type_journal === "a_nouveaux");
const raisonBlocage = computed<string | null>(() => {
  if (enEdition.value) return null;
  if (estRan.value) return "Le journal de report à nouveau n'est pas saisissable : il est généré automatiquement.";
  if (aDesMois.value && !moisChoisi.value) return "Choisis le mois de travail avant de saisir.";
  if (moisChoisi.value?.statut === "cloturee") return "Ce mois est clôturé : aucune saisie n'est possible.";
  return null;
});

async function creerLesMois(): Promise<void> {
  erreur.value = null;
  try {
    await genererMois.mutateAsync(exerciceTravailId.value);
  } catch (e) {
    erreur.value = messageErreur(e);
  }
}

// Récapitulatif du mois pour un journal de caisse / banque.
const { data: resume } = useResumeJournal(
  entrepriseId,
  computed(() => (estTresorerie.value && !enEdition.value ? formulaire.journal_id : null)),
  computed(() => moisChoisi.value?.date_debut ?? null),
  computed(() => moisChoisi.value?.date_fin ?? null),
);

watch(
  ecritureExistante,
  (e) => {
    if (!e) return;
    formulaire.journal_id = e.journal_id;
    formulaire.exercice_id = e.exercice_id;
    formulaire.date_ecriture = e.date_ecriture;
    formulaire.libelle = e.libelle;
    formulaire.reference_piece = e.reference_piece ?? "";
    formulaire.lignes = e.lignes.map((l) => ({
      compte_id: l.compte_id,
      sens: Number(l.credit) > 0 ? "credit" : "debit",
      montant: Number(l.credit) > 0 ? Number(l.credit) : Number(l.debit),
      tiers_id: l.tiers_id ?? "",
      libelle: l.libelle ?? "",
    }));
  },
  { immediate: true },
);

const totalDebit = computed(() =>
  formulaire.lignes.reduce((s, l) => s + (l.sens === "debit" ? l.montant : 0), 0),
);
const totalCredit = computed(() =>
  formulaire.lignes.reduce((s, l) => s + (l.sens === "credit" ? l.montant : 0), 0),
);
const equilibree = computed(() => Math.abs(totalDebit.value - totalCredit.value) < 0.005);

// --- Contrepartie automatique ------------------------------------------------
// Pour une NOUVELLE écriture, la dernière ligne équilibre automatiquement les
// autres (sens et montant). Dès que l'utilisateur la modifie lui-même, la
// contrepartie automatique s'arrête ; ajouter une ligne la relance sur la
// nouvelle dernière ligne. On repère la modification manuelle en comparant
// la ligne aux dernières valeurs calculées (aucun événement du composant de
// montant n'est nécessaire).
const contrepartieAuto = ref(true);
let derniereValeurAuto: { sens: "debit" | "credit"; montant: number } | null = null;

function recalculerContrepartie(): void {
  if (enEdition.value || !contrepartieAuto.value || formulaire.lignes.length < 2) return;
  const derniere = formulaire.lignes[formulaire.lignes.length - 1];
  if (
    derniereValeurAuto &&
    (derniere.sens !== derniereValeurAuto.sens || derniere.montant !== derniereValeurAuto.montant)
  ) {
    contrepartieAuto.value = false;
    return;
  }
  const net = formulaire.lignes
    .slice(0, -1)
    .reduce((s, l) => s + (l.sens === "debit" ? l.montant : -l.montant), 0);
  const sens: "debit" | "credit" = net > 0 ? "credit" : net < 0 ? "debit" : derniere.sens;
  const montant = Math.round(Math.abs(net) * 100) / 100;
  if (derniere.sens !== sens) derniere.sens = sens;
  if (derniere.montant !== montant) derniere.montant = montant;
  derniereValeurAuto = { sens: derniere.sens, montant: derniere.montant };
}

watch(() => formulaire.lignes, recalculerContrepartie, { deep: true });

function ajouterLigne(): void {
  formulaire.lignes.push(ligneVide());
  contrepartieAuto.value = true;
  derniereValeurAuto = null;
}
function retirerLigne(index: number): void {
  formulaire.lignes.splice(index, 1);
}

function lignesSaisies() {
  return formulaire.lignes.map((l) => ({
    compte_id: l.compte_id,
    debit: l.sens === "debit" ? l.montant : 0,
    credit: l.sens === "credit" ? l.montant : 0,
    tiers_id: l.tiers_id || null,
    // Libellé uniforme : toutes les lignes portent celui de l'écriture.
    libelle: formulaire.libelle,
  }));
}

const erreur = ref<string | null>(null);
// Dernière écriture enregistrée depuis ce formulaire (bandeau de confirmation).
const derniereEcriture = ref<{ id: string; numero: string | null } | null>(null);
// Vrai quand la dernière écriture enregistrée débite un compte d'immobilisation
// (21 à 27) : on propose d'aller la reprendre dans le module Immobilisations.
const acquisitionDetectee = ref(false);

function reinitialiserSaisie(): void {
  // On garde le journal et la date : on enchaîne souvent plusieurs
  // écritures du même jour dans le même journal.
  formulaire.libelle = "";
  formulaire.reference_piece = "";
  formulaire.lignes = [ligneVide(), ligneVide()];
  contrepartieAuto.value = true;
  derniereValeurAuto = null;
}

const enEnvoi = computed(() => creer.isPending.value || modifier.isPending.value);

async function soumettre(): Promise<void> {
  erreur.value = null;
  if (raisonBlocage.value) {
    erreur.value = raisonBlocage.value;
    return;
  }
  if (
    !enEdition.value &&
    moisChoisi.value &&
    (formulaire.date_ecriture < moisChoisi.value.date_debut || formulaire.date_ecriture > moisChoisi.value.date_fin)
  ) {
    erreur.value = `La date doit rester dans le mois choisi (${moisChoisi.value.date_debut} → ${moisChoisi.value.date_fin}).`;
    return;
  }
  if (formulaire.lignes.some((l) => !l.compte_id)) {
    erreur.value = "Choisis un compte pour chaque ligne.";
    return;
  }
  if (!equilibree.value) {
    erreur.value = `L'écriture n'est pas équilibrée : débit ${totalDebit.value} ≠ crédit ${totalCredit.value}.`;
    return;
  }
  try {
    if (enEdition.value) {
      const ecriture = await modifier.mutateAsync({
        id: ecritureId.value!,
        donnees: {
          date_ecriture: formulaire.date_ecriture,
          libelle: formulaire.libelle,
          reference_piece: formulaire.reference_piece || null,
          lignes: lignesSaisies(),
        },
      });
      router.push({ name: "comptabilite.ecriture", params: { id: ecriture.id } });
    } else {
      const ecriture = await creer.mutateAsync({
        journal_id: formulaire.journal_id,
        date_ecriture: formulaire.date_ecriture,
        libelle: formulaire.libelle,
        // Numéro de pièce : généré par le logiciel à la validation.
        reference_piece: null,
        lignes: lignesSaisies(),
      });
      derniereEcriture.value = { id: ecriture.id, numero: ecriture.numero };
      acquisitionDetectee.value = ecriture.lignes.some((l) => {
        const numero = comptes.value?.find((c) => c.id === l.compte_id)?.numero ?? "";
        return Number(l.debit) > 0 && /^2[1-7]/.test(numero);
      });
      reinitialiserSaisie();
    }
  } catch (e) {
    erreur.value = messageErreur(e);
  }
}

const confirmationSuppression = ref(false);
async function confirmerSuppression(): Promise<void> {
  await supprimer.mutateAsync(ecritureId.value!);
  router.push({ name: "comptabilite.ecritures" });
}

const erreurValidation = ref<string | null>(null);
async function validerEcriture(): Promise<void> {
  erreurValidation.value = null;
  try {
    await valider.mutateAsync(ecritureId.value!);
  } catch (e) {
    erreurValidation.value = messageErreur(e);
  }
}

const duplicationOuverte = ref(false);
const duplication = reactive({ date_ecriture: "", exercice_id: "", libelle: "" });
const erreurDuplication = ref<string | null>(null);

function ouvrirDuplication(): void {
  duplication.date_ecriture = "";
  duplication.exercice_id = formulaire.exercice_id;
  duplication.libelle = "";
  erreurDuplication.value = null;
  duplicationOuverte.value = true;
}

async function soumettreDuplication(): Promise<void> {
  erreurDuplication.value = null;
  try {
    const donnees: EcritureDuplication = {
      date_ecriture: duplication.date_ecriture,
      exercice_id: duplication.exercice_id || null,
      libelle: duplication.libelle || null,
    };
    const copie = await dupliquer.mutateAsync({ id: ecritureId.value!, donnees });
    duplicationOuverte.value = false;
    router.push({ name: "comptabilite.ecriture", params: { id: copie.id } });
  } catch (e) {
    erreurDuplication.value = messageErreur(e);
  }
}

const extourneOuvert = ref(false);
const extourne = reactive({ date_ecriture: "", libelle: "" });
const erreurExtourne = ref<string | null>(null);
async function soumettreExtourne(): Promise<void> {
  erreurExtourne.value = null;
  try {
    const nouvelle = await extourner.mutateAsync({
      id: ecritureId.value!,
      donnees: { date_ecriture: extourne.date_ecriture, libelle: extourne.libelle || null },
    });
    extourneOuvert.value = false;
    router.push({ name: "comptabilite.ecriture", params: { id: nouvelle.id } });
  } catch (e) {
    erreurExtourne.value = messageErreur(e);
  }
}

// --- Pièces justificatives (section 8.2 du cahier) --------------------------
// Un document peut être soit déposé directement en rattachement (nouveau
// fichier), soit rattaché après coup parmi les documents déjà déposés dans
// l'entreprise (donc pas encore rattachés à une autre écriture) — les deux
// options cohabitent dans le même panneau.

const { data: piecesJustificatives } = useDocumentsPourEcriture(entrepriseId, ecritureId);
const { deposer: deposerDocument, rattacherEcriture, detacherEcriture } = useMutationsDocuments(entrepriseId);

const piecesOuvert = ref(false);

// Documents déjà déposés dans l'entreprise, non rattachés à une écriture —
// candidats au rattachement sans nouveau dépôt.
const filtresDocumentsLibres = computed(() => ({}));
const { data: documentsEntreprise } = useListeDocuments(entrepriseId, filtresDocumentsLibres);
const documentsRattachables = computed(() =>
  (documentsEntreprise.value ?? []).filter((d) => !d.ecriture_id),
);

const nouveauDepot = reactive({
  fichier: null as File | null,
  categorie: "comptable" as CategorieDocument,
});
const documentARattacher = ref("");
const erreurPieces = ref<string | null>(null);

function surChoixFichierPiece(evenement: Event): void {
  nouveauDepot.fichier = (evenement.target as HTMLInputElement).files?.[0] ?? null;
}

async function deposerNouvellePiece(): Promise<void> {
  erreurPieces.value = null;
  if (!nouveauDepot.fichier) {
    erreurPieces.value = "Choisis un fichier à déposer.";
    return;
  }
  try {
    await deposerDocument.mutateAsync({
      fichier: nouveauDepot.fichier,
      categorie: nouveauDepot.categorie,
      ecriture_id: ecritureId.value!,
    });
    nouveauDepot.fichier = null;
  } catch (e) {
    erreurPieces.value = messageErreur(e);
  }
}

async function rattacherPieceExistante(): Promise<void> {
  erreurPieces.value = null;
  if (!documentARattacher.value) return;
  try {
    await rattacherEcriture.mutateAsync({ id: documentARattacher.value, ecritureId: ecritureId.value! });
    documentARattacher.value = "";
  } catch (e) {
    erreurPieces.value = messageErreur(e);
  }
}

async function detacherPiece(documentId: string): Promise<void> {
  await detacherEcriture.mutateAsync(documentId);
}

async function telechargerPiece(piece: NonNullable<typeof piecesJustificatives.value>[number]): Promise<void> {
  await telechargerDocument(entrepriseId, piece);
}
</script>

<template>
  <div class="max-w-4xl space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-lg font-semibold text-text">
        {{ enEdition ? (ecritureExistante?.numero ?? "Écriture (brouillon)") : "Nouvelle écriture" }}
      </h1>
      <div class="flex items-center gap-3">
        <StatutBadge
          v-if="enEdition"
          :libelle="estValidee ? 'Validée' : 'Brouillon'"
          :tonalite="estValidee ? 'succes' : 'avertissement'"
        />
        <button
          v-if="enEdition && ecritureExistante && aPermission('ecriture.creer')"
          type="button"
          class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted"
          @click="ouvrirDuplication"
        >
          Dupliquer
        </button>
      </div>
    </div>

    <div v-if="duplicationOuverte" class="rounded-lg border border-border bg-surface p-6">
      <h2 class="mb-3 text-base font-semibold text-text">Dupliquer cette écriture</h2>
      <p class="mb-3 text-sm text-text-muted">
        Crée une nouvelle écriture en brouillon avec les mêmes lignes — l'originale n'est pas modifiée.
        Tous les contrôles habituels s'appliquent à la cible (exercice ouvert, comptes toujours actifs, équilibre).
      </p>
      <form class="space-y-4" @submit.prevent="soumettreDuplication">
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="mb-1 block text-sm font-medium text-text">Exercice cible</label>
            <select v-model="duplication.exercice_id" required class="w-full rounded-md border border-border px-3 py-2 text-text">
              <option value="" disabled>— Choisir —</option>
              <option v-for="e in exercices" :key="e.id" :value="e.id">{{ e.date_debut }} → {{ e.date_fin }}</option>
            </select>
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-text">Date</label>
            <input v-model="duplication.date_ecriture" type="date" required class="w-full rounded-md border border-border px-3 py-2 text-text" />
          </div>
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-text">Libellé (optionnel — par défaut « Copie de … »)</label>
          <input v-model="duplication.libelle" class="w-full rounded-md border border-border px-3 py-2 text-text" />
        </div>
        <p v-if="erreurDuplication" class="text-sm text-danger">{{ erreurDuplication }}</p>
        <div class="flex justify-end gap-2">
          <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted" @click="duplicationOuverte = false">
            Annuler
          </button>
          <button type="submit" :disabled="dupliquer.isPending.value" class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60">
            Créer la copie (brouillon)
          </button>
        </div>
      </form>
    </div>

    <div
      v-if="derniereEcriture && !enEdition"
      class="flex items-center justify-between rounded-lg border border-success bg-success/10 px-4 py-3 text-sm text-text"
    >
      <span>
        Écriture enregistrée et validée — numéro de pièce
        <strong>{{ derniereEcriture.numero ?? "—" }}</strong>. Le formulaire est prêt pour une nouvelle écriture.
      </span>
      <router-link
        :to="{ name: 'comptabilite.ecriture', params: { id: derniereEcriture.id } }"
        class="text-primary hover:underline"
      >
        Voir l'écriture
      </router-link>
    </div>
    <div
      v-if="acquisitionDetectee && !enEdition && aPermission('immobilisation.creer')"
      class="flex items-center justify-between rounded-lg border border-warning bg-warning-bg px-4 py-3 text-sm text-text"
    >
      <span>Cette écriture débite un compte d'immobilisation (classe 2) : elle peut être reprise en immobilisation.</span>
      <router-link :to="{ name: 'immobilisations.a-confirmer' }" class="font-medium text-primary hover:underline">
        Confirmer l'immobilisation
      </router-link>
    </div>

    <!-- Mois de travail (nouvelle écriture uniquement) -->
    <div v-if="!enEdition && !estRan" class="space-y-3 rounded-lg border border-border bg-surface p-4">
      <div class="flex flex-wrap items-end gap-3">
        <div>
          <label class="mb-1 block text-xs font-medium text-text-muted">Exercice</label>
          <select v-model="exerciceTravailId" class="rounded-md border border-border px-2 py-1.5 text-sm text-text">
            <option v-for="e in exercices" :key="e.id" :value="e.id">
              {{ e.date_debut }} → {{ e.date_fin }}{{ e.statut === "cloture" ? " (clôturé)" : "" }}
            </option>
          </select>
        </div>
        <div>
          <label class="mb-1 block text-xs font-medium text-text-muted">Mois de travail</label>
          <select v-model="moisId" :disabled="!aDesMois" class="rounded-md border border-border px-2 py-1.5 text-sm text-text disabled:opacity-60">
            <option value="" disabled>— Choisir le mois —</option>
            <option v-for="p in periodes" :key="p.id" :value="p.id" :disabled="p.statut === 'cloturee'">
              {{ p.libelle ?? p.date_debut }}{{ p.statut === "cloturee" ? " (clôturé)" : "" }}
            </option>
          </select>
        </div>
        <button
          v-if="aPermission('periode.creer') && exerciceTravailId"
          type="button"
          :disabled="genererMois.isPending.value"
          class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted disabled:opacity-60"
          @click="creerLesMois"
        >
          {{ aDesMois ? "Créer les mois manquants" : "Créer les mois de l'exercice" }}
        </button>
      </div>
      <p v-if="!aDesMois" class="text-xs text-text-muted">
        Aucun mois défini pour cet exercice : crée-les pour cadrer la saisie. Tant qu'aucun mois n'existe, la
        saisie reste libre dans l'exercice.
      </p>
    </div>

    <div v-if="estRan && !enEdition" class="rounded-lg border border-border bg-surface-muted px-4 py-3 text-sm text-text-muted">
      Le journal de report à nouveau n'est pas saisissable : ses écritures sont générées automatiquement et ne
      peuvent être ni ajoutées, ni modifiées, ni supprimées.
    </div>
    <p v-else-if="raisonBlocage" class="rounded-lg border border-danger px-4 py-3 text-sm text-danger">
      {{ raisonBlocage }}
    </p>

    <!-- Caisse / banque : situation du mois -->
    <div v-if="estTresorerie && !enEdition && resume" class="rounded-lg border border-border bg-surface p-4">
      <h2 class="mb-2 text-sm font-semibold text-text">
        {{ journalCourant?.libelle }} — {{ moisChoisi?.libelle ?? "mois choisi" }}
      </h2>
      <dl class="grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
        <div><dt class="text-text-muted">Solde initial</dt><dd class="font-medium text-text">{{ formaterMontant(resume.solde_initial) }}</dd></div>
        <div><dt class="text-text-muted">Total débit</dt><dd class="font-medium text-text">{{ formaterMontant(resume.total_debit) }}</dd></div>
        <div><dt class="text-text-muted">Total crédit</dt><dd class="font-medium text-text">{{ formaterMontant(resume.total_credit) }}</dd></div>
        <div><dt class="text-text-muted">Solde final</dt><dd class="font-semibold text-text">{{ formaterMontant(resume.solde_final) }}</dd></div>
      </dl>
      <details v-if="resume.mouvements.length > 0" class="mt-3 text-sm">
        <summary class="cursor-pointer text-primary">Voir les {{ resume.mouvements.length }} mouvement(s)</summary>
        <table class="mt-2 w-full text-xs">
          <thead class="text-left text-text-muted">
            <tr><th class="py-1">Date</th><th>Pièce</th><th>Libellé</th><th class="text-right">Débit</th><th class="text-right">Crédit</th><th class="text-right">Solde</th></tr>
          </thead>
          <tbody class="divide-y divide-border">
            <tr v-for="(m, i) in resume.mouvements" :key="i" class="text-text">
              <td class="py-1">{{ m.date_ecriture }}</td>
              <td>{{ m.numero ?? "—" }}</td>
              <td>{{ m.libelle }}</td>
              <td class="text-right">{{ Number(m.debit) > 0 ? formaterMontant(m.debit) : "" }}</td>
              <td class="text-right">{{ Number(m.credit) > 0 ? formaterMontant(m.credit) : "" }}</td>
              <td class="text-right">{{ formaterMontant(m.solde_cumule) }}</td>
            </tr>
          </tbody>
        </table>
      </details>
      <p class="mt-2 text-xs text-text-muted">Solde en débit − crédit, sur les comptes de trésorerie de ce journal (écritures validées).</p>
    </div>

    <BaseFormulaire
      v-if="!lectureSeule"
      titre="Informations"
      :erreur="erreur"
      :en-envoi="enEnvoi"
      :libelle-enregistrer="enEdition ? 'Enregistrer les modifications' : 'Enregistrer'"
      @soumettre="soumettre"
      @annuler="router.push({ name: 'comptabilite.ecritures' })"
    >
      <fieldset class="space-y-4">
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="mb-1 block text-sm font-medium text-text">Journal</label>
            <select v-model="formulaire.journal_id" required :disabled="enEdition" class="w-full rounded-md border border-border px-3 py-2 text-text disabled:opacity-60">
              <option value="" disabled>— Choisir —</option>
              <option v-for="j in journauxSaisie" :key="j.id" :value="j.id">{{ j.code }} — {{ j.libelle }}</option>
            </select>
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-text">Date</label>
            <input v-model="formulaire.date_ecriture" type="date" required :min="!enEdition ? moisChoisi?.date_debut : undefined" :max="!enEdition ? moisChoisi?.date_fin : undefined" class="w-full rounded-md border border-border px-3 py-2 text-text" />
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="mb-1 block text-sm font-medium text-text">Numéro de pièce</label>
            <input
              v-if="!enEdition"
              value="Généré automatiquement à l'enregistrement"
              disabled
              class="w-full rounded-md border border-border px-3 py-2 text-text-muted disabled:opacity-70"
            />
            <input v-else v-model="formulaire.reference_piece" class="w-full rounded-md border border-border px-3 py-2 text-text" />
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-text">Libellé</label>
            <input v-model="formulaire.libelle" required minlength="2" class="w-full rounded-md border border-border px-3 py-2 text-text" />
          </div>
        </div>

        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <h3 class="text-sm font-semibold text-text">Lignes</h3>
            <button v-if="!lectureSeule" type="button" class="text-sm text-primary hover:underline" @click="ajouterLigne">
              + Ajouter une ligne
            </button>
          </div>

          <div v-for="(ligne, index) in formulaire.lignes" :key="index" class="grid grid-cols-12 items-end gap-2 rounded-md border border-border p-3">
            <div class="col-span-4">
              <label class="mb-1 block text-xs font-medium text-text-muted">Compte</label>
              <CompteSelect v-model="ligne.compte_id" :comptes="comptes" required />
            </div>
            <div class="col-span-2">
              <label class="mb-1 block text-xs font-medium text-text-muted">Tiers (optionnel)</label>
              <select v-model="ligne.tiers_id" class="w-full rounded-md border border-border px-2 py-1.5 text-sm text-text">
                <option value="">— Aucun —</option>
                <option v-for="t in tiersListe" :key="t.id" :value="t.id">{{ t.code }}</option>
              </select>
            </div>
            <div class="col-span-2">
              <label class="mb-1 block text-xs font-medium text-text-muted">Sens</label>
              <select v-model="ligne.sens" class="w-full rounded-md border border-border px-2 py-1.5 text-sm text-text">
                <option value="debit">Débit</option>
                <option value="credit">Crédit</option>
              </select>
            </div>
            <div class="col-span-3">
              <label class="mb-1 block text-xs font-medium text-text-muted">Montant</label>
              <MontantInput v-model="ligne.montant" required />
            </div>
            <div class="col-span-1">
              <button
                v-if="!lectureSeule"
                type="button"
                :disabled="formulaire.lignes.length <= 2"
                class="w-full rounded-md border border-border px-2 py-1.5 text-sm text-text hover:bg-surface-muted disabled:opacity-40"
                @click="retirerLigne(index)"
              >
                Retirer
              </button>
            </div>
          </div>

          <p class="text-sm" :class="equilibree ? 'text-text-muted' : 'text-danger'">
            Total débit : {{ formaterMontant(totalDebit) }} — Total crédit : {{ formaterMontant(totalCredit) }}
            <span v-if="!equilibree"> (non équilibrée)</span>
          </p>
        </div>
      </fieldset>
    </BaseFormulaire>

    <div v-else class="space-y-4 rounded-lg border border-border bg-surface p-6 text-sm">
      <div class="grid grid-cols-2 gap-4">
        <div><p class="text-text-muted">Date</p><p class="text-text">{{ formulaire.date_ecriture }}</p></div>
        <div><p class="text-text-muted">Numéro de pièce</p><p class="text-text">{{ ecritureExistante?.numero ?? formulaire.reference_piece ?? "—" }}</p></div>
      </div>
      <div><p class="text-text-muted">Libellé</p><p class="text-text">{{ formulaire.libelle }}</p></div>
      <div class="overflow-hidden rounded-lg border border-border">
        <table class="w-full text-sm">
          <thead class="bg-surface-muted text-left text-xs font-medium uppercase text-text-muted">
            <tr><th class="px-3 py-2">Compte</th><th class="px-3 py-2">Libellé</th><th class="px-3 py-2 text-right">Débit</th><th class="px-3 py-2 text-right">Crédit</th></tr>
          </thead>
          <tbody class="divide-y divide-border">
            <tr v-for="(l, i) in ecritureExistante?.lignes ?? []" :key="i">
              <td class="px-3 py-2 text-text">{{ comptes?.find((c) => c.id === l.compte_id)?.numero ?? l.compte_id }}</td>
              <td class="px-3 py-2 text-text">{{ l.libelle ?? "—" }}</td>
              <td class="px-3 py-2 text-right text-text">{{ Number(l.debit) > 0 ? formaterMontant(l.debit) : "" }}</td>
              <td class="px-3 py-2 text-right text-text">{{ Number(l.credit) > 0 ? formaterMontant(l.credit) : "" }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <template v-if="enEdition && ecritureExistante">
      <div v-if="!estValidee" class="flex items-center justify-between rounded-lg border border-border bg-surface p-6">
        <div>
          <p class="text-sm font-medium text-text">Validation</p>
          <p class="text-sm text-text-muted">Une fois validée, l'écriture ne peut plus être modifiée ni supprimée.</p>
          <p v-if="erreurValidation" class="text-sm text-danger">{{ erreurValidation }}</p>
        </div>
        <div class="flex gap-2">
          <button type="button" class="rounded-md border border-danger px-3 py-1.5 text-sm text-danger hover:bg-danger/10" @click="confirmationSuppression = true">
            Supprimer
          </button>
          <button type="button" :disabled="valider.isPending.value" class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60" @click="validerEcriture">
            Valider
          </button>
        </div>
      </div>

      <div v-else class="space-y-4 rounded-lg border border-border bg-surface p-6">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm font-medium text-text">Écriture validée — {{ ecritureExistante.numero }}</p>
            <p class="text-sm text-text-muted">Une correction se fait par une écriture d'extourne.</p>
          </div>
          <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted" @click="extourneOuvert = true">
            Extourner
          </button>
        </div>
        <div v-if="extournantes && extournantes.length > 0" class="text-sm">
          <p class="font-medium text-text">Extournée par :</p>
          <ul class="mt-1 list-inside list-disc text-text-muted">
            <li v-for="e in extournantes" :key="e.id">
              <router-link :to="{ name: 'comptabilite.ecriture', params: { id: e.id } }" class="text-primary hover:underline">
                {{ e.numero ?? "brouillon" }} — {{ e.libelle }}
              </router-link>
            </li>
          </ul>
        </div>
      </div>
    </template>

    <div v-if="enEdition && ecritureExistante" class="space-y-4 rounded-lg border border-border bg-surface p-6">
      <div class="flex items-center justify-between">
        <h2 class="text-sm font-semibold text-text">Pièces justificatives</h2>
        <button
          v-if="aPermission('document.creer')"
          type="button"
          class="text-sm text-primary hover:underline"
          @click="piecesOuvert = !piecesOuvert"
        >
          Rattacher une pièce
        </button>
      </div>

      <ul v-if="piecesJustificatives && piecesJustificatives.length > 0" class="divide-y divide-border text-sm">
        <li v-for="p in piecesJustificatives" :key="p.id" class="flex items-center justify-between py-2">
          <span class="text-text">{{ p.nom_fichier }}</span>
          <div class="flex items-center gap-3">
            <button type="button" class="text-primary hover:underline" @click="telechargerPiece(p)">
              Télécharger
            </button>
            <button
              v-if="aPermission('document.modifier')"
              type="button"
              class="text-text-muted hover:underline"
              @click="detacherPiece(p.id)"
            >
              Détacher
            </button>
          </div>
        </li>
      </ul>
      <p v-else class="text-sm text-text-muted">Aucune pièce justificative rattachée pour le moment.</p>

      <div v-if="piecesOuvert" class="space-y-4 rounded-md border border-border p-4">
        <div>
          <h3 class="mb-2 text-xs font-semibold uppercase text-text-muted">Déposer un nouveau fichier</h3>
          <form class="flex flex-wrap items-end gap-3" @submit.prevent="deposerNouvellePiece">
            <div>
              <label class="mb-1 block text-xs font-medium text-text-muted">Fichier</label>
              <input type="file" class="text-sm text-text" @change="surChoixFichierPiece" />
            </div>
            <div>
              <label class="mb-1 block text-xs font-medium text-text-muted">Catégorie</label>
              <select v-model="nouveauDepot.categorie" class="rounded-md border border-border px-2 py-1.5 text-sm text-text">
                <option v-for="c in CATEGORIES_DOCUMENT" :key="c.valeur" :value="c.valeur">{{ c.libelle }}</option>
              </select>
            </div>
            <button
              type="submit"
              :disabled="deposerDocument.isPending.value"
              class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60"
            >
              Déposer et rattacher
            </button>
          </form>
        </div>

        <div>
          <h3 class="mb-2 text-xs font-semibold uppercase text-text-muted">
            Ou rattacher un document déjà déposé
          </h3>
          <div class="flex flex-wrap items-end gap-3">
            <select v-model="documentARattacher" class="rounded-md border border-border px-2 py-1.5 text-sm text-text">
              <option value="" disabled>— Choisir un document —</option>
              <option v-for="d in documentsRattachables" :key="d.id" :value="d.id">{{ d.nom_fichier }}</option>
            </select>
            <button
              type="button"
              :disabled="!documentARattacher || rattacherEcriture.isPending.value"
              class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted disabled:opacity-60"
              @click="rattacherPieceExistante"
            >
              Rattacher
            </button>
          </div>
        </div>

        <p v-if="erreurPieces" class="text-sm text-danger">{{ erreurPieces }}</p>
      </div>
    </div>

    <ConfirmDialog
      v-model:ouvert="confirmationSuppression"
      titre="Supprimer ce brouillon ?"
      message="Cette action est irréversible."
      libelle-confirmer="Supprimer"
      dangereux
      @confirmer="confirmerSuppression"
    />

    <div v-if="extourneOuvert" class="rounded-lg border border-border bg-surface p-6">
      <h2 class="mb-3 text-base font-semibold text-text">Extourner cette écriture</h2>
      <form class="space-y-4" @submit.prevent="soumettreExtourne">
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="mb-1 block text-sm font-medium text-text">Date de l'extourne</label>
            <input v-model="extourne.date_ecriture" type="date" required class="w-full rounded-md border border-border px-3 py-2 text-text" />
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-text">Libellé (optionnel)</label>
            <input v-model="extourne.libelle" class="w-full rounded-md border border-border px-3 py-2 text-text" />
          </div>
        </div>
        <p v-if="erreurExtourne" class="text-sm text-danger">{{ erreurExtourne }}</p>
        <div class="flex justify-end gap-2">
          <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface-muted" @click="extourneOuvert = false">
            Annuler
          </button>
          <button type="submit" :disabled="extourner.isPending.value" class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60">
            Créer l'extourne
          </button>
        </div>
      </form>
    </div>
  </div>
</template>