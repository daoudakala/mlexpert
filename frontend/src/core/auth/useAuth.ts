/**
 * Façade fine autour de `auth.store.ts` — à importer dans les composants
 * plutôt que le store directement, pour garder un seul point d'entrée côté
 * composants si la logique d'auth évolue.
 */
import { storeToRefs } from "pinia";

import { useAuthStore } from "./auth.store";

export function useAuth() {
  const store = useAuthStore();
  // storeToRefs conserve la réactivité sur les propriétés déstructurées
  // (un accès direct à store.utilisateur la perdrait).
  const {
    utilisateur,
    estConnecte,
    estAdministrateurPlateforme,
    contexteActif,
    contextes,
    initialise,
    enChargement,
  } = storeToRefs(store);

  return {
    utilisateur,
    estConnecte,
    estAdministrateurPlateforme,
    contexteActif,
    contextes,
    initialise,
    enChargement,
    aPermission: store.aPermission,
    definirEntrepriseActive: store.definirEntrepriseActive,
    connecter: store.connecter,
    deconnecter: store.deconnecter,
    chargerContexte: store.chargerContexte,
  };
}
