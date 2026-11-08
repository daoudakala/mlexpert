/**
 * Accès réseau du module regularisations. Une seule mutation (création) :
 * la régularisation et son écriture naissent ensemble, il n'y a rien à
 * modifier ni d'action dédiée comme la dotation/reprise de `provisions`.
 */
import { computed, type Ref } from "vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";

import { apiClient } from "@/core/api/client";
import type { Regularisation, RegularisationCreation } from "./types";

function racine(entrepriseId: Ref<string | null | undefined>): string {
  return `/regularisations/entreprises/${entrepriseId.value}`;
}

export interface FiltresRegularisations {
  typeRegularisation?: string | null;
}

export function useListeRegularisations(
  entrepriseId: Ref<string | null | undefined>,
  filtres: Ref<FiltresRegularisations>,
) {
  return useQuery({
    queryKey: computed(() => ["regularisations", entrepriseId.value, filtres.value]),
    queryFn: async () => {
      const { data } = await apiClient.get<Regularisation[]>(`${racine(entrepriseId)}/regularisations`, {
        params: {
          type_regularisation: filtres.value.typeRegularisation || undefined,
        },
      });
      return data;
    },
    enabled: () => !!entrepriseId.value,
  });
}

export function useMutationsRegularisations(entrepriseId: Ref<string | null | undefined>) {
  const queryClient = useQueryClient();
  const invalider = () => queryClient.invalidateQueries({ queryKey: ["regularisations"] });

  const creer = useMutation({
    mutationFn: async (donnees: RegularisationCreation) => {
      const { data } = await apiClient.post<Regularisation>(
        `${racine(entrepriseId)}/regularisations`,
        donnees,
      );
      return data;
    },
    onSuccess: invalider,
  });

  return { creer };
}