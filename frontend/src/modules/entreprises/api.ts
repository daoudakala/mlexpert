/**
 * Accès réseau du module entreprises. La gestion de la fiche (créer,
 * modifier, archiver/suspendre/réactiver) est réservée à l'administrateur
 * plateforme (voir router.py) ; `/entreprises/moi` reste du self-service.
 */
import { computed, type Ref } from "vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";

import { apiClient } from "@/core/api/client";
import type { Entreprise, EntrepriseCreation, EntrepriseMiseAJour } from "./types";

export function useListeEntreprises(recherche: Ref<string>) {
  return useQuery({
    queryKey: computed(() => ["entreprises", recherche.value]),
    queryFn: async () => {
      const { data } = await apiClient.get<Entreprise[]>("/entreprises", {
        params: recherche.value ? { q: recherche.value } : undefined,
      });
      return data;
    },
  });
}

export function useEntreprise(entrepriseId: Ref<string | null | undefined>) {
  return useQuery({
    queryKey: ["entreprise-detail", entrepriseId],
    queryFn: async () => {
      const { data } = await apiClient.get<Entreprise>(`/entreprises/${entrepriseId.value}`);
      return data;
    },
    enabled: () => !!entrepriseId.value,
  });
}

export function useMutationsEntreprises() {
  const queryClient = useQueryClient();
  const invalider = () => queryClient.invalidateQueries({ queryKey: ["entreprises"] });
  const invaliderDetail = () => queryClient.invalidateQueries({ queryKey: ["entreprise-detail"] });

  const creer = useMutation({
    mutationFn: async (donnees: EntrepriseCreation) => {
      const { data } = await apiClient.post<Entreprise>("/entreprises", donnees);
      return data;
    },
    onSuccess: invalider,
  });

  const modifier = useMutation({
    mutationFn: async ({ id, donnees }: { id: string; donnees: EntrepriseMiseAJour }) => {
      const { data } = await apiClient.patch<Entreprise>(`/entreprises/${id}`, donnees);
      return data;
    },
    onSuccess: () => {
      invalider();
      invaliderDetail();
    },
  });

  const archiver = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.post(`/entreprises/${id}/archiver`);
    },
    onSuccess: () => {
      invalider();
      invaliderDetail();
    },
  });

  const suspendre = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.post(`/entreprises/${id}/suspendre`);
    },
    onSuccess: () => {
      invalider();
      invaliderDetail();
    },
  });

  const reactiver = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.post(`/entreprises/${id}/reactiver`);
    },
    onSuccess: () => {
      invalider();
      invaliderDetail();
    },
  });

  return { creer, modifier, archiver, suspendre, reactiver };
}
