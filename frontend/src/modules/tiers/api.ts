/**
 * Accès réseau du module tiers. Pas de `useCrudRessource` générique ici :
 * les actions désactiver/réactiver sont des endpoints dédiés (pas un
 * DELETE), et la mise à jour des comptes collectifs est une route à part
 * (PUT .../comptes-collectifs) — le générique ne couvrirait pas ces cas
 * sans se complexifier inutilement pour un seul module.
 */
import { computed, type Ref } from "vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";

import { apiClient } from "@/core/api/client";
import type { Tiers, TiersComptesCollectifs, TiersCreation, TiersMiseAJour } from "./types";

function cheminTiers(entrepriseId: Ref<string | null | undefined>, suffixe = ""): string {
  return `/entreprises/${entrepriseId.value}/tiers${suffixe}`;
}

export interface FiltresTiers {
  actifsSeulement?: boolean;
  clientSeulement?: boolean;
  fournisseurSeulement?: boolean;
}

export function useListeTiers(
  entrepriseId: Ref<string | null | undefined>,
  filtres: Ref<FiltresTiers>,
) {
  const cle = computed(() => ["tiers", entrepriseId.value, filtres.value]);
  return useQuery({
    queryKey: cle,
    queryFn: async () => {
      const { data } = await apiClient.get<Tiers[]>(cheminTiers(entrepriseId), {
        params: {
          actifs_seulement: filtres.value.actifsSeulement ?? true,
          client_seulement: filtres.value.clientSeulement ?? false,
          fournisseur_seulement: filtres.value.fournisseurSeulement ?? false,
        },
      });
      return data;
    },
    enabled: () => !!entrepriseId.value,
  });
}

export function useTiers(entrepriseId: Ref<string | null | undefined>, tiersId: Ref<string | null>) {
  return useQuery({
    queryKey: ["tiers-detail", entrepriseId, tiersId],
    queryFn: async () => {
      const { data } = await apiClient.get<Tiers>(cheminTiers(entrepriseId, `/${tiersId.value}`));
      return data;
    },
    enabled: () => !!entrepriseId.value && !!tiersId.value,
  });
}

export function useMutationsTiers(entrepriseId: Ref<string | null | undefined>) {
  const queryClient = useQueryClient();
  const invalider = () => queryClient.invalidateQueries({ queryKey: ["tiers"] });
  // Clé partielle volontaire : invalidateQueries fait un matching par
  // préfixe, donc ["tiers-detail"] seul suffit à invalider toutes les
  // fiches en cache (peu nombreuses, pas besoin de cibler plus finement).
  // L'ancienne version construisait une clé avec { value: id } qui ne
  // correspondait à aucune entrée réelle (vue-query déballe les refs dans
  // la clé d'origine) : l'invalidation ne faisait jamais rien.
  const invaliderDetail = (_id: string) =>
    queryClient.invalidateQueries({ queryKey: ["tiers-detail"] });

  const creer = useMutation({
    mutationFn: async (donnees: TiersCreation) => {
      const { data } = await apiClient.post<Tiers>(cheminTiers(entrepriseId), donnees);
      return data;
    },
    onSuccess: invalider,
  });

  const modifier = useMutation({
    mutationFn: async ({ id, donnees }: { id: string; donnees: TiersMiseAJour }) => {
      const { data } = await apiClient.patch<Tiers>(cheminTiers(entrepriseId, `/${id}`), donnees);
      return data;
    },
    onSuccess: (_resultat, variables) => {
      invalider();
      invaliderDetail(variables.id);
    },
  });

  const modifierComptesCollectifs = useMutation({
    mutationFn: async ({ id, donnees }: { id: string; donnees: TiersComptesCollectifs }) => {
      const { data } = await apiClient.put<Tiers>(
        cheminTiers(entrepriseId, `/${id}/comptes-collectifs`),
        donnees,
      );
      return data;
    },
    onSuccess: (_resultat, variables) => {
      invalider();
      invaliderDetail(variables.id);
    },
  });

  const desactiver = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.post(cheminTiers(entrepriseId, `/${id}/desactiver`));
    },
    onSuccess: (_resultat, id) => {
      invalider();
      invaliderDetail(id);
    },
  });

  const reactiver = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.post(cheminTiers(entrepriseId, `/${id}/reactiver`));
    },
    onSuccess: (_resultat, id) => {
      invalider();
      invaliderDetail(id);
    },
  });

  return { creer, modifier, modifierComptesCollectifs, desactiver, reactiver };
}
