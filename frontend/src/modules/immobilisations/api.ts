/**
 * Accès réseau du module immobilisations. Comme tiers/tresorerie/
 * comptabilite, pas de `useCrudRessource` générique : la génération d'une
 * ligne de plan d'amortissement, la génération de son écriture de
 * dotation, la cession et la réforme sont toutes des actions dédiées qui
 * ne rentrent pas dans un CRUD classique.
 */
import { computed, type Ref } from "vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";

import { apiClient } from "@/core/api/client";
import type { EcritureLecture } from "@/modules/comptabilite/types";
import type {
  CessionDemande,
  GenerationEcritureDemande,
  Immobilisation,
  ImmobilisationCreation,
  ImmobilisationMiseAJour,
  LigneAmortissement,
  ReformeDemande,
} from "./types";

function racine(entrepriseId: Ref<string | null | undefined>): string {
  return `/immobilisations/entreprises/${entrepriseId.value}`;
}

export function useListeImmobilisations(
  entrepriseId: Ref<string | null | undefined>,
  statut: Ref<string | null>,
) {
  return useQuery({
    queryKey: computed(() => ["immobilisations", entrepriseId.value, statut.value]),
    queryFn: async () => {
      const { data } = await apiClient.get<Immobilisation[]>(`${racine(entrepriseId)}/immobilisations`, {
        params: { statut: statut.value || undefined },
      });
      return data;
    },
    enabled: () => !!entrepriseId.value,
  });
}

export function useImmobilisation(
  entrepriseId: Ref<string | null | undefined>,
  immobilisationId: Ref<string | null>,
) {
  return useQuery({
    queryKey: ["immobilisation-detail", entrepriseId, immobilisationId],
    queryFn: async () => {
      const { data } = await apiClient.get<Immobilisation>(
        `${racine(entrepriseId)}/immobilisations/${immobilisationId.value}`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value && !!immobilisationId.value,
  });
}

export function useLignesAmortissement(
  entrepriseId: Ref<string | null | undefined>,
  immobilisationId: Ref<string | null>,
) {
  return useQuery({
    queryKey: ["lignes-amortissement", entrepriseId, immobilisationId],
    queryFn: async () => {
      const { data } = await apiClient.get<LigneAmortissement[]>(
        `${racine(entrepriseId)}/immobilisations/${immobilisationId.value}/lignes-amortissement`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value && !!immobilisationId.value,
  });
}

export function useMutationsImmobilisations(entrepriseId: Ref<string | null | undefined>) {
  const queryClient = useQueryClient();
  const invalider = () => queryClient.invalidateQueries({ queryKey: ["immobilisations"] });
  // Clé partielle volontaire, même raisonnement que les autres modules :
  // le matching par préfixe de invalidateQueries suffit.
  const invaliderDetail = () =>
    queryClient.invalidateQueries({ queryKey: ["immobilisation-detail"] });
  const invaliderLignes = () => queryClient.invalidateQueries({ queryKey: ["lignes-amortissement"] });

  const creer = useMutation({
    mutationFn: async (donnees: ImmobilisationCreation) => {
      const { data } = await apiClient.post<Immobilisation>(
        `${racine(entrepriseId)}/immobilisations`,
        donnees,
      );
      return data;
    },
    onSuccess: invalider,
  });

  const modifier = useMutation({
    mutationFn: async ({ id, donnees }: { id: string; donnees: ImmobilisationMiseAJour }) => {
      const { data } = await apiClient.patch<Immobilisation>(
        `${racine(entrepriseId)}/immobilisations/${id}`,
        donnees,
      );
      return data;
    },
    onSuccess: () => {
      invalider();
      invaliderDetail();
    },
  });

  const genererLigneAmortissement = useMutation({
    mutationFn: async ({ immobilisationId, exerciceId }: { immobilisationId: string; exerciceId: string }) => {
      const { data } = await apiClient.post<LigneAmortissement>(
        `${racine(entrepriseId)}/immobilisations/${immobilisationId}/lignes-amortissement/${exerciceId}`,
      );
      return data;
    },
    onSuccess: invaliderLignes,
  });

  const genererEcritureAmortissement = useMutation({
    mutationFn: async ({ ligneId, donnees }: { ligneId: string; donnees: GenerationEcritureDemande }) => {
      const { data } = await apiClient.post<EcritureLecture>(
        `${racine(entrepriseId)}/lignes-amortissement/${ligneId}/generer-ecriture`,
        donnees,
      );
      return data;
    },
    onSuccess: invaliderLignes,
  });

  const ceder = useMutation({
    mutationFn: async ({ id, donnees }: { id: string; donnees: CessionDemande }) => {
      const { data } = await apiClient.post<Immobilisation>(
        `${racine(entrepriseId)}/immobilisations/${id}/ceder`,
        donnees,
      );
      return data;
    },
    onSuccess: () => {
      invalider();
      invaliderDetail();
    },
  });

  const reformer = useMutation({
    mutationFn: async ({ id, donnees }: { id: string; donnees: ReformeDemande }) => {
      const { data } = await apiClient.post<Immobilisation>(
        `${racine(entrepriseId)}/immobilisations/${id}/reformer`,
        donnees,
      );
      return data;
    },
    onSuccess: () => {
      invalider();
      invaliderDetail();
    },
  });

  return { creer, modifier, genererLigneAmortissement, genererEcritureAmortissement, ceder, reformer };
}
