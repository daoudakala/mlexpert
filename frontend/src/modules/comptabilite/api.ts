import { computed, type Ref } from "vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";

import { apiClient } from "@/core/api/client";
import type {
  AppliquerModeleDonnees,
  Compte,
  CompteCreation,
  CompteImportResultat,
  EcritureAvecLignes,
  EcritureCreation,
  EcritureDuplication,
  EcritureImportResultat,
  EcritureLecture,
  EcritureMiseAJour,
  EcritureExtourne,
  EcritureRecurrenteAvecLignes,
  EcritureRecurrenteCreation,
  EcritureRecurrenteMiseAJour,
  GenerationEcheancesDemande,
  GenerationEcheancesResultat,
  Journal,
  JournalCreation,
  LettrageDemande,
  LettrageReponse,
  LigneLettrage,
  ModeleEcritureAvecLignes,
  ModeleEcritureCreation,
  ModeleEcritureMiseAJour,
} from "./types";

/** Les comptes éligibles comme compte collectif d'un tiers (compte lettrable
 * + est_collectif) — voir GET /comptabilite/entreprises/{id}/comptes/collectifs. */
export function useComptesCollectifs(entrepriseId: Ref<string | null | undefined>) {
  return useQuery({
    queryKey: ["comptes-collectifs", entrepriseId],
    queryFn: async () => {
      const { data } = await apiClient.get<Compte[]>(
        `/comptabilite/entreprises/${entrepriseId.value}/comptes/collectifs`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value,
  });
}

export interface FiltresComptes {
  recherche?: string | null;
  classe?: number | null;
  limite?: number;
  decalage?: number;
}

/** Tout le plan comptable de l'entreprise (actifs par défaut) — utilisé
 * pour choisir le compte comptable d'un compte bancaire (module trésorerie)
 * et par toutes les listes déroulantes de choix de compte ailleurs dans
 * l'app. `filtres` est optionnel : un appel sans second argument se
 * comporte exactement comme avant (liste complète, jusqu'à 1000 comptes,
 * pas de recherche) — seule `ComptesListe.vue` (page de recherche
 * paginée du plan comptable) passe une recherche et une pagination. */
export function useComptesEntreprise(
  entrepriseId: Ref<string | null | undefined>,
  filtres: Ref<FiltresComptes> = computed(() => ({})) as Ref<FiltresComptes>,
) {
  return useQuery({
    queryKey: computed(() => ["comptes-entreprise", entrepriseId.value, filtres.value]),
    queryFn: async () => {
      const { data } = await apiClient.get<Compte[]>(
        `/comptabilite/entreprises/${entrepriseId.value}/comptes`,
        {
          params: {
            recherche: filtres.value.recherche || undefined,
            classe: filtres.value.classe ?? undefined,
            limite: filtres.value.limite ?? 1000,
            decalage: filtres.value.decalage ?? 0,
          },
        },
      );
      return data;
    },
    enabled: () => !!entrepriseId.value,
  });
}

/** Les journaux de l'entreprise (actifs par défaut) — utilisé pour choisir
 * le journal d'un compte bancaire (module trésorerie). */
export function useJournaux(
  entrepriseId: Ref<string | null | undefined>,
  actifsSeulement: Ref<boolean> = computed(() => true) as Ref<boolean>,
) {
  return useQuery({
    queryKey: computed(() => ["journaux", entrepriseId.value, actifsSeulement.value]),
    queryFn: async () => {
      const { data } = await apiClient.get<Journal[]>(
        `/comptabilite/entreprises/${entrepriseId.value}/journaux`,
        { params: { actifs_seulement: actifsSeulement.value } },
      );
      return data;
    },
    enabled: () => !!entrepriseId.value,
  });
}

function racineCompta(entrepriseId: Ref<string | null | undefined>): string {
  return `/comptabilite/entreprises/${entrepriseId.value}`;
}

// --- Plan comptable (extensions propres à l'entreprise) ----------------------

export function useMutationsComptes(entrepriseId: Ref<string | null | undefined>) {
  const queryClient = useQueryClient();
  const invalider = () => {
    queryClient.invalidateQueries({ queryKey: ["comptes-entreprise"] });
    queryClient.invalidateQueries({ queryKey: ["comptes-collectifs"] });
  };

  const creer = useMutation({
    mutationFn: async (donnees: CompteCreation) => {
      const { data } = await apiClient.post<Compte>(`${racineCompta(entrepriseId)}/comptes`, donnees);
      return data;
    },
    onSuccess: invalider,
  });

  const desactiver = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.post(`${racineCompta(entrepriseId)}/comptes/${id}/desactiver`);
    },
    onSuccess: invalider,
  });

  // Import en masse (CSV/Excel, voir ComptesListe.vue) : upload multipart,
  // comme le dépôt de document (`documents/api.ts`) — axios fixe lui-même
  // le Content-Type multipart/form-data à partir du FormData.
  const importer = useMutation({
    mutationFn: async (fichier: File) => {
      const formulaire = new FormData();
      formulaire.append("fichier", fichier);
      const { data } = await apiClient.post<CompteImportResultat>(
        `${racineCompta(entrepriseId)}/comptes/importer`,
        formulaire,
      );
      return data;
    },
    onSuccess: invalider,
  });

  return { creer, desactiver, importer };
}

// --- À-nouveaux ------------------------------------------------------------

export function useMutationGenererANouveaux(entrepriseId: Ref<string | null | undefined>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (exerciceId: string) => {
      const { data } = await apiClient.post<EcritureLecture>(
        `${racineCompta(entrepriseId)}/exercices/${exerciceId}/a-nouveaux`,
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ecritures"] });
      queryClient.invalidateQueries({ queryKey: ["journaux"] });
    },
  });
}

// --- Journaux ------------------------------------------------------------------

export function useMutationsJournaux(entrepriseId: Ref<string | null | undefined>) {
  const queryClient = useQueryClient();
  const invalider = () => queryClient.invalidateQueries({ queryKey: ["journaux"] });

  const creer = useMutation({
    mutationFn: async (donnees: JournalCreation) => {
      const { data } = await apiClient.post<Journal>(`${racineCompta(entrepriseId)}/journaux`, donnees);
      return data;
    },
    onSuccess: invalider,
  });

  const desactiver = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.post(`${racineCompta(entrepriseId)}/journaux/${id}/desactiver`);
    },
    onSuccess: invalider,
  });

  return { creer, desactiver };
}

// --- Modèles d'écriture (saisie par modèle) ---------------------------------
// Un modèle fige le compte et le sens de chaque ligne ; le montant se
// saisit toujours au moment de l'appliquer (voir types.ts).

export function useModelesEcriture(
  entrepriseId: Ref<string | null | undefined>,
  actifsSeulement: Ref<boolean> = computed(() => true) as Ref<boolean>,
) {
  return useQuery({
    queryKey: computed(() => ["modeles-ecriture", entrepriseId.value, actifsSeulement.value]),
    queryFn: async () => {
      const { data } = await apiClient.get<ModeleEcritureAvecLignes[]>(
        `${racineCompta(entrepriseId)}/modeles-ecriture`,
        { params: { actifs_seulement: actifsSeulement.value } },
      );
      return data;
    },
    enabled: () => !!entrepriseId.value,
  });
}

export function useModeleEcriture(
  entrepriseId: Ref<string | null | undefined>,
  modeleId: Ref<string | null>,
) {
  return useQuery({
    queryKey: ["modele-ecriture-detail", entrepriseId, modeleId],
    queryFn: async () => {
      const { data } = await apiClient.get<ModeleEcritureAvecLignes>(
        `${racineCompta(entrepriseId)}/modeles-ecriture/${modeleId.value}`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value && !!modeleId.value,
  });
}

export function useMutationsModelesEcriture(entrepriseId: Ref<string | null | undefined>) {
  const queryClient = useQueryClient();
  const invalider = () => queryClient.invalidateQueries({ queryKey: ["modeles-ecriture"] });
  const invaliderDetail = () =>
    queryClient.invalidateQueries({ queryKey: ["modele-ecriture-detail"] });

  const creer = useMutation({
    mutationFn: async (donnees: ModeleEcritureCreation) => {
      const { data } = await apiClient.post<ModeleEcritureAvecLignes>(
        `${racineCompta(entrepriseId)}/modeles-ecriture`,
        donnees,
      );
      return data;
    },
    onSuccess: invalider,
  });

  const modifier = useMutation({
    mutationFn: async ({ id, donnees }: { id: string; donnees: ModeleEcritureMiseAJour }) => {
      const { data } = await apiClient.patch<ModeleEcritureAvecLignes>(
        `${racineCompta(entrepriseId)}/modeles-ecriture/${id}`,
        donnees,
      );
      return data;
    },
    onSuccess: () => {
      invalider();
      invaliderDetail();
    },
  });

  const desactiver = useMutation({
    mutationFn: async (id: string) => {
      const { data } = await apiClient.patch<ModeleEcritureAvecLignes>(
        `${racineCompta(entrepriseId)}/modeles-ecriture/${id}`,
        { actif: false },
      );
      return data;
    },
    onSuccess: () => {
      invalider();
      invaliderDetail();
    },
  });

  const appliquer = useMutation({
    mutationFn: async ({ id, donnees }: { id: string; donnees: AppliquerModeleDonnees }) => {
      const { data } = await apiClient.post<EcritureAvecLignes>(
        `${racineCompta(entrepriseId)}/modeles-ecriture/${id}/appliquer`,
        donnees,
      );
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ecritures"] }),
  });

  return { creer, modifier, desactiver, appliquer };
}

// --- Écritures récurrentes ---------------------------------------------------

export function useEcrituresRecurrentes(
  entrepriseId: Ref<string | null | undefined>,
  actifsSeulement: Ref<boolean> = computed(() => true) as Ref<boolean>,
) {
  return useQuery({
    queryKey: computed(() => ["ecritures-recurrentes", entrepriseId.value, actifsSeulement.value]),
    queryFn: async () => {
      const { data } = await apiClient.get<EcritureRecurrenteAvecLignes[]>(
        `${racineCompta(entrepriseId)}/ecritures-recurrentes`,
        { params: { actifs_seulement: actifsSeulement.value } },
      );
      return data;
    },
    enabled: () => !!entrepriseId.value,
  });
}

export function useEcritureRecurrente(
  entrepriseId: Ref<string | null | undefined>,
  ecritureRecurrenteId: Ref<string | null>,
) {
  return useQuery({
    queryKey: ["ecriture-recurrente-detail", entrepriseId, ecritureRecurrenteId],
    queryFn: async () => {
      const { data } = await apiClient.get<EcritureRecurrenteAvecLignes>(
        `${racineCompta(entrepriseId)}/ecritures-recurrentes/${ecritureRecurrenteId.value}`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value && !!ecritureRecurrenteId.value,
  });
}

export function useMutationsEcrituresRecurrentes(entrepriseId: Ref<string | null | undefined>) {
  const queryClient = useQueryClient();
  const invalider = () => queryClient.invalidateQueries({ queryKey: ["ecritures-recurrentes"] });
  const invaliderDetail = () =>
    queryClient.invalidateQueries({ queryKey: ["ecriture-recurrente-detail"] });

  const creer = useMutation({
    mutationFn: async (donnees: EcritureRecurrenteCreation) => {
      const { data } = await apiClient.post<EcritureRecurrenteAvecLignes>(
        `${racineCompta(entrepriseId)}/ecritures-recurrentes`,
        donnees,
      );
      return data;
    },
    onSuccess: invalider,
  });

  const modifier = useMutation({
    mutationFn: async ({ id, donnees }: { id: string; donnees: EcritureRecurrenteMiseAJour }) => {
      const { data } = await apiClient.patch<EcritureRecurrenteAvecLignes>(
        `${racineCompta(entrepriseId)}/ecritures-recurrentes/${id}`,
        donnees,
      );
      return data;
    },
    onSuccess: () => {
      invalider();
      invaliderDetail();
    },
  });

  const desactiver = useMutation({
    mutationFn: async (id: string) => {
      const { data } = await apiClient.patch<EcritureRecurrenteAvecLignes>(
        `${racineCompta(entrepriseId)}/ecritures-recurrentes/${id}`,
        { actif: false },
      );
      return data;
    },
    onSuccess: () => {
      invalider();
      invaliderDetail();
    },
  });

  const activer = useMutation({
    mutationFn: async (id: string) => {
      const { data } = await apiClient.patch<EcritureRecurrenteAvecLignes>(
        `${racineCompta(entrepriseId)}/ecritures-recurrentes/${id}`,
        { actif: true },
      );
      return data;
    },
    onSuccess: () => {
      invalider();
      invaliderDetail();
    },
  });

  const genererEcheances = useMutation({
    mutationFn: async ({ id, donnees }: { id: string; donnees: GenerationEcheancesDemande }) => {
      const { data } = await apiClient.post<GenerationEcheancesResultat>(
        `${racineCompta(entrepriseId)}/ecritures-recurrentes/${id}/generer`,
        donnees,
      );
      return data;
    },
    onSuccess: () => {
      invaliderDetail();
      invalider();
      queryClient.invalidateQueries({ queryKey: ["ecritures"] });
    },
  });

  return { creer, modifier, desactiver, activer, genererEcheances };
}

// --- Écritures -------------------------------------------------------------

export interface FiltresEcritures {
  journalId?: string | null;
  exerciceId?: string | null;
  statut?: string | null;
}

export function useListeEcritures(
  entrepriseId: Ref<string | null | undefined>,
  filtres: Ref<FiltresEcritures>,
) {
  return useQuery({
    queryKey: computed(() => ["ecritures", entrepriseId.value, filtres.value]),
    queryFn: async () => {
      const { data } = await apiClient.get<EcritureLecture[]>(`${racineCompta(entrepriseId)}/ecritures`, {
        params: {
          journal_id: filtres.value.journalId || undefined,
          exercice_id: filtres.value.exerciceId || undefined,
          statut: filtres.value.statut || undefined,
        },
      });
      return data;
    },
    enabled: () => !!entrepriseId.value,
  });
}

export function useEcriture(
  entrepriseId: Ref<string | null | undefined>,
  ecritureId: Ref<string | null>,
) {
  return useQuery({
    queryKey: ["ecriture-detail", entrepriseId, ecritureId],
    queryFn: async () => {
      const { data } = await apiClient.get<EcritureAvecLignes>(
        `${racineCompta(entrepriseId)}/ecritures/${ecritureId.value}`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value && !!ecritureId.value,
  });
}

export function useExournantes(
  entrepriseId: Ref<string | null | undefined>,
  ecritureId: Ref<string | null>,
) {
  return useQuery({
    queryKey: ["ecriture-extournantes", entrepriseId, ecritureId],
    queryFn: async () => {
      const { data } = await apiClient.get<EcritureLecture[]>(
        `${racineCompta(entrepriseId)}/ecritures/${ecritureId.value}/extournant`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value && !!ecritureId.value,
  });
}

export function useMutationsEcritures(entrepriseId: Ref<string | null | undefined>) {
  const queryClient = useQueryClient();
  const invalider = () => queryClient.invalidateQueries({ queryKey: ["ecritures"] });
  // Clé partielle volontaire, même raisonnement que tiers/api.ts et
  // tresorerie/api.ts : le matching par préfixe de invalidateQueries
  // suffit, pas besoin de reconstruire la clé exacte.
  const invaliderDetail = () => queryClient.invalidateQueries({ queryKey: ["ecriture-detail"] });

  const creer = useMutation({
    mutationFn: async (donnees: EcritureCreation) => {
      const { data } = await apiClient.post<EcritureAvecLignes>(
        `${racineCompta(entrepriseId)}/ecritures`,
        donnees,
      );
      return data;
    },
    onSuccess: invalider,
  });

  const modifier = useMutation({
    mutationFn: async ({ id, donnees }: { id: string; donnees: EcritureMiseAJour }) => {
      const { data } = await apiClient.patch<EcritureAvecLignes>(
        `${racineCompta(entrepriseId)}/ecritures/${id}`,
        donnees,
      );
      return data;
    },
    onSuccess: () => {
      invalider();
      invaliderDetail();
    },
  });

  const supprimer = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.post(`${racineCompta(entrepriseId)}/ecritures/${id}/supprimer`);
    },
    onSuccess: () => {
      invalider();
      invaliderDetail();
    },
  });

  const valider = useMutation({
    mutationFn: async (id: string) => {
      const { data } = await apiClient.post<EcritureLecture>(
        `${racineCompta(entrepriseId)}/ecritures/${id}/valider`,
      );
      return data;
    },
    onSuccess: () => {
      invalider();
      invaliderDetail();
    },
  });

  const dupliquer = useMutation({
    mutationFn: async ({ id, donnees }: { id: string; donnees: EcritureDuplication }) => {
      const { data } = await apiClient.post<EcritureAvecLignes>(
        `${racineCompta(entrepriseId)}/ecritures/${id}/dupliquer`,
        donnees,
      );
      return data;
    },
    onSuccess: invalider,
  });

  const extourner = useMutation({
    mutationFn: async ({ id, donnees }: { id: string; donnees: EcritureExtourne }) => {
      const { data } = await apiClient.post<EcritureAvecLignes>(
        `${racineCompta(entrepriseId)}/ecritures/${id}/extourner`,
        donnees,
      );
      return data;
    },
    onSuccess: () => {
      invalider();
      invaliderDetail();
    },
  });

  const importer = useMutation({
    mutationFn: async (fichier: File) => {
      const formulaire = new FormData();
      formulaire.append("fichier", fichier);
      const { data } = await apiClient.post<EcritureImportResultat>(
        `${racineCompta(entrepriseId)}/ecritures/importer`,
        formulaire,
      );
      return data;
    },
    onSuccess: invalider,
  });

  return { creer, modifier, supprimer, valider, dupliquer, extourner, importer };
}

// --- Lettrage manuel (comptes généraux / tiers) -----------------------------

export interface FiltresLignesLettrage {
  tiersId?: string | null;
  // undefined = toutes, true = seulement lettrées, false = seulement non
  // lettrées — voir ServiceComptabilite.lister_lignes_lettrage.
  lettrees?: boolean;
}

export function useLignesLettrage(
  entrepriseId: Ref<string | null | undefined>,
  compteId: Ref<string | null>,
  filtres: Ref<FiltresLignesLettrage>,
) {
  return useQuery({
    queryKey: computed(() => ["lignes-lettrage", entrepriseId.value, compteId.value, filtres.value]),
    queryFn: async () => {
      const { data } = await apiClient.get<LigneLettrage[]>(
        `${racineCompta(entrepriseId)}/comptes/${compteId.value}/lignes-lettrage`,
        {
          params: {
            tiers_id: filtres.value.tiersId || undefined,
            lettrees: filtres.value.lettrees,
          },
        },
      );
      return data;
    },
    enabled: () => !!entrepriseId.value && !!compteId.value,
  });
}

export function useMutationsLettrage(entrepriseId: Ref<string | null | undefined>) {
  const queryClient = useQueryClient();
  const invalider = () => queryClient.invalidateQueries({ queryKey: ["lignes-lettrage"] });

  const lettrer = useMutation({
    mutationFn: async (donnees: LettrageDemande) => {
      const { data } = await apiClient.post<LettrageReponse>(
        `${racineCompta(entrepriseId)}/lettrages`,
        donnees,
      );
      return data;
    },
    onSuccess: invalider,
  });

  const delettrer = useMutation({
    mutationFn: async (codeLettrage: string) => {
      await apiClient.post(`${racineCompta(entrepriseId)}/lettrages/annuler`, {
        code_lettrage: codeLettrage,
      });
    },
    onSuccess: invalider,
  });

  return { lettrer, delettrer };
}