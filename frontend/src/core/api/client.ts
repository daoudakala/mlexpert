/**
 * Client HTTP unique de l'application.
 *
 * `withCredentials: true` est ce qui fait voyager les cookies HttpOnly
 * (`mlexpert_acces` / `mlexpert_rafraichissement`, voir
 * app/modules/auth/router.py) avec chaque requête — rien côté JS n'a
 * jamais accès à leur valeur.
 *
 * Intercepteur 401 : une seule tentative de rafraîchissement automatique
 * via `/auth/rafraichir` (qui pose un nouveau cookie d'accès), puis on
 * rejoue la requête d'origine. Si le rafraîchissement échoue aussi (session
 * vraiment expirée), on laisse l'erreur remonter — c'est `router/index.ts`
 * / `useAuth.ts` qui décident de rediriger vers l'écran de connexion.
 */
import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  withCredentials: true,
});

let rafraichissementEnCours: Promise<void> | null = null;

async function rafraichir(): Promise<void> {
  if (!rafraichissementEnCours) {
    rafraichissementEnCours = apiClient
      .post("/auth/rafraichir")
      .then(() => undefined)
      .finally(() => {
        rafraichissementEnCours = null;
      });
  }
  return rafraichissementEnCours;
}

interface ConfigAvecRetry extends InternalAxiosRequestConfig {
  _dejaRejouee?: boolean;
}

apiClient.interceptors.response.use(
  (reponse) => reponse,
  async (erreur: AxiosError) => {
    const configOrigine = erreur.config as ConfigAvecRetry | undefined;
    const estRouteAuth = configOrigine?.url?.startsWith("/auth/");

    if (
      erreur.response?.status === 401 &&
      configOrigine &&
      !configOrigine._dejaRejouee &&
      !estRouteAuth
    ) {
      configOrigine._dejaRejouee = true;
      try {
        await rafraichir();
        return apiClient.request(configOrigine);
      } catch (erreurRafraichissement) {
        // Session réellement expirée : on laisse remonter l'erreur 401
        // d'origine, pas celle du rafraîchissement, pour que l'appelant
        // garde un message cohérent.
        return Promise.reject(erreur);
      }
    }
    return Promise.reject(erreur);
  },
);
