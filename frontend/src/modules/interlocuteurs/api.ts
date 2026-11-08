/** Accès réseau du module interlocuteurs — CRUD classique, même gabarit
 * que `documents/api.ts` (sans la partie upload). */
import { computed, type Ref } from "vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";

import { apiClient } from "@/core/api/client";
import type { Interlocuteur, InterlocuteurEcriture, RoleInterlocuteur } from "./types";

function racine(entrepriseId: Ref<string | null | undefined>): string {
  return `/interlocuteurs/entreprises/${entrepriseId.value}`;
}

export interface FiltresInterlocuteurs {
  role?: RoleInterlocuteur | null;
  actifsSeulement?: boolean;
}

export function useListeInterlocuteurs(
  entrepriseId: Ref<string | null | undefined>,
  filtres: Ref<FiltresInterlocuteurs>,
) {
  return useQuery({
    queryKey: computed(() => ["interlocuteurs", entrepriseId.value, filtres.value]),
    queryFn: async () => {
      const { data } = await apiClient.get<Interlocuteur[]>(`${racine(entrepriseId)}/interlocuteurs`, {
        params: {
          role: filtres.value.role || undefined,
          actifs_seulement: filtres.value.actifsSeulement ?? true,
        },
      });
      return data;
    },
    enabled: () => !!entrepriseId.value,
  });
}

export function useMutationsInterlocuteurs(entrepriseId: Ref<string | null | undefined>) {
  const queryClient = useQueryClient();
  const invalider = () => queryClient.invalidateQueries({ queryKey: ["interlocuteurs"] });

  const creer = useMutation({
    mutationFn: async (donnees: InterlocuteurEcriture) => {
      const { data } = await apiClient.post<Interlocuteur>(
        `${racine(entrepriseId)}/interlocuteurs`,
        donnees,
      );
      return data;
    },
    onSuccess: invalider,
  });

  const modifier = useMutation({
    mutationFn: async ({ id, donnees }: { id: string; donnees: InterlocuteurEcriture }) => {
      const { data } = await apiClient.patch<Interlocuteur>(
        `${racine(entrepriseId)}/interlocuteurs/${id}`,
        donnees,
      );
      return data;
    },
    onSuccess: invalider,
  });

  const desactiver = useMutation({
    mutationFn: async (id: string) => {
      const { data } = await apiClient.post<Interlocuteur>(
        `${racine(entrepriseId)}/interlocuteurs/${id}/desactiver`,
      );
      return data;
    },
    onSuccess: invalider,
  });

  const reactiver = useMutation({
    mutationFn: async (id: string) => {
      const { data } = await apiClient.post<Interlocuteur>(
        `${racine(entrepriseId)}/interlocuteurs/${id}/reactiver`,
      );
      return data;
    },
    onSuccess: invalider,
  });

  return { creer, modifier, desactiver, reactiver };
}
