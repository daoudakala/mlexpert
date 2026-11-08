/**
 * Accès réseau du module paie — employés, rubriques, bulletins. Même
 * convention que immobilisations/tresorerie : pas de suppression dure
 * pour employé/rubrique (désactivation logique), un brouillon de bulletin
 * peut être supprimé mais pas un bulletin validé (voir service.py).
 */
import { computed, type Ref } from "vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";

import { apiClient } from "@/core/api/client";
import type { EcritureLecture } from "@/modules/comptabilite/types";
import type {
  Bulletin,
  BulletinCreation,
  BulletinMiseAJourLignes,
  Employe,
  EmployeCreation,
  EmployeMiseAJour,
  GenerationEcritureBulletinDemande,
  LigneBulletin,
  RubriquePaie,
  RubriquePaieCreation,
} from "./types";

function racinePaie(entrepriseId: Ref<string | null | undefined>): string {
  return `/paie/entreprises/${entrepriseId.value}`;
}

// --- Employés ----------------------------------------------------------------

export interface FiltresEmployes {
  actifsSeulement?: boolean;
}

export function useListeEmployes(
  entrepriseId: Ref<string | null | undefined>,
  filtres: Ref<FiltresEmployes>,
) {
  return useQuery({
    queryKey: computed(() => ["employes", entrepriseId.value, filtres.value]),
    queryFn: async () => {
      const { data } = await apiClient.get<Employe[]>(`${racinePaie(entrepriseId)}/employes`, {
        params: { actifs_seulement: filtres.value.actifsSeulement ?? true },
      });
      return data;
    },
    enabled: () => !!entrepriseId.value,
  });
}

export function useEmploye(entrepriseId: Ref<string | null | undefined>, employeId: Ref<string | null>) {
  return useQuery({
    queryKey: ["employe-detail", entrepriseId, employeId],
    queryFn: async () => {
      const { data } = await apiClient.get<Employe>(
        `${racinePaie(entrepriseId)}/employes/${employeId.value}`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value && !!employeId.value,
  });
}

export function useMutationsEmployes(entrepriseId: Ref<string | null | undefined>) {
  const queryClient = useQueryClient();
  const invalider = () => queryClient.invalidateQueries({ queryKey: ["employes"] });
  const invaliderDetail = () => queryClient.invalidateQueries({ queryKey: ["employe-detail"] });

  const creer = useMutation({
    mutationFn: async (donnees: EmployeCreation) => {
      const { data } = await apiClient.post<Employe>(`${racinePaie(entrepriseId)}/employes`, donnees);
      return data;
    },
    onSuccess: invalider,
  });

  const modifier = useMutation({
    mutationFn: async ({ id, donnees }: { id: string; donnees: EmployeMiseAJour }) => {
      const { data } = await apiClient.patch<Employe>(
        `${racinePaie(entrepriseId)}/employes/${id}`,
        donnees,
      );
      return data;
    },
    onSuccess: () => {
      invalider();
      invaliderDetail();
    },
  });

  const desactiver = useMutation({
    mutationFn: async ({ id, date_sortie }: { id: string; date_sortie: string }) => {
      const { data } = await apiClient.post<Employe>(
        `${racinePaie(entrepriseId)}/employes/${id}/desactiver`,
        { date_sortie },
      );
      return data;
    },
    onSuccess: () => {
      invalider();
      invaliderDetail();
    },
  });

  const reactiver = useMutation({
    mutationFn: async (id: string) => {
      const { data } = await apiClient.post<Employe>(
        `${racinePaie(entrepriseId)}/employes/${id}/reactiver`,
      );
      return data;
    },
    onSuccess: () => {
      invalider();
      invaliderDetail();
    },
  });

  return { creer, modifier, desactiver, reactiver };
}

// --- Rubriques de paie ---------------------------------------------------------

export function useListeRubriques(
  entrepriseId: Ref<string | null | undefined>,
  actifsSeulement: Ref<boolean> = computed(() => true) as Ref<boolean>,
) {
  return useQuery({
    queryKey: computed(() => ["rubriques-paie", entrepriseId.value, actifsSeulement.value]),
    queryFn: async () => {
      const { data } = await apiClient.get<RubriquePaie[]>(`${racinePaie(entrepriseId)}/rubriques`, {
        params: { actifs_seulement: actifsSeulement.value },
      });
      return data;
    },
    enabled: () => !!entrepriseId.value,
  });
}

export function useMutationsRubriques(entrepriseId: Ref<string | null | undefined>) {
  const queryClient = useQueryClient();
  const invalider = () => queryClient.invalidateQueries({ queryKey: ["rubriques-paie"] });

  const creer = useMutation({
    mutationFn: async (donnees: RubriquePaieCreation) => {
      const { data } = await apiClient.post<RubriquePaie>(
        `${racinePaie(entrepriseId)}/rubriques`,
        donnees,
      );
      return data;
    },
    onSuccess: invalider,
  });

  const definirCompteComptable = useMutation({
    mutationFn: async ({ id, compteComptableId }: { id: string; compteComptableId: string }) => {
      const { data } = await apiClient.post<RubriquePaie>(
        `${racinePaie(entrepriseId)}/rubriques/${id}/compte-comptable`,
        { compte_comptable_id: compteComptableId },
      );
      return data;
    },
    onSuccess: invalider,
  });

  const desactiver = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.post(`${racinePaie(entrepriseId)}/rubriques/${id}/desactiver`);
    },
    onSuccess: invalider,
  });

  return { creer, definirCompteComptable, desactiver };
}

// --- Bulletins de paie -----------------------------------------------------------

export interface FiltresBulletins {
  employeId?: string;
  exerciceId?: string;
  statut?: string;
}

export function useListeBulletins(
  entrepriseId: Ref<string | null | undefined>,
  filtres: Ref<FiltresBulletins>,
) {
  return useQuery({
    queryKey: computed(() => ["bulletins", entrepriseId.value, filtres.value]),
    queryFn: async () => {
      const { data } = await apiClient.get<Bulletin[]>(`${racinePaie(entrepriseId)}/bulletins`, {
        params: {
          employe_id: filtres.value.employeId || undefined,
          exercice_id: filtres.value.exerciceId || undefined,
          statut: filtres.value.statut || undefined,
        },
      });
      return data;
    },
    enabled: () => !!entrepriseId.value,
  });
}

export function useBulletin(entrepriseId: Ref<string | null | undefined>, bulletinId: Ref<string | null>) {
  return useQuery({
    queryKey: ["bulletin-detail", entrepriseId, bulletinId],
    queryFn: async () => {
      const { data } = await apiClient.get<Bulletin>(
        `${racinePaie(entrepriseId)}/bulletins/${bulletinId.value}`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value && !!bulletinId.value,
  });
}

export function useLignesBulletin(
  entrepriseId: Ref<string | null | undefined>,
  bulletinId: Ref<string | null>,
) {
  return useQuery({
    queryKey: ["bulletin-lignes", entrepriseId, bulletinId],
    queryFn: async () => {
      const { data } = await apiClient.get<LigneBulletin[]>(
        `${racinePaie(entrepriseId)}/bulletins/${bulletinId.value}/lignes`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value && !!bulletinId.value,
  });
}

export function useMutationsBulletins(entrepriseId: Ref<string | null | undefined>) {
  const queryClient = useQueryClient();
  const invalider = () => queryClient.invalidateQueries({ queryKey: ["bulletins"] });
  const invaliderDetail = () => {
    queryClient.invalidateQueries({ queryKey: ["bulletin-detail"] });
    queryClient.invalidateQueries({ queryKey: ["bulletin-lignes"] });
  };

  const creer = useMutation({
    mutationFn: async (donnees: BulletinCreation) => {
      const { data } = await apiClient.post<Bulletin>(`${racinePaie(entrepriseId)}/bulletins`, donnees);
      return data;
    },
    onSuccess: invalider,
  });

  const modifier = useMutation({
    mutationFn: async ({ id, donnees }: { id: string; donnees: BulletinMiseAJourLignes }) => {
      const { data } = await apiClient.patch<Bulletin>(
        `${racinePaie(entrepriseId)}/bulletins/${id}`,
        donnees,
      );
      return data;
    },
    onSuccess: () => {
      invalider();
      invaliderDetail();
    },
  });

  const supprimer = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.post(`${racinePaie(entrepriseId)}/bulletins/${id}/supprimer`);
    },
    onSuccess: invalider,
  });

  const valider = useMutation({
    mutationFn: async (id: string) => {
      const { data } = await apiClient.post<Bulletin>(
        `${racinePaie(entrepriseId)}/bulletins/${id}/valider`,
      );
      return data;
    },
    onSuccess: () => {
      invalider();
      invaliderDetail();
    },
  });

  const genererEcriture = useMutation({
    mutationFn: async ({ id, donnees }: { id: string; donnees: GenerationEcritureBulletinDemande }) => {
      const { data } = await apiClient.post<EcritureLecture>(
        `${racinePaie(entrepriseId)}/bulletins/${id}/generer-ecriture`,
        donnees,
      );
      return data;
    },
    onSuccess: () => {
      invalider();
      invaliderDetail();
    },
  });

  return { creer, modifier, supprimer, valider, genererEcriture };
}
