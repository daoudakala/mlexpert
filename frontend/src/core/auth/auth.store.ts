/**
 * État global d'authentification : l'utilisateur connecté, son portefeuille
 * d'entreprises/rôles/permissions (voir GET /droits/moi/contextes), et
 * l'entreprise actuellement sélectionnée.
 *
 * Réservé à Pinia, conformément à l'architecture validée : seul l'état
 * vraiment global (auth, entreprise courante, chrome de l'UI) vit ici — le
 * reste (listes, formulaires métier) passe par TanStack Query au plus près
 * des composants.
 */
import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { apiClient } from "@/core/api/client";
import type { ContexteAccesUtilisateur } from "@/modules/droits/types";
import type { MonProfil } from "@/modules/utilisateurs/types";

const CLE_ENTREPRISE_ACTIVE = "mlexpert.entreprise_active_id";

export const useAuthStore = defineStore("auth", () => {
  const utilisateur = ref<MonProfil | null>(null);
  const contextes = ref<ContexteAccesUtilisateur[]>([]);
  const entrepriseActiveId = ref<string | null>(
    localStorage.getItem(CLE_ENTREPRISE_ACTIVE),
  );
  const initialise = ref(false);
  const enChargement = ref(false);

  const estConnecte = computed(() => utilisateur.value !== null);

  /** Administrateur plateforme : mécanisme séparé des permissions par
   * entreprise (voir ServiceDroits.est_administrateur_plateforme côté
   * backend). Utilisé par les pages d'administration (entreprises,
   * utilisateurs, rôles globaux) pour savoir si elles doivent s'afficher. */
  const estAdministrateurPlateforme = computed(
    () => utilisateur.value?.administrateur_plateforme ?? false,
  );

  const contexteActif = computed<ContexteAccesUtilisateur | null>(() => {
    if (contextes.value.length === 0) return null;
    const correspondant = contextes.value.find(
      (c) => c.entreprise.id === entrepriseActiveId.value,
    );
    return correspondant ?? contextes.value[0] ?? null;
  });

  const codesPermissions = computed<Set<string>>(
    () => new Set(contexteActif.value?.codes_permissions ?? []),
  );

  function aPermission(code: string): boolean {
    return codesPermissions.value.has(code);
  }

  function definirEntrepriseActive(entrepriseId: string): void {
    entrepriseActiveId.value = entrepriseId;
    localStorage.setItem(CLE_ENTREPRISE_ACTIVE, entrepriseId);
  }

  /** Recharge utilisateur + portefeuille depuis le backend. À appeler après
   * connexion, et une fois au démarrage de l'app pour restaurer une session
   * existante (cookie encore valide). */
  async function chargerContexte(): Promise<void> {
    enChargement.value = true;
    try {
      const [{ data: moi }, { data: contextesCharges }] = await Promise.all([
        apiClient.get<MonProfil>("/utilisateurs/moi"),
        apiClient.get<ContexteAccesUtilisateur[]>("/droits/moi/contextes"),
      ]);
      utilisateur.value = moi;
      contextes.value = contextesCharges;
      if (
        entrepriseActiveId.value === null ||
        !contextesCharges.some((c) => c.entreprise.id === entrepriseActiveId.value)
      ) {
        const premiere = contextesCharges[0];
        if (premiere) definirEntrepriseActive(premiere.entreprise.id);
      }
    } finally {
      enChargement.value = false;
      initialise.value = true;
    }
  }

  async function connecter(email: string, mot_de_passe: string): Promise<void> {
    await apiClient.post("/auth/connexion", { email, mot_de_passe });
    await chargerContexte();
  }

  async function deconnecter(): Promise<void> {
    try {
      await apiClient.post("/auth/deconnexion");
    } finally {
      utilisateur.value = null;
      contextes.value = [];
      entrepriseActiveId.value = null;
      localStorage.removeItem(CLE_ENTREPRISE_ACTIVE);
    }
  }

  return {
    utilisateur,
    contextes,
    entrepriseActiveId,
    initialise,
    enChargement,
    estConnecte,
    estAdministrateurPlateforme,
    contexteActif,
    aPermission,
    definirEntrepriseActive,
    chargerContexte,
    connecter,
    deconnecter,
  };
});
