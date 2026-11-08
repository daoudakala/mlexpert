/**
 * Accès réseau du module documents. Pas de `useCrudRessource` générique :
 * le dépôt est un upload multipart (pas un POST JSON), le téléchargement
 * renvoie un flux binaire à faire enregistrer par le navigateur (pas une
 * réponse JSON), et la visibilité client est une route dédiée avec un
 * paramètre de requête — rien de tout ça ne rentre dans un CRUD classique.
 */
import { computed, type Ref } from "vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";

import { apiClient } from "@/core/api/client";
import type { CategorieDocument, Document, DocumentMiseAJour } from "./types";

function racine(entrepriseId: Ref<string | null | undefined>): string {
  return `/documents/entreprises/${entrepriseId.value}`;
}

export interface FiltresDocuments {
  categorie?: CategorieDocument | null;
  exerciceId?: string | null;
  dossierPermanentSeulement?: boolean;
}

export function useListeDocuments(
  entrepriseId: Ref<string | null | undefined>,
  filtres: Ref<FiltresDocuments>,
) {
  return useQuery({
    queryKey: computed(() => ["documents", entrepriseId.value, filtres.value]),
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

/** Pièces justificatives déjà rattachées à une écriture — utilisé par la
 * page de détail d'une écriture (module comptabilité). */
export function useDocumentsPourEcriture(
  entrepriseId: Ref<string | null | undefined>,
  ecritureId: Ref<string | null>,
) {
  return useQuery({
    queryKey: computed(() => ["documents-pour-ecriture", entrepriseId.value, ecritureId.value]),
    queryFn: async () => {
      const { data } = await apiClient.get<Document[]>(`${racine(entrepriseId)}/documents`, {
        params: { ecriture_id: ecritureId.value },
      });
      return data;
    },
    enabled: () => !!entrepriseId.value && !!ecritureId.value,
  });
}

export function useDocument(
  entrepriseId: Ref<string | null | undefined>,
  documentId: Ref<string | null>,
) {
  return useQuery({
    queryKey: ["document-detail", entrepriseId, documentId],
    queryFn: async () => {
      const { data } = await apiClient.get<Document>(
        `${racine(entrepriseId)}/documents/${documentId.value}`,
      );
      return data;
    },
    enabled: () => !!entrepriseId.value && !!documentId.value,
  });
}

export interface DepotDocument {
  fichier: File;
  categorie: CategorieDocument;
  description?: string | null;
  date_document?: string | null;
  date_expiration?: string | null;
  exercice_id?: string | null;
  ecriture_id?: string | null;
}

export function useMutationsDocuments(entrepriseId: Ref<string | null | undefined>) {
  const queryClient = useQueryClient();
  const invalider = () => queryClient.invalidateQueries({ queryKey: ["documents"] });
  const invaliderDetail = () => queryClient.invalidateQueries({ queryKey: ["document-detail"] });
  const invaliderPourEcriture = () =>
    queryClient.invalidateQueries({ queryKey: ["documents-pour-ecriture"] });

  const deposer = useMutation({
    mutationFn: async (donnees: DepotDocument) => {
      const formulaire = new FormData();
      formulaire.append("fichier", donnees.fichier);
      formulaire.append("categorie", donnees.categorie);
      if (donnees.description) formulaire.append("description", donnees.description);
      if (donnees.date_document) formulaire.append("date_document", donnees.date_document);
      if (donnees.date_expiration) formulaire.append("date_expiration", donnees.date_expiration);
      if (donnees.exercice_id) formulaire.append("exercice_id", donnees.exercice_id);
      if (donnees.ecriture_id) formulaire.append("ecriture_id", donnees.ecriture_id);
      const { data } = await apiClient.post<Document>(`${racine(entrepriseId)}/documents`, formulaire);
      return data;
    },
    onSuccess: () => {
      invalider();
      invaliderPourEcriture();
    },
  });

  const rattacherEcriture = useMutation({
    mutationFn: async ({ id, ecritureId }: { id: string; ecritureId: string }) => {
      const { data } = await apiClient.post<Document>(
        `${racine(entrepriseId)}/documents/${id}/rattacher-ecriture`,
        { ecriture_id: ecritureId },
      );
      return data;
    },
    onSuccess: () => {
      invalider();
      invaliderDetail();
      invaliderPourEcriture();
    },
  });

  const detacherEcriture = useMutation({
    mutationFn: async (id: string) => {
      const { data } = await apiClient.post<Document>(
        `${racine(entrepriseId)}/documents/${id}/detacher-ecriture`,
      );
      return data;
    },
    onSuccess: () => {
      invalider();
      invaliderDetail();
      invaliderPourEcriture();
    },
  });

  const modifier = useMutation({
    mutationFn: async ({ id, donnees }: { id: string; donnees: DocumentMiseAJour }) => {
      const { data } = await apiClient.patch<Document>(
        `${racine(entrepriseId)}/documents/${id}`,
        donnees,
      );
      return data;
    },
    onSuccess: () => {
      invalider();
      invaliderDetail();
    },
  });

  const definirVisibiliteClient = useMutation({
    mutationFn: async ({ id, visibleClient }: { id: string; visibleClient: boolean }) => {
      const { data } = await apiClient.post<Document>(
        `${racine(entrepriseId)}/documents/${id}/visibilite-client`,
        null,
        { params: { visible_client: visibleClient } },
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
      await apiClient.post(`${racine(entrepriseId)}/documents/${id}/supprimer`);
    },
    onSuccess: invalider,
  });

  return { deposer, modifier, definirVisibiliteClient, supprimer, rattacherEcriture, detacherEcriture };
}

/** Télécharge un document : récupère le flux binaire et déclenche
 * l'enregistrement par le navigateur via une URL d'objet temporaire —
 * le backend renvoie le contenu brut, pas du JSON (voir router.py). */
export async function telechargerDocument(
  entrepriseId: Ref<string | null | undefined>,
  document: Document,
): Promise<void> {
  const reponse = await apiClient.get(`${racine(entrepriseId)}/documents/${document.id}/telecharger`, {
    responseType: "blob",
  });
  const url = window.URL.createObjectURL(new Blob([reponse.data]));
  const lien = window.document.createElement("a");
  lien.href = url;
  lien.download = document.nom_fichier;
  lien.click();
  window.URL.revokeObjectURL(url);
}