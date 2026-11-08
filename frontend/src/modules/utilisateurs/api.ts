/**
 * Accès réseau du module utilisateurs : self-service (mon profil, mot de
 * passe) et administration des comptes (réservée à l'administrateur
 * plateforme, voir exiger_administrateur_plateforme côté backend).
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";

import { apiClient } from "@/core/api/client";
import type {
  ChangementMotDePasse,
  ReinitialisationMotDePasse,
  Utilisateur,
  UtilisateurCreation,
  UtilisateurMiseAJourProfil,
} from "./types";

// --- Self-service -----------------------------------------------------------

/** Ne gère pas la mise à jour du store d'auth (voir `useAuth().utilisateur`)
 * : l'appelant (MonProfilPage) fusionne le résultat lui-même, le store
 * n'étant pas piloté par TanStack Query. */
export function useMutationsMonProfil() {
  const modifier = useMutation({
    mutationFn: async (donnees: UtilisateurMiseAJourProfil) => {
      const { data } = await apiClient.patch<Utilisateur>("/utilisateurs/moi", donnees);
      return data;
    },
  });

  const changerMotDePasse = useMutation({
    mutationFn: async (donnees: ChangementMotDePasse) => {
      await apiClient.post("/utilisateurs/moi/mot-de-passe", donnees);
    },
  });

  return { modifier, changerMotDePasse };
}

// --- Administration des comptes (administrateur plateforme) ----------------

export function useListeUtilisateurs() {
  return useQuery({
    queryKey: ["utilisateurs"],
    queryFn: async () => {
      const { data } = await apiClient.get<Utilisateur[]>("/utilisateurs");
      return data;
    },
  });
}

export function useMutationsUtilisateurs() {
  const queryClient = useQueryClient();
  const invalider = () => queryClient.invalidateQueries({ queryKey: ["utilisateurs"] });

  const creer = useMutation({
    mutationFn: async (donnees: UtilisateurCreation) => {
      const { data } = await apiClient.post<Utilisateur>("/utilisateurs", donnees);
      return data;
    },
    onSuccess: invalider,
  });

  const desactiver = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.post(`/utilisateurs/${id}/desactiver`);
    },
    onSuccess: invalider,
  });

  const reactiver = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.post(`/utilisateurs/${id}/reactiver`);
    },
    onSuccess: invalider,
  });

  const reinitialiserMotDePasse = useMutation({
    mutationFn: async ({ id, donnees }: { id: string; donnees: ReinitialisationMotDePasse }) => {
      await apiClient.post(`/utilisateurs/${id}/reinitialiser-mot-de-passe`, donnees);
    },
  });

  return { creer, desactiver, reactiver, reinitialiserMotDePasse };
}
