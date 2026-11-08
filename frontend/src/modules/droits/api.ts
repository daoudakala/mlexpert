/**
 * Accès réseau du module droits. Les rôles/permissions sont globaux
 * (administrateur plateforme) ; les affectations et l'invitation sont
 * gérées dans le périmètre d'une entreprise (`droits.administrer`/
 * `droits.consulter`) — y compris le retrait, aligné sur
 * `droits.administrer` depuis l'Étape 6 (auto-gestion des entreprises,
 * voir la note de tête de `router.py` côté backend).
 */
import { computed, type Ref } from "vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";

import { apiClient } from "@/core/api/client";
import type {
  Affectation,
  AffectationCreation,
  AttributionRoleGlobal,
  AttributionRoleGlobalCreation,
  InvitationCreation,
  InvitationResultat,
  Permission,
  Role,
  RoleAvecPermissions,
  RoleCreation,
  RoleMiseAJour,
} from "./types";

export function useRoles() {
  return useQuery({
    queryKey: ["roles"],
    queryFn: async () => {
      const { data } = await apiClient.get<RoleAvecPermissions[]>("/droits/roles");
      return data;
    },
  });
}

export function usePermissions() {
  return useQuery({
    queryKey: ["permissions"],
    queryFn: async () => {
      const { data } = await apiClient.get<Permission[]>("/droits/permissions");
      return data;
    },
  });
}

export function useMutationsRoles() {
  const queryClient = useQueryClient();
  const invalider = () => queryClient.invalidateQueries({ queryKey: ["roles"] });

  const creer = useMutation({
    mutationFn: async (donnees: RoleCreation) => {
      const { data } = await apiClient.post<Role>("/droits/roles", donnees);
      return data;
    },
    onSuccess: invalider,
  });

  const modifier = useMutation({
    mutationFn: async ({ id, donnees }: { id: string; donnees: RoleMiseAJour }) => {
      const { data } = await apiClient.patch<RoleAvecPermissions>(`/droits/roles/${id}`, donnees);
      return data;
    },
    onSuccess: invalider,
  });

  return { creer, modifier };
}

export function useMutationsAttributionsGlobales() {
  const attribuer = useMutation({
    mutationFn: async (donnees: AttributionRoleGlobalCreation) => {
      const { data } = await apiClient.post<AttributionRoleGlobal>(
        "/droits/attributions-globales",
        donnees,
      );
      return data;
    },
  });

  return { attribuer };
}

// --- Rôles disponibles pour une entreprise (Étape 6) ------------------------

/**
 * Les rôles que l'administrateur de CETTE entreprise peut choisir pour
 * inviter/affecter (tous les rôles non-plateforme) — contrairement à
 * `useRoles` (toute la liste, y compris plateforme), cette route est
 * accessible à `droits.administrer` sans être l'administrateur plateforme.
 */
export function useRolesDisponibles(entrepriseId: Ref<string | null | undefined>) {
  return useQuery({
    queryKey: computed(() => ["roles-disponibles", entrepriseId.value]),
    queryFn: async () => {
      const { data } = await apiClient.get<Role[]>(
        `/droits/entreprises/${entrepriseId.value}/roles-disponibles`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value,
  });
}

// --- Affectations (périmètre d'une entreprise) ------------------------------

export function useAffectations(entrepriseId: Ref<string | null | undefined>) {
  return useQuery({
    queryKey: computed(() => ["affectations", entrepriseId.value]),
    queryFn: async () => {
      const { data } = await apiClient.get<Affectation[]>(
        `/droits/entreprises/${entrepriseId.value}/affectations`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value,
  });
}

export function useMutationsAffectations(entrepriseId: Ref<string | null | undefined>) {
  const queryClient = useQueryClient();
  const invalider = () => queryClient.invalidateQueries({ queryKey: ["affectations"] });

  const affecter = useMutation({
    mutationFn: async (donnees: AffectationCreation) => {
      const { data } = await apiClient.post<Affectation>(
        `/droits/entreprises/${entrepriseId.value}/affectations`,
        donnees,
      );
      return data;
    },
    onSuccess: invalider,
  });

  const retirer = useMutation({
    mutationFn: async (affectationId: string) => {
      await apiClient.delete(
        `/droits/entreprises/${entrepriseId.value}/affectations/${affectationId}`,
      );
    },
    onSuccess: invalider,
  });

  const inviter = useMutation({
    mutationFn: async (donnees: InvitationCreation) => {
      const { data } = await apiClient.post<InvitationResultat>(
        `/droits/entreprises/${entrepriseId.value}/inviter`,
        donnees,
      );
      return data;
    },
    onSuccess: invalider,
  });

  return { affecter, retirer, inviter };
}