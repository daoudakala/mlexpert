<script setup lang="ts">
/**
 * Fil de commentaires d'une demande — réutilisé par PortailAccueil.vue
 * (client) et DemandesClientsListe.vue (cabinet), même panneau des deux
 * côtés puisque le backend ne distingue pas les deux par la route (voir
 * router.py : un seul couple GET/POST, permission `portail_client.consulter`
 * commune). Pas d'édition ni de suppression d'un message envoyé.
 */
import { computed, reactive, ref } from "vue";

import { useAuth } from "@/core/auth/useAuth";
import { messageErreur } from "@/core/api/erreurs";
import { useCommentairesDemande, useMutationAjouterCommentaire } from "./api";
import type { DemandeDocument } from "./types";

const props = defineProps<{
  entrepriseId: string | null | undefined;
  demande: DemandeDocument;
}>();

const { utilisateur } = useAuth();

const entrepriseIdRef = computed(() => props.entrepriseId);
const demandeIdRef = computed(() => props.demande.id);

const { data: commentaires, isLoading } = useCommentairesDemande(entrepriseIdRef, demandeIdRef);
const { mutateAsync: ajouter, isPending } = useMutationAjouterCommentaire(entrepriseIdRef);

const formulaire = reactive({ message: "" });
const erreur = ref<string | null>(null);

function auteur(commentaireAuteurId: string): string {
  if (commentaireAuteurId === utilisateur.value?.id) return "Vous";
  return commentaireAuteurId === props.demande.demandeur_id ? "Le client" : "Le cabinet";
}

function formaterDate(valeur: string): string {
  return new Date(valeur).toLocaleString("fr-FR");
}

async function envoyer(): Promise<void> {
  if (!formulaire.message.trim()) return;
  erreur.value = null;
  try {
    await ajouter({ demandeId: props.demande.id, message: formulaire.message.trim() });
    formulaire.message = "";
  } catch (e) {
    erreur.value = messageErreur(e);
  }
}
</script>

<template>
  <div class="space-y-3 rounded-lg border border-border bg-surface p-4">
    <h3 class="text-sm font-semibold text-text">Échanges sur « {{ demande.libelle }} »</h3>

    <div v-if="isLoading" class="text-sm text-text-muted">Chargement...</div>
    <div v-else-if="(commentaires ?? []).length === 0" class="text-sm text-text-muted">
      Aucun message pour le moment.
    </div>
    <ul v-else class="max-h-72 space-y-2 overflow-y-auto">
      <li
        v-for="commentaire in commentaires"
        :key="commentaire.id"
        class="rounded-md bg-surface-muted p-2.5 text-sm"
      >
        <div class="mb-1 flex items-center justify-between text-xs text-text-muted">
          <span class="font-medium text-text">{{ auteur(commentaire.auteur_id) }}</span>
          <span>{{ formaterDate(commentaire.cree_le) }}</span>
        </div>
        <p class="whitespace-pre-wrap text-text">{{ commentaire.message }}</p>
      </li>
    </ul>

    <form class="flex items-start gap-2" @submit.prevent="envoyer">
      <textarea
        v-model="formulaire.message"
        rows="2"
        maxlength="2000"
        placeholder="Écrire un message..."
        class="flex-1 rounded-md border border-border px-3 py-2 text-sm text-text"
      />
      <button
        type="submit"
        :disabled="isPending.value || !formulaire.message.trim()"
        class="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60"
      >
        Envoyer
      </button>
    </form>
    <p v-if="erreur" class="text-sm text-danger">{{ erreur }}</p>
  </div>
</template>