<script setup lang="ts">
/**
 * Page d'accueil (route `accueil`) : tableau de bord affiché dès la
 * connexion pour les personnes qui ont la permission `dashboard.consulter`
 * (indicateurs de gestion, structure financière, pilotage Direction /
 * Comptabilité). Les rapports détaillés (balance, grand livre, états
 * financiers, échéancier…) restent dans ReportingPage, ouverts depuis le
 * menu latéral.
 *
 * Le message de bienvenue simple reste le contenu de repli pour les
 * comptes sans cette permission (ex. portail client) — la route `accueil`
 * ne doit JAMAIS porter elle-même une exigence de permission, car le garde
 * de navigation (router/index.ts) y redirige en cas de refus ; une boucle
 * de redirection infinie s'ensuivrait sinon.
 */
import { computed, ref } from "vue";

import { useAuth } from "@/core/auth/useAuth";
import { formaterMontant } from "@/core/ui/formatage";
import { useExercices } from "@/modules/exercices/api";
import { useTableauBord } from "./api";
import type { IndicateurComparatif } from "./types";

const { utilisateur, contexteActif, aPermission } = useAuth();
const peutVoir = computed(() => aPermission("dashboard.consulter"));
// Sans la permission, aucune requête n'est émise (elles échoueraient en 403).
const entrepriseId = computed(() => (peutVoir.value ? contexteActif.value?.entreprise.id : null));

// --- Exercice et période -----------------------------------------------------

const { data: exercices } = useExercices(entrepriseId);
const exerciceChoisi = ref<string | null>(null);
// Le filtre par période a été retiré de l'écran : le tableau de bord porte
// toujours sur l'exercice entier (le backend accepte encore des dates).
const dateDebut = ref<string | null>(null);
const dateFin = ref<string | null>(null);

const { data: tb, isLoading, isError } = useTableauBord(entrepriseId, exerciceChoisi, dateDebut, dateFin);

// L'exercice affiché dans la liste : celui choisi, sinon celui que le
// backend a retenu (exercice courant).
const exerciceAffiche = computed(() => exerciceChoisi.value ?? tb.value?.exercice_id ?? "");

function libelleExercice(dateFinExercice: string): string {
  return `Exercice ${dateFinExercice.slice(0, 4)}`;
}

function surChangementExercice(evenement: Event): void {
  exerciceChoisi.value = (evenement.target as HTMLSelectElement).value || null;
}

// --- Formatage -----------------------------------------------------------------

function fcfa(valeur: string | number | null | undefined): string {
  return `${formaterMontant(valeur)} F CFA`;
}

function nombre(valeur: string | null | undefined): number {
  return Number(valeur ?? 0);
}

function formaterVariation(pct: number): string {
  return `${new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 }).format(pct)} %`;
}

function texteComparaison(indicateur: IndicateurComparatif): string {
  if (tb.value?.annee_precedente == null) return "Aucun exercice précédent à comparer";
  if (indicateur.variation_pourcentage === null) return `Pas de base de comparaison en ${tb.value.annee_precedente}`;
  return `${formaterVariation(indicateur.variation_pourcentage)} par rapport à ${tb.value.annee_precedente}`;
}

function classeVariation(indicateur: IndicateurComparatif): string {
  const v = indicateur.variation_pourcentage;
  if (v === null) return "text-text-muted";
  return v >= 0 ? "text-success" : "text-danger";
}

function classeMontant(valeur: string): string {
  return nombre(valeur) < 0 ? "text-danger" : "text-text";
}

// Barre de progression des cartes Marge / VA / EBE : part du chiffre
// d'affaires (bornée à 0-100 %).
function partDuCa(valeur: string): number {
  const ca = nombre(tb.value?.chiffre_affaires.valeur);
  if (ca <= 0) return 0;
  return Math.max(0, Math.min(100, (nombre(valeur) / ca) * 100));
}

// --- Graphiques (HTML/CSS purs, aucune librairie de graphiques) -----------------

const lignesFrBfr = computed(() => {
  if (!tb.value) return [];
  const fr = nombre(tb.value.fonds_roulement);
  const bfr = nombre(tb.value.besoin_fonds_roulement);
  const max = Math.max(Math.abs(fr), Math.abs(bfr), 1);
  return [
    { sigle: "FR", valeur: fr, largeur: Math.max(12, (Math.abs(fr) / max) * 100) },
    { sigle: "BFR", valeur: bfr, largeur: Math.max(12, (Math.abs(bfr) / max) * 100) },
  ];
});

interface Segment {
  libelle: string;
  valeur: number;
  couleur: string;
}

const colonnesBilan = computed<{ titre: string; segments: Segment[]; total: number }[]>(() => {
  if (!tb.value) return [];
  const b = tb.value.bilan_fonctionnel;
  const emplois: Segment[] = [
    { libelle: "Immobilisations", valeur: nombre(b.immobilisations), couleur: "bg-[#6b5fb5]" },
    { libelle: "Actif circulant", valeur: nombre(b.actif_circulant), couleur: "bg-[#3fae49]" },
    { libelle: "Trésorerie active", valeur: nombre(b.tresorerie_actif), couleur: "bg-[#3b9be0]" },
  ];
  const ressources: Segment[] = [
    { libelle: "Ressources durables", valeur: nombre(b.ressources_durables), couleur: "bg-[#e07b39]" },
    { libelle: "Passif circulant", valeur: nombre(b.passif_circulant), couleur: "bg-[#d94f70]" },
    { libelle: "Trésorerie passive", valeur: nombre(b.tresorerie_passif), couleur: "bg-[#f2c230]" },
  ];
  const somme = (segments: Segment[]) => segments.reduce((s, x) => s + Math.max(0, x.valeur), 0);
  return [
    { titre: "Emplois", segments: emplois, total: somme(emplois) },
    { titre: "Ressources", segments: ressources, total: somme(ressources) },
  ];
});

const plafondBilan = computed(() => Math.max(1, ...colonnesBilan.value.map((c) => c.total)));

const etapesSig = computed(() => {
  if (!tb.value) return [];
  const etapes = [
    { libelle: "Chiffre d'affaires", valeur: nombre(tb.value.chiffre_affaires.valeur) },
    { libelle: "Marge commerciale", valeur: nombre(tb.value.marge_commerciale.valeur) },
    { libelle: "Valeur ajoutée", valeur: nombre(tb.value.valeur_ajoutee.valeur) },
    { libelle: "Excédent brut d'exploitation", valeur: nombre(tb.value.excedent_brut_exploitation.valeur) },
    { libelle: "Résultat d'exploitation", valeur: nombre(tb.value.resultat_exploitation) },
    { libelle: "Résultat net", valeur: nombre(tb.value.resultat_net) },
  ];
  const max = Math.max(...etapes.map((e) => Math.abs(e.valeur)), 1);
  return etapes.map((e) => ({ ...e, largeur: Math.max(30, (Math.abs(e.valeur) / max) * 100) }));
});
</script>

<template>
  <div v-if="peutVoir" class="space-y-6">
    <!-- En-tête -->
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 class="text-xl font-semibold text-text">Tableau de bord</h1>
        <p v-if="tb" class="text-xs text-text-muted">
          Du {{ tb.date_debut }} au {{ tb.date_fin }} — écritures validées uniquement
        </p>
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <select
          :value="exerciceAffiche"
          class="rounded-md border border-border px-3 py-1.5 text-sm text-text"
          @change="surChangementExercice"
        >
          <option v-if="!exercices?.length" value="">Exercice courant</option>
          <option v-for="e in exercices" :key="e.id" :value="e.id">{{ libelleExercice(e.date_fin) }}</option>
        </select>

      </div>
    </div>

    <p v-if="isLoading" class="text-sm text-text-muted">Chargement…</p>
    <div v-else-if="isError || !tb" class="rounded-lg border border-border bg-surface p-6 text-sm text-text-muted">
      Aucun tableau de bord à afficher : l'entreprise n'a pas encore d'exercice, ou la période choisie est invalide.
    </div>

    <template v-else>
      <!-- Ligne 1 : CA + marges -->
      <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div class="rounded-lg bg-surface-muted p-5">
          <p class="text-sm text-text-muted">Chiffre d'affaires cumulé {{ tb.annee }}</p>
          <p class="mt-4 text-xl font-semibold" :class="classeMontant(tb.chiffre_affaires.valeur)">
            {{ fcfa(tb.chiffre_affaires.valeur) }}
          </p>
          <p class="mt-4 text-xs" :class="classeVariation(tb.chiffre_affaires)">
            {{ texteComparaison(tb.chiffre_affaires) }}
          </p>
          <p v-if="tb.chiffre_affaires.valeur_n1 !== null" class="text-xs font-medium text-text">
            {{ fcfa(tb.chiffre_affaires.valeur_n1) }}
          </p>
        </div>

        <div
          v-for="carte in [
            { titre: 'Marge commerciale', ind: tb.marge_commerciale },
            { titre: 'Valeur ajoutée', ind: tb.valeur_ajoutee },
            { titre: 'Excédent brut d\'exploitation', ind: tb.excedent_brut_exploitation },
          ]"
          :key="carte.titre"
          class="rounded-lg border border-border bg-surface p-5 text-center"
        >
          <p class="text-sm font-semibold text-text">{{ carte.titre }}</p>
          <p class="mt-3 text-lg font-semibold" :class="nombre(carte.ind.valeur) < 0 ? 'text-danger' : 'text-primary'">
            {{ fcfa(carte.ind.valeur) }}
          </p>
          <div class="mt-3 h-2 overflow-hidden rounded-full bg-surface-muted">
            <div
              class="h-full rounded-full"
              :class="nombre(carte.ind.valeur) < 0 ? 'bg-danger' : 'bg-primary'"
              :style="{ width: `${nombre(carte.ind.valeur) < 0 ? 100 : partDuCa(carte.ind.valeur)}%` }"
            />
          </div>
          <p class="mt-3 text-xs" :class="classeVariation(carte.ind)">{{ texteComparaison(carte.ind) }}</p>
        </div>
      </div>

      <!-- Ligne 2 : trésorerie, CAF, circulants, FR/BFR -->
      <div class="grid gap-4 lg:grid-cols-2 xl:grid-cols-4">
        <div class="space-y-4">
          <div class="rounded-lg border border-border bg-surface p-5 text-center">
            <p class="text-sm font-semibold text-text">Trésorerie</p>
            <p class="mt-2 text-lg font-semibold" :class="classeMontant(tb.tresorerie)">{{ fcfa(tb.tresorerie) }}</p>
          </div>
          <div class="rounded-lg border border-border bg-surface p-5 text-center">
            <p class="text-sm font-semibold text-text">Capacité d'autofinancement</p>
            <p class="mt-2 text-lg font-semibold" :class="classeMontant(tb.capacite_autofinancement)">
              {{ fcfa(tb.capacite_autofinancement) }}
            </p>
          </div>
        </div>

        <div class="rounded-lg bg-success-bg p-5">
          <p class="text-center text-sm font-semibold text-text">Actif circulant</p>
          <p class="mt-2 text-center text-lg font-semibold text-text">{{ fcfa(tb.actif_circulant.total) }}</p>
          <dl class="mt-4 space-y-1 text-xs text-text-muted">
            <div class="flex justify-between gap-2"><dt>Créances clients</dt><dd class="font-medium text-text">{{ fcfa(tb.actif_circulant.creances_clients) }}</dd></div>
            <div class="flex justify-between gap-2"><dt>Autres créances</dt><dd class="font-medium text-text">{{ fcfa(tb.actif_circulant.autres_creances) }}</dd></div>
            <div class="flex justify-between gap-2"><dt>Stock</dt><dd class="font-medium text-text">{{ fcfa(tb.actif_circulant.stocks) }}</dd></div>
          </dl>
        </div>

        <div class="rounded-lg bg-danger-bg p-5">
          <p class="text-center text-sm font-semibold text-text">Passif circulant</p>
          <p class="mt-2 text-center text-lg font-semibold text-text">{{ fcfa(tb.passif_circulant.total) }}</p>
          <dl class="mt-4 space-y-1 text-xs text-text-muted">
            <div class="flex justify-between gap-2"><dt>Dettes fournisseurs</dt><dd class="font-medium text-text">{{ fcfa(tb.passif_circulant.dettes_fournisseurs) }}</dd></div>
            <div class="flex justify-between gap-2"><dt>Dettes fiscales</dt><dd class="font-medium text-text">{{ fcfa(tb.passif_circulant.dettes_fiscales) }}</dd></div>
            <div class="flex justify-between gap-2"><dt>Dettes sociales</dt><dd class="font-medium text-text">{{ fcfa(tb.passif_circulant.dettes_sociales) }}</dd></div>
            <div class="flex justify-between gap-2"><dt>Autres dettes</dt><dd class="font-medium text-text">{{ fcfa(tb.passif_circulant.autres_dettes) }}</dd></div>
          </dl>
        </div>

        <div class="rounded-lg border border-border bg-surface p-5">
          <p class="text-xs text-text-muted">FR : Fonds de roulement</p>
          <p class="text-xs text-text-muted">BFR : Besoin en fonds de roulement</p>
          <div class="mt-4 space-y-3">
            <div v-for="l in lignesFrBfr" :key="l.sigle" class="flex items-center gap-3">
              <span class="w-8 text-xs text-text-muted">{{ l.sigle }}</span>
              <div class="flex-1">
                <div
                  class="rounded px-2 py-2 text-center text-xs font-medium text-white"
                  :class="l.valeur < 0 ? 'bg-[#c4264f]' : 'bg-[#2f9e5b]'"
                  :style="{ width: `${l.largeur}%` }"
                >
                  {{ fcfa(l.valeur) }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Ligne 3 : bilan fonctionnel + SIG -->
      <div class="grid gap-4 xl:grid-cols-3">
        <div class="rounded-lg border border-border bg-surface p-5 xl:col-span-2">
          <h2 class="text-base font-semibold text-text">Bilan fonctionnel</h2>
          <p class="text-sm text-text-muted">Le bilan fonctionnel de votre activité durant l'exercice</p>

          <div class="mt-6 grid grid-cols-2 gap-8">
            <div v-for="col in colonnesBilan" :key="col.titre" class="flex flex-col items-center">
              <div class="flex h-56 w-full max-w-[9rem] flex-col-reverse overflow-hidden rounded-t bg-surface-muted">
                <div
                  v-for="s in col.segments"
                  :key="s.libelle"
                  :class="s.couleur"
                  :style="{ height: `${(Math.max(0, s.valeur) / plafondBilan) * 100}%` }"
                  :title="`${s.libelle} : ${fcfa(s.valeur)}`"
                />
              </div>
              <p class="mt-2 text-sm font-medium text-text">{{ col.titre }}</p>
              <p class="text-xs text-text-muted">{{ fcfa(col.total) }}</p>
              <ul class="mt-3 w-full space-y-1 text-xs">
                <li v-for="s in col.segments" :key="s.libelle" class="flex items-center justify-between gap-2">
                  <span class="flex items-center gap-2 text-text-muted">
                    <span class="h-2.5 w-2.5 rounded-sm" :class="s.couleur" />{{ s.libelle }}
                  </span>
                  <span class="font-medium" :class="s.valeur < 0 ? 'text-danger' : 'text-text'">{{ fcfa(s.valeur) }}</span>
                </li>
              </ul>
            </div>
          </div>
        </div>

        <div class="rounded-lg border border-border bg-surface p-5">
          <h2 class="text-base font-semibold text-text">Soldes intermédiaires de gestion</h2>
          <p class="text-sm text-text-muted">Votre solde intermédiaire de gestion de l'exercice</p>
          <div class="mt-6 space-y-2">
            <div
              v-for="e in etapesSig"
              :key="e.libelle"
              class="mx-auto rounded px-3 py-2 text-center text-xs font-semibold text-white"
              :class="e.valeur < 0 ? 'bg-danger' : 'bg-[#c4264f]'"
              :style="{ width: `${e.largeur}%` }"
            >
              {{ e.libelle }} : {{ fcfa(e.valeur) }}
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>

  <div v-else>
    <h1 class="text-lg font-semibold text-text">
      Bonjour{{ utilisateur ? `, ${utilisateur.prenom}` : "" }}
    </h1>
    <p v-if="contexteActif" class="mt-1 text-sm text-text-muted">
      {{ contexteActif.entreprise.raison_sociale }} — rôle {{ contexteActif.role.libelle }}
    </p>
  </div>
</template>