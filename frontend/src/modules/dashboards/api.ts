/**
 * Accès réseau du module dashboards : trois routes de lecture seule,
 * toutes scopées à un exercice. Pas de mutation (le module ne persiste
 * rien, voir la note de tête de service.py).
 */
import type { Ref } from "vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";

import { apiClient } from "@/core/api/client";
import type {
  BalanceAuxiliaire,
  BalanceDetaillee,
  Bilan,
  CompteResultatDetaille,
  GrandLivreGeneral,
  CompteResultatSommaire,
  LigneBalance,
  LigneBalanceComparee,
  LigneEcheance,
  LigneGrandLivre,
  PrevisionTresorerie,
  ResultatDetectionAlertes,
  TableauBord,
  TableauComptabilite,
  TableauDirection,
  TrancheAgee,
  TypeTiersEcheancier,
} from "./types";

function racine(entrepriseId: Ref<string | null | undefined>): string {
  return `/dashboards/entreprises/${entrepriseId.value}`;
}

export function useBalanceGenerale(
  entrepriseId: Ref<string | null | undefined>,
  exerciceId: Ref<string | null>,
) {
  return useQuery({
    queryKey: ["balance-generale", entrepriseId, exerciceId],
    queryFn: async () => {
      const { data } = await apiClient.get<LigneBalance[]>(
        `${racine(entrepriseId)}/exercices/${exerciceId.value}/balance-generale`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value && !!exerciceId.value,
  });
}

export function useBalanceCompareeN1(
  entrepriseId: Ref<string | null | undefined>,
  exerciceId: Ref<string | null>,
) {
  return useQuery({
    queryKey: ["balance-comparee-n1", entrepriseId, exerciceId],
    queryFn: async () => {
      const { data } = await apiClient.get<LigneBalanceComparee[]>(
        `${racine(entrepriseId)}/exercices/${exerciceId.value}/balance-comparee-n1`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value && !!exerciceId.value,
  });
}

export function useGrandLivre(
  entrepriseId: Ref<string | null | undefined>,
  exerciceId: Ref<string | null>,
  compteId: Ref<string | null>,
) {
  return useQuery({
    queryKey: ["grand-livre", entrepriseId, exerciceId, compteId],
    queryFn: async () => {
      const { data } = await apiClient.get<LigneGrandLivre[]>(
        `${racine(entrepriseId)}/exercices/${exerciceId.value}/comptes/${compteId.value}/grand-livre`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value && !!exerciceId.value && !!compteId.value,
  });
}

export function useCompteResultatSommaire(
  entrepriseId: Ref<string | null | undefined>,
  exerciceId: Ref<string | null>,
) {
  return useQuery({
    queryKey: ["compte-resultat-sommaire", entrepriseId, exerciceId],
    queryFn: async () => {
      const { data } = await apiClient.get<CompteResultatSommaire>(
        `${racine(entrepriseId)}/exercices/${exerciceId.value}/compte-resultat-sommaire`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value && !!exerciceId.value,
  });
}

export function useBilan(
  entrepriseId: Ref<string | null | undefined>,
  exerciceId: Ref<string | null>,
) {
  return useQuery({
    queryKey: ["bilan", entrepriseId, exerciceId],
    queryFn: async () => {
      const { data } = await apiClient.get<Bilan>(
        `${racine(entrepriseId)}/exercices/${exerciceId.value}/bilan`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value && !!exerciceId.value,
  });
}

export function useCompteResultatDetaille(
  entrepriseId: Ref<string | null | undefined>,
  exerciceId: Ref<string | null>,
) {
  return useQuery({
    queryKey: ["compte-resultat-detaille", entrepriseId, exerciceId],
    queryFn: async () => {
      const { data } = await apiClient.get<CompteResultatDetaille>(
        `${racine(entrepriseId)}/exercices/${exerciceId.value}/compte-resultat-detaille`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value && !!exerciceId.value,
  });
}

export function useEcheancier(
  entrepriseId: Ref<string | null | undefined>,
  typeTiers: Ref<TypeTiersEcheancier>,
) {
  return useQuery({
    queryKey: ["echeancier", entrepriseId, typeTiers],
    queryFn: async () => {
      const { data } = await apiClient.get<LigneEcheance[]>(
        `${racine(entrepriseId)}/echeancier/${typeTiers.value}`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value,
  });
}

export function useBalanceAgee(
  entrepriseId: Ref<string | null | undefined>,
  typeTiers: Ref<TypeTiersEcheancier>,
) {
  return useQuery({
    queryKey: ["balance-agee", entrepriseId, typeTiers],
    queryFn: async () => {
      const { data } = await apiClient.get<TrancheAgee[]>(
        `${racine(entrepriseId)}/balance-agee/${typeTiers.value}`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value,
  });
}

/** Prévision de trésorerie : solde bancaire actuel projeté sur un
 * horizon glissant (en jours) à partir des échéances clients/fournisseurs
 * connues. `horizonJours` est une Ref pour permettre à la page de changer
 * l'horizon (30/60/90/180 jours) sans recréer le hook. */
export function usePrevisionTresorerie(
  entrepriseId: Ref<string | null | undefined>,
  horizonJours: Ref<number>,
) {
  return useQuery({
    queryKey: ["prevision-tresorerie", entrepriseId, horizonJours],
    queryFn: async () => {
      const { data } = await apiClient.get<PrevisionTresorerie>(
        `${racine(entrepriseId)}/prevision-tresorerie`,
        { params: { horizon_jours: horizonJours.value } },
      );
      return data;
    },
    enabled: () => !!entrepriseId.value,
  });
}

/** Tableau de bord d'accueil. `exerciceId` null = exercice courant (choisi
 * par le backend) ; `dateDebut`/`dateFin` vides = exercice entier. */
export function useTableauBord(
  entrepriseId: Ref<string | null | undefined>,
  exerciceId: Ref<string | null>,
  dateDebut: Ref<string | null>,
  dateFin: Ref<string | null>,
) {
  return useQuery({
    queryKey: ["tableau-bord", entrepriseId, exerciceId, dateDebut, dateFin],
    queryFn: async () => {
      const params: Record<string, string> = {};
      if (exerciceId.value) params.exercice_id = exerciceId.value;
      if (dateDebut.value) params.date_debut = dateDebut.value;
      if (dateFin.value) params.date_fin = dateFin.value;
      const { data } = await apiClient.get<TableauBord>(`${racine(entrepriseId)}/tableau-bord`, { params });
      return data;
    },
    enabled: () => !!entrepriseId.value,
    retry: false,
  });
}

// --- Pilotage Direction / Comptabilité (Étape 5) --------------------------

export function useTableauDirection(entrepriseId: Ref<string | null | undefined>) {
  return useQuery({
    queryKey: ["tableau-direction", entrepriseId],
    queryFn: async () => {
      const { data } = await apiClient.get<TableauDirection>(`${racine(entrepriseId)}/tableau-direction`);
      return data;
    },
    enabled: () => !!entrepriseId.value,
  });
}

export function useTableauComptabilite(entrepriseId: Ref<string | null | undefined>) {
  return useQuery({
    queryKey: ["tableau-comptabilite", entrepriseId],
    queryFn: async () => {
      const { data } = await apiClient.get<TableauComptabilite>(
        `${racine(entrepriseId)}/tableau-comptabilite`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value,
  });
}

/** Déclenche `POST .../detecter-alertes` (module notifications, pas
 * dashboards — mais côté frontend l'action vit ici, à côté des tableaux
 * qu'elle rafraîchit) et invalide la cloche de notifications et les deux
 * tableaux ci-dessus, dont les compteurs peuvent changer après détection
 * (ex. une demande en attente qui vient de générer une alerte ne change
 * pas elle-même, mais le cabinet s'attend à voir la cloche se mettre à
 * jour immédiatement plutôt qu'au prochain polling). */
export function useMutationDetecterAlertes(entrepriseId: Ref<string | null | undefined>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await apiClient.post<ResultatDetectionAlertes>(
        `/notifications/entreprises/${entrepriseId.value}/detecter-alertes`,
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mes-notifications-compteur"] });
      queryClient.invalidateQueries({ queryKey: ["tableau-direction"] });
      queryClient.invalidateQueries({ queryKey: ["tableau-comptabilite"] });
    },
  });
}

/** Export Excel des états financiers (cahier des charges, section 9) —
 * même permission `dashboard.consulter` que le reste du module, pas de
 * mutation TanStack Query ici : un téléchargement de fichier n'a pas
 * d'état à invalider ni de cache à tenir, contrairement aux mutations
 * ci-dessus. */
export async function exporterEtatsFinanciers(
  entrepriseId: Ref<string | null | undefined>,
  exerciceId: string,
): Promise<void> {
  const reponse = await apiClient.get(
    `${racine(entrepriseId)}/exercices/${exerciceId}/etats-financiers/export`,
    { responseType: "blob" },
  );
  const url = window.URL.createObjectURL(new Blob([reponse.data]));
  const lien = window.document.createElement("a");
  lien.href = url;
  lien.download = `etats_financiers_${exerciceId}.xlsx`;
  lien.click();
  window.URL.revokeObjectURL(url);
}
// --- Balance générale à colonnes --------------------------------------------

function parametresBalance(
  dateDebut: string | null,
  dateFin: string | null,
  classe: string | null,
): Record<string, string> {
  const params: Record<string, string> = {};
  if (dateDebut) params.date_debut = dateDebut;
  if (dateFin) params.date_fin = dateFin;
  if (classe) params.classes = classe;
  return params;
}

export function useBalanceDetaillee(
  entrepriseId: Ref<string | null | undefined>,
  exerciceId: Ref<string | null>,
  dateDebut: Ref<string | null>,
  dateFin: Ref<string | null>,
  classe: Ref<string | null>,
) {
  return useQuery({
    queryKey: ["balance-detaillee", entrepriseId, exerciceId, dateDebut, dateFin, classe],
    queryFn: async () => {
      const { data } = await apiClient.get<BalanceDetaillee>(
        `${racine(entrepriseId)}/exercices/${exerciceId.value}/balance-detaillee`,
        { params: parametresBalance(dateDebut.value, dateFin.value, classe.value) },
      );
      return data;
    },
    enabled: () => !!entrepriseId.value && !!exerciceId.value,
    retry: false,
  });
}

/** Télécharge la balance en Excel, avec les mêmes filtres que l'écran. */
export async function exporterBalanceDetaillee(
  entrepriseId: Ref<string | null | undefined>,
  exerciceId: string,
  dateDebut: string | null,
  dateFin: string | null,
  classe: string | null,
): Promise<void> {
  const reponse = await apiClient.get(
    `${racine(entrepriseId)}/exercices/${exerciceId}/balance-detaillee/export`,
    { params: parametresBalance(dateDebut, dateFin, classe), responseType: "blob" },
  );
  const url = window.URL.createObjectURL(new Blob([reponse.data]));
  const lien = window.document.createElement("a");
  lien.href = url;
  lien.download = `balance_generale_${dateFin ?? exerciceId}.xlsx`;
  lien.click();
  window.URL.revokeObjectURL(url);
}

// --- Grand livre général -------------------------------------------------------

export interface FiltresGrandLivre {
  dateDebut: string | null;
  dateFin: string | null;
  compteDebut: string;
  compteFin: string;
  journalId: string | null;
}

function parametresGrandLivre(f: FiltresGrandLivre): Record<string, string> {
  const params: Record<string, string> = {};
  if (f.dateDebut) params.date_debut = f.dateDebut;
  if (f.dateFin) params.date_fin = f.dateFin;
  if (f.compteDebut.trim()) params.compte_debut = f.compteDebut.trim();
  if (f.compteFin.trim()) params.compte_fin = f.compteFin.trim();
  if (f.journalId) params.journal_id = f.journalId;
  return params;
}

export function useGrandLivreGeneral(
  entrepriseId: Ref<string | null | undefined>,
  exerciceId: Ref<string | null>,
  filtres: Ref<FiltresGrandLivre>,
) {
  return useQuery({
    queryKey: ["grand-livre-general", entrepriseId, exerciceId, filtres],
    queryFn: async () => {
      const { data } = await apiClient.get<GrandLivreGeneral>(
        `${racine(entrepriseId)}/exercices/${exerciceId.value}/grand-livre-general`,
        { params: parametresGrandLivre(filtres.value) },
      );
      return data;
    },
    enabled: () => !!entrepriseId.value && !!exerciceId.value,
    retry: false,
  });
}

/** Télécharge le grand livre en Excel, avec les mêmes filtres que l'écran. */
export async function exporterGrandLivreGeneral(
  entrepriseId: Ref<string | null | undefined>,
  exerciceId: string,
  filtres: FiltresGrandLivre,
): Promise<void> {
  const reponse = await apiClient.get(
    `${racine(entrepriseId)}/exercices/${exerciceId}/grand-livre-general/export`,
    { params: parametresGrandLivre(filtres), responseType: "blob" },
  );
  const url = window.URL.createObjectURL(new Blob([reponse.data]));
  const lien = window.document.createElement("a");
  lien.href = url;
  lien.download = `grand_livre_${filtres.dateFin ?? exerciceId}.xlsx`;
  lien.click();
  window.URL.revokeObjectURL(url);
}

// --- Balance auxiliaire (comptes tiers 40/41) --------------------------------

export type RoleBalanceAuxiliaire = "client" | "fournisseur" | "tous";

function parametresAuxiliaire(
  dateDebut: string | null,
  dateFin: string | null,
  role: RoleBalanceAuxiliaire,
  recherche: string,
): Record<string, string> {
  const params: Record<string, string> = { role };
  if (dateDebut) params.date_debut = dateDebut;
  if (dateFin) params.date_fin = dateFin;
  if (recherche.trim()) params.recherche = recherche.trim();
  return params;
}

export function useBalanceAuxiliaire(
  entrepriseId: Ref<string | null | undefined>,
  exerciceId: Ref<string | null>,
  dateDebut: Ref<string | null>,
  dateFin: Ref<string | null>,
  role: Ref<RoleBalanceAuxiliaire>,
  recherche: Ref<string>,
) {
  return useQuery({
    queryKey: ["balance-auxiliaire", entrepriseId, exerciceId, dateDebut, dateFin, role, recherche],
    queryFn: async () => {
      const { data } = await apiClient.get<BalanceAuxiliaire>(
        `${racine(entrepriseId)}/exercices/${exerciceId.value}/balance-auxiliaire`,
        { params: parametresAuxiliaire(dateDebut.value, dateFin.value, role.value, recherche.value) },
      );
      return data;
    },
    enabled: () => !!entrepriseId.value && !!exerciceId.value,
    retry: false,
  });
}

/** Télécharge la balance auxiliaire en Excel, avec les filtres de l'écran. */
export async function exporterBalanceAuxiliaire(
  entrepriseId: Ref<string | null | undefined>,
  exerciceId: string,
  dateDebut: string | null,
  dateFin: string | null,
  role: RoleBalanceAuxiliaire,
  recherche: string,
): Promise<void> {
  const reponse = await apiClient.get(
    `${racine(entrepriseId)}/exercices/${exerciceId}/balance-auxiliaire/export`,
    { params: parametresAuxiliaire(dateDebut, dateFin, role, recherche), responseType: "blob" },
  );
  const url = window.URL.createObjectURL(new Blob([reponse.data]));
  const lien = window.document.createElement("a");
  lien.href = url;
  lien.download = `balance_auxiliaire_${role}_${dateFin ?? exerciceId}.xlsx`;
  lien.click();
  window.URL.revokeObjectURL(url);
}