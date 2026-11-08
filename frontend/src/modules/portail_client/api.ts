/**
 * Accès réseau du module portail_client. Sert les deux usages du même
 * backend (voir router.py) : la page client (documents visibles, mes
 * demandes, nouvelle demande) et la page cabinet (toutes les demandes,
 * traiter/refuser) — `mes_demandes_seulement` est le paramètre qui
 * distingue les deux côté client, pas une route séparée.
 *
 * Le téléchargement réutilise le même motif que `telechargerDocument` du
 * module documents (flux binaire, pas JSON), sur une route différente
 * (`.../portail-client/.../telecharger`, qui vérifie la visibilité client
 * plutôt que de servir n'importe quel document de l'entreprise).
 */
import { computed, type Ref } from "vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";

import { apiClient } from "@/core/api/client";
import type { Document } from "@/modules/documents/types";
import type { CommentaireDemande, DemandeDocument, DemandeDocumentCreation } from "./types";

function racine(entrepriseId: Ref<string | null | undefined>): string {
  return `/portail-client/entreprises/${entrepriseId.value}`;
}

export interface FiltresDocumentsVisibles {
  categorie?: string | null;
  exerciceId?: string | null;
  dossierPermanentSeulement?: boolean;
}

export function useDocumentsVisibles(
  entrepriseId: Ref<string | null | undefined>,
  filtres: Ref<FiltresDocumentsVisibles>,
) {
  return useQuery({
    queryKey: computed(() => ["documents-visibles", entrepriseId.value, filtres.value]),
    queryFn: async () => {
      const { data } = await apiClient.get<Document[]>(`${racine(entrepriseId)}/documents`, {
        params: {
          categorie: filtres.value.categorie || undefined,
          exercice_id: filtres.value.exerciceId || undefined,
          dossier_permanent_seulement: filtres.value.dossierPermanentSeulement ?? false,
        },
      });
      return data;
    },
    enabled: () => !!entrepriseId.value,
  });
}

/** Télécharge un document partagé — même motif que `telechargerDocument`
 * du module documents, sur la route dédiée au portail client. */
export async function telechargerDocumentVisible(
  entrepriseId: Ref<string | null | undefined>,
  document: Document,
): Promise<void> {
  const reponse = await apiClient.get(
    `${racine(entrepriseId)}/documents/${document.id}/telecharger`,
    { responseType: "blob" },
  );
  const url = window.URL.createObjectURL(new Blob([reponse.data]));
  const lien = window.document.createElement("a");
  lien.href = url;
  lien.download = document.nom_fichier;
  lien.click();
  window.URL.revokeObjectURL(url);
}

export interface FiltresDemandes {
  statut?: string | null;
  mesDemandesSeulement?: boolean;
}

export function useListeDemandes(
  entrepriseId: Ref<string | null | undefined>,
  filtres: Ref<FiltresDemandes>,
) {
  return useQuery({
    queryKey: computed(() => ["demandes-documents", entrepriseId.value, filtres.value]),
    queryFn: async () => {
      const { data } = await apiClient.get<DemandeDocument[]>(`${racine(entrepriseId)}/demandes`, {
        params: {
          statut: filtres.value.statut || undefined,
          mes_demandes_seulement: filtres.value.mesDemandesSeulement ?? false,
        },
      });
      return data;
    },
    enabled: () => !!entrepriseId.value,
  });
}

export function useMutationsDemandes(entrepriseId: Ref<string | null | undefined>) {
  const queryClient = useQueryClient();
  const invalider = () => queryClient.invalidateQueries({ queryKey: ["demandes-documents"] });

  const creer = useMutation({
    mutationFn: async (donnees: DemandeDocumentCreation) => {
      const { data } = await apiClient.post<DemandeDocument>(`${racine(entrepriseId)}/demandes`, donnees);
      return data;
    },
    onSuccess: invalider,
  });

  const traiter = useMutation({
    mutationFn: async ({ id, documentId }: { id: string; documentId: string }) => {
      const { data } = await apiClient.post<DemandeDocument>(
        `${racine(entrepriseId)}/demandes/${id}/traiter`,
        { document_id: documentId },
      );
      return data;
    },
    onSuccess: invalider,
  });

  const refuser = useMutation({
    mutationFn: async ({ id, motif }: { id: string; motif: string }) => {
      const { data } = await apiClient.post<DemandeDocument>(
        `${racine(entrepriseId)}/demandes/${id}/refuser`,
        { motif },
      );
      return data;
    },
    onSuccess: invalider,
  });

  return { creer, traiter, refuser };
}

// --- Commentaires (messagerie contextualisée) ---------------------------------

export function useCommentairesDemande(
  entrepriseId: Ref<string | null | undefined>,
  demandeId: Ref<string | null | undefined>,
) {
  return useQuery({
    queryKey: computed(() => ["commentaires-demande", entrepriseId.value, demandeId.value]),
    queryFn: async () => {
      const { data } = await apiClient.get<CommentaireDemande[]>(
        `${racine(entrepriseId)}/demandes/${demandeId.value}/commentaires`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value && !!demandeId.value,
  });
}

export function useMutationAjouterCommentaire(entrepriseId: Ref<string | null | undefined>) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ demandeId, message }: { demandeId: string; message: string }) => {
      const { data } = await apiClient.post<CommentaireDemande>(
        `${racine(entrepriseId)}/demandes/${demandeId}/commentaires`,
        { message },
      );
      return data;
    },
    onSuccess: (_donnees, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["commentaires-demande", entrepriseId.value, variables.demandeId],
      });
    },
  });
}