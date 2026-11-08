/**
 * Accès réseau du module trésorerie. Comme `tiers/api.ts`, pas de
 * `useCrudRessource` générique : désactiver un compte bancaire et
 * rapprocher/annuler un rapprochement sont des actions dédiées (pas un
 * DELETE), et un relevé se crée/modifie sous un compte bancaire mais se
 * lit/modifie/supprime via une route au niveau entreprise — deux formes de
 * chemin que le générique ne couvrirait pas proprement.
 */
import { computed, type Ref } from "vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";

import { apiClient } from "@/core/api/client";
import type { LigneEcritureLecture } from "@/modules/comptabilite/types";
import type {
  AnnulationRapprochementDemande,
  CompteBancaire,
  CompteBancaireCreation,
  LigneReleveLecture,
  RapprochementDemande,
  RapprochementReponse,
  ReleveAvecLignes,
  ReleveCreation,
  ReleveLecture,
  ReleveMiseAJour,
} from "./types";

function racine(entrepriseId: Ref<string | null | undefined>): string {
  return `/tresorerie/entreprises/${entrepriseId.value}`;
}

// --- Comptes bancaires -------------------------------------------------------

export function useListeComptesBancaires(
  entrepriseId: Ref<string | null | undefined>,
  actifsSeulement: Ref<boolean>,
) {
  return useQuery({
    queryKey: computed(() => ["comptes-bancaires", entrepriseId.value, actifsSeulement.value]),
    queryFn: async () => {
      const { data } = await apiClient.get<CompteBancaire[]>(
        `${racine(entrepriseId)}/comptes-bancaires`,
        { params: { actifs_seulement: actifsSeulement.value } },
      );
      return data;
    },
    enabled: () => !!entrepriseId.value,
  });
}

export function useCompteBancaire(
  entrepriseId: Ref<string | null | undefined>,
  compteBancaireId: Ref<string | null>,
) {
  return useQuery({
    queryKey: ["compte-bancaire-detail", entrepriseId, compteBancaireId],
    queryFn: async () => {
      const { data } = await apiClient.get<CompteBancaire>(
        `${racine(entrepriseId)}/comptes-bancaires/${compteBancaireId.value}`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value && !!compteBancaireId.value,
  });
}

export function useLignesNonRapprochees(
  entrepriseId: Ref<string | null | undefined>,
  compteBancaireId: Ref<string | null>,
) {
  return useQuery({
    queryKey: ["lignes-non-rapprochees", entrepriseId, compteBancaireId],
    queryFn: async () => {
      const { data } = await apiClient.get<LigneReleveLecture[]>(
        `${racine(entrepriseId)}/comptes-bancaires/${compteBancaireId.value}/lignes-non-rapprochees`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value && !!compteBancaireId.value,
  });
}

export function useEcrituresCandidates(
  entrepriseId: Ref<string | null | undefined>,
  compteBancaireId: Ref<string | null>,
) {
  return useQuery({
    queryKey: ["ecritures-candidates", entrepriseId, compteBancaireId],
    queryFn: async () => {
      const { data } = await apiClient.get<LigneEcritureLecture[]>(
        `${racine(entrepriseId)}/comptes-bancaires/${compteBancaireId.value}/ecritures-candidates`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value && !!compteBancaireId.value,
  });
}

export function useMutationsComptesBancaires(entrepriseId: Ref<string | null | undefined>) {
  const queryClient = useQueryClient();
  const invalider = () => queryClient.invalidateQueries({ queryKey: ["comptes-bancaires"] });
  // Clé partielle volontaire, même raisonnement que tiers/api.ts : le
  // matching par préfixe de invalidateQueries suffit, pas besoin de
  // reconstruire la clé exacte (avec les refs déballées).
  const invaliderDetail = () =>
    queryClient.invalidateQueries({ queryKey: ["compte-bancaire-detail"] });

  const creer = useMutation({
    mutationFn: async (donnees: CompteBancaireCreation) => {
      const { data } = await apiClient.post<CompteBancaire>(
        `${racine(entrepriseId)}/comptes-bancaires`,
        donnees,
      );
      return data;
    },
    onSuccess: invalider,
  });

  const desactiver = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.post(`${racine(entrepriseId)}/comptes-bancaires/${id}/desactiver`);
    },
    onSuccess: () => {
      invalider();
      invaliderDetail();
    },
  });

  return { creer, desactiver };
}

// --- Relevés bancaires -------------------------------------------------------

export function useListeReleves(
  entrepriseId: Ref<string | null | undefined>,
  compteBancaireId: Ref<string | null>,
) {
  return useQuery({
    queryKey: ["releves", entrepriseId, compteBancaireId],
    queryFn: async () => {
      const { data } = await apiClient.get<ReleveLecture[]>(
        `${racine(entrepriseId)}/comptes-bancaires/${compteBancaireId.value}/releves`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value && !!compteBancaireId.value,
  });
}

export function useReleve(
  entrepriseId: Ref<string | null | undefined>,
  releveId: Ref<string | null>,
) {
  return useQuery({
    queryKey: ["releve-detail", entrepriseId, releveId],
    queryFn: async () => {
      const { data } = await apiClient.get<ReleveAvecLignes>(
        `${racine(entrepriseId)}/releves/${releveId.value}`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value && !!releveId.value,
  });
}

export function useMutationsReleves(entrepriseId: Ref<string | null | undefined>) {
  const queryClient = useQueryClient();
  const invalider = () => queryClient.invalidateQueries({ queryKey: ["releves"] });
  const invaliderDetail = () => queryClient.invalidateQueries({ queryKey: ["releve-detail"] });
  const invaliderRapprochement = () => {
    queryClient.invalidateQueries({ queryKey: ["lignes-non-rapprochees"] });
    queryClient.invalidateQueries({ queryKey: ["ecritures-candidates"] });
  };

  const creer = useMutation({
    mutationFn: async ({
      compteBancaireId,
      donnees,
    }: {
      compteBancaireId: string;
      donnees: ReleveCreation;
    }) => {
      const { data } = await apiClient.post<ReleveAvecLignes>(
        `${racine(entrepriseId)}/comptes-bancaires/${compteBancaireId}/releves`,
        donnees,
      );
      return data;
    },
    onSuccess: () => {
      invalider();
      invaliderRapprochement();
    },
  });

  const modifier = useMutation({
    mutationFn: async ({ id, donnees }: { id: string; donnees: ReleveMiseAJour }) => {
      const { data } = await apiClient.patch<ReleveAvecLignes>(
        `${racine(entrepriseId)}/releves/${id}`,
        donnees,
      );
      return data;
    },
    onSuccess: () => {
      invalider();
      invaliderDetail();
      invaliderRapprochement();
    },
  });

  const supprimer = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.post(`${racine(entrepriseId)}/releves/${id}/supprimer`);
    },
    onSuccess: () => {
      invalider();
      invaliderDetail();
      invaliderRapprochement();
    },
  });

  return { creer, modifier, supprimer };
}

// --- Rapprochement -----------------------------------------------------------

export function useMutationsRapprochement(entrepriseId: Ref<string | null | undefined>) {
  const queryClient = useQueryClient();
  const invaliderRapprochement = () => {
    queryClient.invalidateQueries({ queryKey: ["lignes-non-rapprochees"] });
    queryClient.invalidateQueries({ queryKey: ["ecritures-candidates"] });
    queryClient.invalidateQueries({ queryKey: ["releve-detail"] });
  };

  const rapprocher = useMutation({
    mutationFn: async ({
      compteBancaireId,
      donnees,
    }: {
      compteBancaireId: string;
      donnees: RapprochementDemande;
    }) => {
      const { data } = await apiClient.post<RapprochementReponse>(
        `${racine(entrepriseId)}/comptes-bancaires/${compteBancaireId}/rapprocher`,
        donnees,
      );
      return data;
    },
    onSuccess: invaliderRapprochement,
  });

  const annuler = useMutation({
    mutationFn: async (donnees: AnnulationRapprochementDemande) => {
      await apiClient.post(`${racine(entrepriseId)}/rapprochements/annuler`, donnees);
    },
    onSuccess: invaliderRapprochement,
  });

  return { rapprocher, annuler };
}
