/**
 * Accès réseau du module stocks. Comme les autres modules métier, pas de
 * `useCrudRessource` générique : deux routes de création de mouvement
 * distinctes (entrée/sortie, reflet des deux schémas backend), plus la
 * génération d'écriture et l'historique des lignes de consommation FIFO
 * (actions dédiées qui ne rentrent pas dans un CRUD classique).
 */
import { computed, type Ref } from "vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";

import { apiClient } from "@/core/api/client";
import type { EcritureLecture } from "@/modules/comptabilite/types";
import type {
  Article,
  ArticleCreation,
  ArticleMiseAJour,
  GenerationEcritureMouvementDemande,
  InventairePhysique,
  InventairePhysiqueCreation,
  LigneConsommationLot,
  MouvementEntreeCreation,
  MouvementSortieCreation,
  MouvementStock,
} from "./types";

function racine(entrepriseId: Ref<string | null | undefined>): string {
  return `/stocks/entreprises/${entrepriseId.value}`;
}

export function useListeArticles(
  entrepriseId: Ref<string | null | undefined>,
  actifsSeulement: Ref<boolean>,
) {
  return useQuery({
    queryKey: computed(() => ["articles", entrepriseId.value, actifsSeulement.value]),
    queryFn: async () => {
      const { data } = await apiClient.get<Article[]>(`${racine(entrepriseId)}/articles`, {
        params: { actifs_seulement: actifsSeulement.value },
      });
      return data;
    },
    enabled: () => !!entrepriseId.value,
  });
}

export function useArticle(
  entrepriseId: Ref<string | null | undefined>,
  articleId: Ref<string | null>,
) {
  return useQuery({
    queryKey: ["article-detail", entrepriseId, articleId],
    queryFn: async () => {
      const { data } = await apiClient.get<Article>(`${racine(entrepriseId)}/articles/${articleId.value}`);
      return data;
    },
    enabled: () => !!entrepriseId.value && !!articleId.value,
  });
}

export function useMouvements(
  entrepriseId: Ref<string | null | undefined>,
  articleId: Ref<string | null>,
) {
  return useQuery({
    queryKey: computed(() => ["mouvements-stock", entrepriseId.value, articleId.value]),
    queryFn: async () => {
      const { data } = await apiClient.get<MouvementStock[]>(`${racine(entrepriseId)}/mouvements`, {
        params: { article_id: articleId.value || undefined },
      });
      return data;
    },
    enabled: () => !!entrepriseId.value && !!articleId.value,
  });
}

export function useLignesConsommation(
  entrepriseId: Ref<string | null | undefined>,
  mouvementId: Ref<string | null>,
) {
  return useQuery({
    queryKey: ["lignes-consommation", entrepriseId, mouvementId],
    queryFn: async () => {
      const { data } = await apiClient.get<LigneConsommationLot[]>(
        `${racine(entrepriseId)}/mouvements/${mouvementId.value}/lignes-consommation`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value && !!mouvementId.value,
  });
}

export function useInventairesPhysiques(
  entrepriseId: Ref<string | null | undefined>,
  articleId: Ref<string | null>,
) {
  return useQuery({
    queryKey: computed(() => ["inventaires-physiques", entrepriseId.value, articleId.value]),
    queryFn: async () => {
      const { data } = await apiClient.get<InventairePhysique[]>(
        `${racine(entrepriseId)}/inventaires-physiques`,
        { params: { article_id: articleId.value || undefined } },
      );
      return data;
    },
    enabled: () => !!entrepriseId.value && !!articleId.value,
  });
}


export function useMutationsArticles(entrepriseId: Ref<string | null | undefined>) {
  const queryClient = useQueryClient();
  const invalider = () => queryClient.invalidateQueries({ queryKey: ["articles"] });
  const invaliderDetail = () => queryClient.invalidateQueries({ queryKey: ["article-detail"] });

  const creer = useMutation({
    mutationFn: async (donnees: ArticleCreation) => {
      const { data } = await apiClient.post<Article>(`${racine(entrepriseId)}/articles`, donnees);
      return data;
    },
    onSuccess: invalider,
  });

  const modifier = useMutation({
    mutationFn: async ({ id, donnees }: { id: string; donnees: ArticleMiseAJour }) => {
      const { data } = await apiClient.patch<Article>(`${racine(entrepriseId)}/articles/${id}`, donnees);
      return data;
    },
    onSuccess: () => {
      invalider();
      invaliderDetail();
    },
  });

  const desactiver = useMutation({
    mutationFn: async (id: string) => {
      const { data } = await apiClient.post<Article>(`${racine(entrepriseId)}/articles/${id}/desactiver`);
      return data;
    },
    onSuccess: () => {
      invalider();
      invaliderDetail();
    },
  });

  const reactiver = useMutation({
    mutationFn: async (id: string) => {
      const { data } = await apiClient.post<Article>(`${racine(entrepriseId)}/articles/${id}/reactiver`);
      return data;
    },
    onSuccess: () => {
      invalider();
      invaliderDetail();
    },
  });

  return { creer, modifier, desactiver, reactiver };
}

export function useMutationsMouvements(entrepriseId: Ref<string | null | undefined>) {
  const queryClient = useQueryClient();
  const invalider = () => {
    queryClient.invalidateQueries({ queryKey: ["mouvements-stock"] });
    queryClient.invalidateQueries({ queryKey: ["article-detail"] });
    queryClient.invalidateQueries({ queryKey: ["articles"] });
  };

  const creerEntree = useMutation({
    mutationFn: async (donnees: MouvementEntreeCreation) => {
      const { data } = await apiClient.post<MouvementStock>(
        `${racine(entrepriseId)}/mouvements/entrees`,
        donnees,
      );
      return data;
    },
    onSuccess: invalider,
  });

  const creerSortie = useMutation({
    mutationFn: async (donnees: MouvementSortieCreation) => {
      const { data } = await apiClient.post<MouvementStock>(
        `${racine(entrepriseId)}/mouvements/sorties`,
        donnees,
      );
      return data;
    },
    onSuccess: invalider,
  });

  const genererEcriture = useMutation({
    mutationFn: async ({
      mouvementId,
      donnees,
    }: {
      mouvementId: string;
      donnees: GenerationEcritureMouvementDemande;
    }) => {
      const { data } = await apiClient.post<EcritureLecture>(
        `${racine(entrepriseId)}/mouvements/${mouvementId}/generer-ecriture`,
        donnees,
      );
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["mouvements-stock"] }),
  });

  return { creerEntree, creerSortie, genererEcriture };
}


export function useMutationsInventairesPhysiques(entrepriseId: Ref<string | null | undefined>) {
  const queryClient = useQueryClient();

  const creer = useMutation({
    mutationFn: async (donnees: InventairePhysiqueCreation) => {
      const { data } = await apiClient.post<InventairePhysique>(
        `${racine(entrepriseId)}/inventaires-physiques`,
        donnees,
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inventaires-physiques"] });
      queryClient.invalidateQueries({ queryKey: ["mouvements-stock"] });
      queryClient.invalidateQueries({ queryKey: ["article-detail"] });
      queryClient.invalidateQueries({ queryKey: ["articles"] });
    },
  });

  return { creer };
}