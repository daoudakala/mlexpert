import { createRouter, createWebHistory } from "vue-router";

import { useAuthStore } from "@/core/auth/auth.store";

/**
 * Convention de méta sur chaque route métier :
 *   meta.permission: "<ressource>.<action>" — vérifiée contre les
 *     codes_permissions de l'entreprise active (voir auth.store.ts).
 *   meta.public: true — route accessible sans session (login, portail
 *     client si un jour il a ses propres pages publiques).
 *   meta.adminPlateforme: true — réservée à l'administrateur plateforme
 *     (mécanisme séparé des permissions par entreprise, voir
 *     estAdministrateurPlateforme dans auth.store.ts) : entreprises,
 *     utilisateurs et rôles sont administrés à ce niveau, pas par
 *     codes_permissions.
 */
const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/connexion",
      name: "connexion",
      component: () => import("@/modules/utilisateurs/ConnexionPage.vue"),
      meta: { public: true },
    },
    {
      path: "/",
      component: () => import("@/layouts/AppLayout.vue"),
      children: [
        {
          path: "",
          name: "accueil",
          component: () => import("@/modules/dashboards/DashboardPage.vue"),
        },
        {
          path: "tiers",
          name: "tiers.liste",
          component: () => import("@/modules/tiers/TiersListe.vue"),
          meta: { permission: "tiers.consulter" },
        },
        {
          path: "tiers/nouveau",
          name: "tiers.nouveau",
          component: () => import("@/modules/tiers/TiersFormulaire.vue"),
          meta: { permission: "tiers.creer" },
        },
        {
          path: "tiers/:id",
          name: "tiers.modifier",
          component: () => import("@/modules/tiers/TiersFormulaire.vue"),
          meta: { permission: "tiers.consulter" },
        },
        {
          path: "tresorerie/comptes-bancaires",
          name: "tresorerie.comptes-bancaires",
          component: () => import("@/modules/tresorerie/ComptesBancairesListe.vue"),
          meta: { permission: "compte_bancaire.consulter" },
        },
        {
          path: "tresorerie/comptes-bancaires/nouveau",
          name: "tresorerie.compte-bancaire.nouveau",
          component: () => import("@/modules/tresorerie/CompteBancaireFormulaire.vue"),
          meta: { permission: "compte_bancaire.creer" },
        },
        {
          path: "tresorerie/comptes-bancaires/:id",
          name: "tresorerie.compte-bancaire",
          component: () => import("@/modules/tresorerie/CompteBancaireDetail.vue"),
          meta: { permission: "compte_bancaire.consulter" },
        },
        {
          path: "tresorerie/comptes-bancaires/:id/releves/nouveau",
          name: "tresorerie.releve.nouveau",
          component: () => import("@/modules/tresorerie/ReleveFormulaire.vue"),
          meta: { permission: "releve.creer" },
        },
        {
          path: "tresorerie/releves/:releveId",
          name: "tresorerie.releve",
          component: () => import("@/modules/tresorerie/ReleveFormulaire.vue"),
          meta: { permission: "releve.consulter" },
        },
        {
          path: "tresorerie/comptes-bancaires/:id/rapprochement",
          name: "tresorerie.rapprochement",
          component: () => import("@/modules/tresorerie/RapprochementPage.vue"),
          meta: { permission: "releve.consulter" },
        },
        {
          path: "comptabilite/comptes",
          name: "comptabilite.comptes",
          component: () => import("@/modules/comptabilite/ComptesListe.vue"),
          meta: { permission: "compte.consulter" },
        },
        {
          path: "comptabilite/journaux",
          name: "comptabilite.journaux",
          component: () => import("@/modules/comptabilite/JournauxListe.vue"),
          meta: { permission: "journal.consulter" },
        },
        {
          path: "comptabilite/modeles-ecriture",
          name: "comptabilite.modeles-ecriture",
          component: () => import("@/modules/comptabilite/ModelesEcritureListe.vue"),
          meta: { permission: "modele_ecriture.consulter" },
        },
        {
          path: "comptabilite/ecritures",
          name: "comptabilite.ecritures",
          component: () => import("@/modules/comptabilite/EcrituresListe.vue"),
          meta: { permission: "ecriture.consulter" },
        },
        {
          path: "comptabilite/ecritures/nouvelle",
          name: "comptabilite.ecriture.nouvelle",
          component: () => import("@/modules/comptabilite/EcritureFormulaire.vue"),
          meta: { permission: "ecriture.creer" },
        },
        {
          path: "comptabilite/ecritures/:id",
          name: "comptabilite.ecriture",
          component: () => import("@/modules/comptabilite/EcritureFormulaire.vue"),
          meta: { permission: "ecriture.consulter" },
        },
        {
          path: "comptabilite/lettrage",
          name: "comptabilite.lettrage",
          component: () => import("@/modules/comptabilite/LettrageManuel.vue"),
          meta: { permission: "ecriture.consulter" },
        },
        {
          path: "comptabilite/ecritures-recurrentes",
          name: "comptabilite.ecritures-recurrentes",
          component: () => import("@/modules/comptabilite/EcrituresRecurrentesListe.vue"),
          meta: { permission: "ecriture_recurrente.consulter" },
        },
        {
          path: "immobilisations",
          name: "immobilisations.liste",
          component: () => import("@/modules/immobilisations/ImmobilisationsListe.vue"),
          meta: { permission: "immobilisation.consulter" },
        },
        {
          path: "immobilisations/nouvelle",
          name: "immobilisations.nouvelle",
          component: () => import("@/modules/immobilisations/ImmobilisationFormulaire.vue"),
          meta: { permission: "immobilisation.creer" },
        },
        {
          path: "immobilisations/a-confirmer",
          name: "immobilisations.a-confirmer",
          component: () => import("@/modules/immobilisations/AcquisitionsAConfirmer.vue"),
          meta: { permission: "immobilisation.creer" },
        },
        {
          path: "immobilisations/:id",
          name: "immobilisations.detail",
          component: () => import("@/modules/immobilisations/ImmobilisationDetail.vue"),
          meta: { permission: "immobilisation.consulter" },
        },
        {
          path: "provisions",
          name: "provisions.liste",
          component: () => import("@/modules/provisions/ProvisionsListe.vue"),
          meta: { permission: "provision.consulter" },
        },
        {
          path: "provisions/nouvelle",
          name: "provisions.nouvelle",
          component: () => import("@/modules/provisions/ProvisionFormulaire.vue"),
          meta: { permission: "provision.creer" },
        },
        {
          path: "provisions/:id",
          name: "provisions.detail",
          component: () => import("@/modules/provisions/ProvisionDetail.vue"),
          meta: { permission: "provision.consulter" },
        },
        {
          path: "regularisations",
          name: "regularisations.liste",
          component: () => import("@/modules/regularisations/RegularisationsListe.vue"),
          meta: { permission: "regularisation.consulter" },
        },
        {
          path: "regularisations/nouvelle",
          name: "regularisations.nouvelle",
          component: () => import("@/modules/regularisations/RegularisationFormulaire.vue"),
          meta: { permission: "regularisation.creer" },
        },
        {
          path: "documents",
          name: "documents.liste",
          component: () => import("@/modules/documents/DocumentsListe.vue"),
          meta: { permission: "document.consulter" },
        },
        {
          path: "interlocuteurs",
          name: "interlocuteurs.liste",
          component: () => import("@/modules/interlocuteurs/InterlocuteursListe.vue"),
          meta: { permission: "interlocuteur.consulter" },
        },
        {
          path: "stocks",
          name: "stocks.liste",
          component: () => import("@/modules/stocks/ArticlesListe.vue"),
          meta: { permission: "article.consulter" },
        },
        {
          path: "stocks/:id",
          name: "stocks.article",
          component: () => import("@/modules/stocks/ArticleDetail.vue"),
          meta: { permission: "article.consulter" },
        },
        {
          path: "dashboards",
          name: "dashboards.reporting",
          component: () => import("@/modules/dashboards/ReportingPage.vue"),
          meta: { permission: "dashboard.consulter" },
        },
        {
          path: "dashboards/balance-generale",
          name: "dashboards.balance-generale",
          component: () => import("@/modules/dashboards/BalanceGeneralePage.vue"),
          meta: { permission: "dashboard.consulter" },
        },
        {
          path: "dashboards/grand-livre",
          name: "dashboards.grand-livre",
          component: () => import("@/modules/dashboards/GrandLivrePage.vue"),
          meta: { permission: "dashboard.consulter" },
        },
        {
          path: "demandes-clients",
          name: "portail_client.demandes",
          component: () => import("@/modules/portail_client/DemandesClientsListe.vue"),
          meta: { permission: "portail_client.consulter" },
        },
        {
          path: "journal-activite",
          name: "journal_activite.page",
          component: () => import("@/modules/journal_activite/JournalActivitePage.vue"),
          meta: { permission: "journal_activite.consulter" },
        },
        {
          path: "mon-profil",
          name: "utilisateurs.mon-profil",
          component: () => import("@/modules/utilisateurs/MonProfilPage.vue"),
        },
        {
          path: "mes-preferences-notifications",
          name: "notifications.preferences",
          component: () => import("@/modules/notifications/PreferencesNotificationsPage.vue"),
          meta: { permission: "notification.consulter" },
        },
        {
          path: "administration/utilisateurs",
          name: "utilisateurs.liste",
          component: () => import("@/modules/utilisateurs/UtilisateursListe.vue"),
          meta: { adminPlateforme: true },
        },
        {
          path: "administration/entreprises",
          name: "entreprises.liste",
          component: () => import("@/modules/entreprises/EntreprisesListe.vue"),
          meta: { adminPlateforme: true },
        },
        {
          path: "administration/entreprises/nouvelle",
          name: "entreprises.nouvelle",
          component: () => import("@/modules/entreprises/EntrepriseFormulaire.vue"),
          meta: { adminPlateforme: true },
        },
        {
          path: "administration/entreprises/:id",
          name: "entreprises.modifier",
          component: () => import("@/modules/entreprises/EntrepriseFormulaire.vue"),
          meta: { adminPlateforme: true },
        },
        {
          path: "administration/roles",
          name: "droits.roles",
          component: () => import("@/modules/droits/RolesListe.vue"),
          meta: { adminPlateforme: true },
        },
        {
          path: "exercices",
          name: "exercices.liste",
          component: () => import("@/modules/exercices/ExercicesListe.vue"),
          meta: { permission: "exercice.consulter" },
        },
        {
          path: "exercices/:id",
          name: "exercices.detail",
          component: () => import("@/modules/exercices/ExerciceDetail.vue"),
          meta: { permission: "periode.consulter" },
        },
        {
          path: "affectations",
          name: "droits.affectations",
          component: () => import("@/modules/droits/AffectationsListe.vue"),
          meta: { permission: "droits.consulter" },
        },
        {
          path: "paie/employes",
          name: "paie.employes",
          component: () => import("@/modules/paie/EmployesListe.vue"),
          meta: { permission: "employe.consulter" },
        },
        {
          path: "paie/employes/nouveau",
          name: "paie.employe.nouveau",
          component: () => import("@/modules/paie/EmployeFormulaire.vue"),
          meta: { permission: "employe.creer" },
        },
        {
          path: "paie/employes/:id",
          name: "paie.employe.modifier",
          component: () => import("@/modules/paie/EmployeFormulaire.vue"),
          meta: { permission: "employe.consulter" },
        },
        {
          path: "paie/rubriques",
          name: "paie.rubriques",
          component: () => import("@/modules/paie/RubriquesListe.vue"),
          meta: { permission: "rubrique_paie.consulter" },
        },
        {
          path: "paie/bulletins",
          name: "paie.bulletins",
          component: () => import("@/modules/paie/BulletinsListe.vue"),
          meta: { permission: "bulletin.consulter" },
        },
        {
          path: "paie/bulletins/nouveau",
          name: "paie.bulletin.nouveau",
          component: () => import("@/modules/paie/BulletinFormulaire.vue"),
          meta: { permission: "bulletin.creer" },
        },
        {
          path: "paie/bulletins/:id",
          name: "paie.bulletin",
          component: () => import("@/modules/paie/BulletinFormulaire.vue"),
          meta: { permission: "bulletin.consulter" },
        },
        // Les routes des modules suivants s'ajoutent ici au fur et à
        // mesure, module par module — chacune avec sa meta.permission,
        // sur le même modèle que ci-dessus.
      ],
    },
    {
      path: "/portail",
      component: () => import("@/layouts/PortailClientLayout.vue"),
      children: [
        {
          path: "",
          name: "portail.accueil",
          component: () => import("@/modules/portail_client/PortailAccueil.vue"),
        },
        {
          path: "mes-preferences-notifications",
          name: "portail.notifications.preferences",
          component: () => import("@/modules/notifications/PreferencesNotificationsPage.vue"),
          meta: { permission: "notification.consulter" },
        },
      ],
    },
  ],
});

router.beforeEach(async (to) => {
  if (to.meta.public) return true;

  const store = useAuthStore();
  if (!store.initialise) {
    try {
      await store.chargerContexte();
    } catch {
      // Pas de session valide : chargerContexte a échoué (401), on
      // continue vers la redirection de connexion ci-dessous.
    }
  }

  if (!store.estConnecte) {
    return { name: "connexion", query: { suite: to.fullPath } };
  }

  if (to.meta.adminPlateforme && !store.estAdministrateurPlateforme) {
    return { name: "accueil" };
  }

  const permissionRequise = to.meta.permission as string | undefined;
  if (permissionRequise && !store.aPermission(permissionRequise)) {
    return { name: "accueil" };
  }

  return true;
});

export default router;