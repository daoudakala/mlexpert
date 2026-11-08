import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import type { Ref } from "vue";

import { apiClient } from "@/core/api/client";
import type { Exercice, ExerciceCreation, Periode, PeriodeCreation } from "./types";

/** Les exercices de l'entreprise — utilisé pour choisir l'exercice d'une
 * écriture (module comptabilite) et par le module exercices lui-même. */
export function useExercices(entrepriseId: Ref<string | null | undefined>) {
  return useQuery({
    queryKey: ["exercices", entrepriseId],
    queryFn: async () => {
      const { data } = await apiClient.get<Exercice[]>(
        `/entreprises/${entrepriseId.value}/exercices`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value,
  });
}

export function useExercice(entrepriseId: Ref<string | null | undefined>, exerciceId: Ref<string | null>) {
  return useQuery({
    queryKey: ["exercice-detail", entrepriseId, exerciceId],
    queryFn: async () => {
      const { data } = await apiClient.get<Exercice>(
        `/entreprises/${entrepriseId.value}/exercices/${exerciceId.value}`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value && !!exerciceId.value,
  });
}

export function useMutationsExercices(entrepriseId: Ref<string | null | undefined>) {
  const queryClient = useQueryClient();
  const invalider = () => queryClient.invalidateQueries({ queryKey: ["exercices"] });
  const invaliderDetail = () => queryClient.invalidateQueries({ queryKey: ["exercice-detail"] });

  const creer = useMutation({
    mutationFn: async (donnees: ExerciceCreation) => {
      const { data } = await apiClient.post<Exercice>(
        `/entreprises/${entrepriseId.value}/exercices`,
        donnees,
      );
      return data;
    },
    onSuccess: invalider,
  });

  const cloturer = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.post(`/entreprises/${entrepriseId.value}/exercices/${id}/cloturer`);
    },
    onSuccess: () => {
      invalider();
      invaliderDetail();
    },
  });

  const reouvrir = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.post(`/entreprises/${entrepriseId.value}/exercices/${id}/reouvrir`);
    },
    onSuccess: () => {
      invalider();
      invaliderDetail();
    },
  });

  return { creer, cloturer, reouvrir };
}

// --- Périodes -------------------------------------------------------------

export function usePeriodes(
  entrepriseId: Ref<string | null | undefined>,
  exerciceId: Ref<string | null | undefined>,
) {
  return useQuery({
    queryKey: ["periodes", entrepriseId, exerciceId],
    queryFn: async () => {
      const { data } = await apiClient.get<Periode[]>(
        `/entreprises/${entrepriseId.value}/exercices/${exerciceId.value}/periodes`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value && !!exerciceId.value,
  });
}

export function useMutationsPeriodes(
  entrepriseId: Ref<string | null | undefined>,
  exerciceId: Ref<string | null | undefined>,
) {
  const queryClient = useQueryClient();
  const invalider = () => queryClient.invalidateQueries({ queryKey: ["periodes"] });

  const creer = useMutation({
    mutationFn: async (donnees: PeriodeCreation) => {
      const { data } = await apiClient.post<Periode>(
        `/entreprises/${entrepriseId.value}/exercices/${exerciceId.value}/periodes`,
        donnees,
      );
      return data;
    },
    onSuccess: invalider,
  });

  const cloturer = useMutation({
    mutationFn: async (periodeId: string) => {
      await apiClient.post(
        `/entreprises/${entrepriseId.value}/exercices/${exerciceId.value}/periodes/${periodeId}/cloturer`,
      );
    },
    onSuccess: invalider,
  });

  const reouvrir = useMutation({
    mutationFn: async (periodeId: string) => {
      await apiClient.post(
        `/entreprises/${entrepriseId.value}/exercices/${exerciceId.value}/periodes/${periodeId}/reouvrir`,
      );
    },
    onSuccess: invalider,
  });

  return { creer, cloturer, reouvrir };
}
