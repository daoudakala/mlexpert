/**
 * Accès réseau du module provisions. Pas de `useCrudRessource` générique :
 * la dotation et la reprise sont des actions dédiées, comme la génération
 * d'une ligne d'amortissement ou la cession dans `immobilisations`.
 */
import { computed, type Ref } from "vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";

import { apiClient } from "@/core/api/client";
import type { EcritureLecture } from "@/modules/comptabilite/types";
import type {
  DotationDemande,
  MouvementProvision,
  Provision,
  ProvisionCreation,
  ProvisionMiseAJour,
  RepriseDemande,
} from "./types";

function racine(entrepriseId: Ref<string | null | undefined>): string {
  return `/provisions/entreprises/${entrepriseId.value}`;
}

export interface FiltresProvisions {
  typeProvision?: string | null;
  statut?: string | null;
}

export function useListeProvisions(
  entrepriseId: Ref<string | null | undefined>,
  filtres: Ref<FiltresProvisions>,
) {
  return useQuery({
    queryKey: computed(() => ["provisions", entrepriseId.value, filtres.value]),
    queryFn: async () => {
      const { data } = await apiClient.get<Provision[]>(`${racine(entrepriseId)}/provisions`, {
        params: {
          type_provision: filtres.value.typeProvision || undefined,
          statut: filtres.value.statut || undefined,
        },
      });
      return data;
    },
    enabled: () => !!entrepriseId.value,
  });
}

export function useProvision(
  entrepriseId: Ref<string | null | undefined>,
  provisionId: Ref<string | null>,
) {
  return useQuery({
    queryKey: ["provision-detail", entrepriseId, provisionId],
    queryFn: async () => {
      const { data } = await apiClient.get<Provision>(
        `${racine(entrepriseId)}/provisions/${provisionId.value}`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value && !!provisionId.value,
  });
}

export function useMouvementsProvision(
  entrepriseId: Ref<string | null | undefined>,
  provisionId: Ref<string | null>,
) {
  return useQuery({
    queryKey: ["mouvements-provision", entrepriseId, provisionId],
    queryFn: async () => {
      const { data } = await apiClient.get<MouvementProvision[]>(
        `${racine(entrepriseId)}/provisions/${provisionId.value}/mouvements`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value && !!provisionId.value,
  });
}

export function useMutationsProvisions(entrepriseId: Ref<string | null | undefined>) {
  const queryClient = useQueryClient();
  const invalider = () => queryClient.invalidateQueries({ queryKey: ["provisions"] });
  const invaliderDetail = () => queryClient.invalidateQueries({ queryKey: ["provision-detail"] });
  const invaliderMouvements = () =>
    queryClient.invalidateQueries({ queryKey: ["mouvements-provision"] });

  const creer = useMutation({
    mutationFn: async (donnees: ProvisionCreation) => {
      const { data } = await apiClient.post<Provision>(`${racine(entrepriseId)}/provisions`, donnees);
      return data;
    },
    onSuccess: invalider,
  });

  const modifier = useMutation({
    mutationFn: async ({ id, donnees }: { id: string; donnees: ProvisionMiseAJour }) => {
      const { data } = await apiClient.patch<Provision>(
        `${racine(entrepriseId)}/provisions/${id}`,
        donnees,
      );
      return data;
    },
    onSuccess: () => {
      invalider();
      invaliderDetail();
    },
  });

  const doter = useMutation({
    mutationFn: async ({ id, donnees }: { id: string; donnees: DotationDemande }) => {
      const { data } = await apiClient.post<EcritureLecture>(
        `${racine(entrepriseId)}/provisions/${id}/dotations`,
        donnees,
      );
      return data;
    },
    onSuccess: () => {
      invaliderDetail();
      invaliderMouvements();
      invalider();
    },
  });

  const reprendre = useMutation({
    mutationFn: async ({ id, donnees }: { id: string; donnees: RepriseDemande }) => {
      const { data } = await apiClient.post<EcritureLecture>(
        `${racine(entrepriseId)}/provisions/${id}/reprises`,
        donnees,
      );
      return data;
    },
    onSuccess: () => {
      invaliderDetail();
      invaliderMouvements();
      invalider();
    },
  });

  return { creer, modifier, doter, reprendre };
}