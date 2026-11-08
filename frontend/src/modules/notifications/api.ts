/**
 * Accès réseau du module notifications. Toutes les routes portent sur
 * "mes" notifications/préférences — pas de paramètre destinataire, c'est
 * toujours l'utilisateur connecté (voir router.py côté backend).
 */
import type { Ref } from "vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";

import { apiClient } from "@/core/api/client";
import type {
  CompteurNotifications,
  Notification,
  PreferenceNotification,
  PreferenceNotificationEcriture,
} from "./types";

function racine(entrepriseId: Ref<string | null | undefined>): string {
  return `/notifications/entreprises/${entrepriseId.value}`;
}

export function useMesNotifications(
  entrepriseId: Ref<string | null | undefined>,
  nonLuesSeulement: Ref<boolean>,
) {
  return useQuery({
    queryKey: ["mes-notifications", entrepriseId, nonLuesSeulement],
    queryFn: async () => {
      const { data } = await apiClient.get<Notification[]>(`${racine(entrepriseId)}/mes-notifications`, {
        params: { non_lues_seulement: nonLuesSeulement.value },
      });
      return data;
    },
    enabled: () => !!entrepriseId.value,
    // Rafraîchi périodiquement : pas de WebSocket/SSE dans ce module
    // (infrastructure volontairement simple, voir la conception de
    // l'Étape 3) — un polling raisonnable fait l'affaire pour un badge.
    refetchInterval: 60_000,
  });
}

export function useCompteurNotifications(entrepriseId: Ref<string | null | undefined>) {
  return useQuery({
    queryKey: ["mes-notifications-compteur", entrepriseId],
    queryFn: async () => {
      const { data } = await apiClient.get<CompteurNotifications>(
        `${racine(entrepriseId)}/mes-notifications/compteur`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value,
    refetchInterval: 60_000,
  });
}

export function useMesPreferences(entrepriseId: Ref<string | null | undefined>) {
  return useQuery({
    queryKey: ["mes-preferences-notifications", entrepriseId],
    queryFn: async () => {
      const { data } = await apiClient.get<PreferenceNotification[]>(`${racine(entrepriseId)}/mes-preferences`);
      return data;
    },
    enabled: () => !!entrepriseId.value,
  });
}

export function useMutationsNotifications(entrepriseId: Ref<string | null | undefined>) {
  const queryClient = useQueryClient();
  const invalider = () =>
    queryClient.invalidateQueries({ queryKey: ["mes-notifications"] }) &&
    queryClient.invalidateQueries({ queryKey: ["mes-notifications-compteur"] });

  const marquerLue = useMutation({
    mutationFn: async (notificationId: string) => {
      const { data } = await apiClient.post<Notification>(
        `${racine(entrepriseId)}/notifications/${notificationId}/marquer-lue`,
      );
      return data;
    },
    onSuccess: invalider,
  });

  const marquerToutesLues = useMutation({
    mutationFn: async () => {
      await apiClient.post(`${racine(entrepriseId)}/mes-notifications/marquer-toutes-lues`);
    },
    onSuccess: invalider,
  });

  const definirPreference = useMutation({
    mutationFn: async ({
      typeNotification,
      donnees,
    }: {
      typeNotification: string;
      donnees: PreferenceNotificationEcriture;
    }) => {
      const { data } = await apiClient.put<PreferenceNotification>(
        `${racine(entrepriseId)}/mes-preferences/${typeNotification}`,
        donnees,
      );
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["mes-preferences-notifications"] }),
  });

  return { marquerLue, marquerToutesLues, definirPreference };
}