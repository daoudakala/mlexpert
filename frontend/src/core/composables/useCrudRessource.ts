/**
 * Enveloppe TanStack Query autour des opérations CRUD REST standard d'une
 * ressource scopée à l'entreprise active (ex. /paie/entreprises/{id}/employes).
 * Chaque module l'utilise plutôt que de réécrire le même couple
 * useQuery/useMutation à chaque fois.
 *
 * `cheminBase` est une fonction (pas une chaîne) parce qu'elle dépend de
 * l'entreprise active, qui peut changer pendant la vie du composant.
 */
import { computed, type Ref } from "vue";
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationReturnType,
  type UseQueryReturnType,
} from "@tanstack/vue-query";

import { apiClient } from "@/core/api/client";

interface OptionsCrudRessource {
  cleCache: string;
  cheminBase: () => string;
}

export function useCrudRessource<TLecture, TCreation, TMiseAJour = Partial<TCreation>>(
  options: OptionsCrudRessource,
) {
  const queryClient = useQueryClient();
  const cleListe = computed(() => [options.cleCache, options.cheminBase()]);

  function invalider(): Promise<void> {
    return queryClient.invalidateQueries({ queryKey: cleListe.value });
  }

  const liste: UseQueryReturnType<TLecture[], Error> = useQuery({
    queryKey: cleListe,
    queryFn: async () => {
      const { data } = await apiClient.get<TLecture[]>(options.cheminBase());
      return data;
    },
  });

  const creer: UseMutationReturnType<TLecture, Error, TCreation, unknown> = useMutation({
    mutationFn: async (donnees: TCreation) => {
      const { data } = await apiClient.post<TLecture>(options.cheminBase(), donnees);
      return data;
    },
    onSuccess: () => invalider(),
  });

  const modifier: UseMutationReturnType<
    TLecture,
    Error,
    { id: string; donnees: TMiseAJour },
    unknown
  > = useMutation({
    mutationFn: async ({ id, donnees }) => {
      const { data } = await apiClient.patch<TLecture>(`${options.cheminBase()}/${id}`, donnees);
      return data;
    },
    onSuccess: () => invalider(),
  });

  const supprimer: UseMutationReturnType<void, Error, string, unknown> = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`${options.cheminBase()}/${id}`);
    },
    onSuccess: () => invalider(),
  });

  return { liste, creer, modifier, supprimer };
}

/** Utilitaire pour construire un chemin scopé à l'entreprise active sans
 * répéter le template literal dans chaque module. */
export function cheminEntreprise(
  module: string,
  sousChemin: string,
  entrepriseId: Ref<string | null | undefined>,
): string {
  if (!entrepriseId.value) return "";
  return `/${module}/entreprises/${entrepriseId.value}/${sousChemin}`;
}
