/**
 * Accès réseau du module journal_activite. Uniquement de la lecture (le
 * journal ne s'écrit jamais depuis le frontend, voir la note de tête de
 * fichier de service.py) : la recherche entreprise-scopée avec filtres +
 * pagination, et l'historique complet d'un objet précis — pas de route
 * pour la vue transversale plateforme, réservée à un administrateur
 * plateforme (pas de notion d'espace "administration" dans le frontend
 * pour l'instant).
 */
import { computed, type Ref } from "vue";
import { useQuery } from "@tanstack/vue-query";

import { apiClient } from "@/core/api/client";
import type { EntreeJournalActivite } from "./types";

export interface FiltresJournalActivite {
  utilisateurId?: string | null;
  module?: string | null;
  typeAction?: string | null;
  typeObjet?: string | null;
  objetId?: string | null;
  depuis?: string | null;
  jusquA?: string | null;
  limite?: number;
  decalage?: number;
}

export function useJournalActivite(
  entrepriseId: Ref<string | null | undefined>,
  filtres: Ref<FiltresJournalActivite>,
) {
  return useQuery({
    queryKey: computed(() => ["journal-activite", entrepriseId.value, filtres.value]),
    queryFn: async () => {
      const { data } = await apiClient.get<EntreeJournalActivite[]>(
        `/entreprises/${entrepriseId.value}/journal-activite`,
        {
          params: {
            utilisateur_id: filtres.value.utilisateurId || undefined,
            module: filtres.value.module || undefined,
            type_action: filtres.value.typeAction || undefined,
            type_objet: filtres.value.typeObjet || undefined,
            objet_id: filtres.value.objetId || undefined,
            depuis: filtres.value.depuis || undefined,
            jusqu_a: filtres.value.jusquA || undefined,
            limite: filtres.value.limite ?? 100,
            decalage: filtres.value.decalage ?? 0,
          },
        },
      );
      return data;
    },
    enabled: () => !!entrepriseId.value,
  });
}

/** Historique complet d'un objet précis (ex. un exercice, une écriture) —
 * destiné à être réutilisé plus tard par d'autres modules qui voudraient
 * afficher "qui a fait quoi" sur une fiche donnée, pas seulement par la
 * page de recherche générale. */
export function useHistoriqueObjet(
  entrepriseId: Ref<string | null | undefined>,
  typeObjet: Ref<string | null>,
  objetId: Ref<string | null>,
) {
  return useQuery({
    queryKey: ["historique-objet", entrepriseId, typeObjet, objetId],
    queryFn: async () => {
      const { data } = await apiClient.get<EntreeJournalActivite[]>(
        `/entreprises/${entrepriseId.value}/journal-activite/objets/${typeObjet.value}/${objetId.value}`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value && !!typeObjet.value && !!objetId.value,
  });
}
