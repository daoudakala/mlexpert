<script setup lang="ts">
/**
 * Menu latéral de l'application (fond marine, sections, groupes repliables).
 *
 * Toute la structure est décrite dans `sections` ci-dessous : pour ajouter
 * une page, on ajoute une ligne. Chaque entrée est masquée si l'utilisateur
 * n'a pas la permission (ou n'est pas administrateur plateforme quand
 * `admin` est posé) ; un groupe sans entrée visible disparaît, une section
 * sans groupe ni entrée visible aussi.
 *
 * Entrée "active" : même route (par préfixe de nom) ET mêmes valeurs pour
 * les paramètres d'URL listés dans `cles` (ex. ?journal=BQ), `defauts`
 * donnant la valeur implicite quand le paramètre est absent.
 */
import { computed, ref } from "vue";
import { useRoute } from "vue-router";

import { useAuth } from "@/core/auth/useAuth";
import IconeNav from "@/core/ui/IconeNav.vue";
import { useJournaux } from "@/modules/comptabilite/api";

interface Entree {
  libelle: string;
  to: { name: string; query?: Record<string, string> };
  /** Noms de routes (et leurs sous-routes "nom.xxx") pour lesquels l'entrée reste active. */
  actifPour?: string[];
  cles?: string[];
  defauts?: Record<string, string>;
  permission?: string;
  admin?: boolean;
}

interface Groupe {
  id: string;
  libelle: string;
  icone: string;
  enfants: Entree[];
}

interface ElementMenu {
  type: "lien" | "groupe";
  lien?: Entree & { icone: string };
  groupe?: Groupe;
}

interface Section {
  titre: string;
  elements: ElementMenu[];
}

const emit = defineEmits<{ (e: "navigation"): void }>();

const route = useRoute();
const { contexteActif, aPermission, estAdministrateurPlateforme } = useAuth();

// Journaux de l'entreprise active : chacun devient une entrée du groupe
// "Journaux" (liste des écritures filtrée sur ce journal).
const entrepriseJournaux = computed(() =>
  aPermission("journal.consulter") ? contexteActif.value?.entreprise.id : null,
);
const { data: journaux } = useJournaux(entrepriseJournaux);

const entreesJournaux = computed<Entree[]>(() =>
  (journaux.value ?? []).map((j) => ({
    libelle: `${j.libelle} (${j.code})`,
    to: { name: "comptabilite.ecritures", query: { journal: j.code } },
    actifPour: ["comptabilite.ecriture"],
    cles: ["journal"],
    permission: "ecriture.consulter",
  })),
);

const lien = (e: Entree, icone: string): ElementMenu => ({ type: "lien", lien: { ...e, icone } });
const groupe = (id: string, libelle: string, icone: string, enfants: Entree[]): ElementMenu => ({
  type: "groupe",
  groupe: { id, libelle, icone, enfants },
});

const rapport = (
  libelle: string,
  onglet: string,
  extra: Partial<Entree> & { query?: Record<string, string> } = {},
): Entree => {
  const { query, ...reste } = extra;
  return {
    libelle,
    to: { name: "dashboards.reporting", query: { onglet, ...(query ?? {}) } },
    cles: ["onglet", ...(query?.type ? ["type"] : [])],
    defauts: { onglet: "balance", type: "client" },
    permission: "dashboard.consulter",
    ...reste,
  };
};

const sections = computed<Section[]>(() => [
  {
    titre: "Principal",
    elements: [lien({ libelle: "Tableau de bord", to: { name: "accueil" } }, "tableau-bord")],
  },
  {
    titre: "Comptabilité",
    elements: [
      lien(
        { libelle: "Plan comptable", to: { name: "comptabilite.comptes" }, permission: "compte.consulter" },
        "plan-comptable",
      ),
      groupe("journaux", "Journaux", "journaux", [
        ...entreesJournaux.value,
        {
          libelle: "Toutes les écritures",
          to: { name: "comptabilite.ecritures" },
          actifPour: ["comptabilite.ecriture"],
          cles: ["journal"],
          permission: "ecriture.consulter",
        },
        {
          libelle: "Gérer les journaux",
          to: { name: "comptabilite.journaux" },
          permission: "journal.consulter",
        },
      ]),
      lien(
        {
          libelle: "Modèles d'écriture",
          to: { name: "comptabilite.modeles-ecriture" },
          permission: "modele_ecriture.consulter",
        },
        "modeles-ecriture",
      ),
      lien(
        { libelle: "Lettrage", to: { name: "comptabilite.lettrage" }, permission: "ecriture.consulter" },
        "lettrage",
      ),
      lien(
        {
          libelle: "Écritures récurrentes",
          to: { name: "comptabilite.ecritures-recurrentes" },
          permission: "ecriture_recurrente.consulter",
        },
        "ecritures-recurrentes",
      ),
      lien(
        { libelle: "Exercices", to: { name: "exercices.liste" }, actifPour: ["exercices"], permission: "exercice.consulter" },
        "exercices",
      ),
    ],
  },
  {
    titre: "États",
    elements: [
      lien(rapport("Grand livre", "grand-livre"), "grand-livre"),
      groupe("balances", "Balances", "balance", [
        rapport("Balance générale", "balance"),
        rapport("Comparaison N-1", "comparaison"),
        rapport("Balance âgée", "balance-agee", { query: { type: "client" } }),
      ]),
      groupe("etats-financiers", "États financiers", "dashboards", [
        rapport("Compte de résultat", "resultat"),
        rapport("Résultat détaillé", "resultat-detaille"),
        rapport("Bilan", "bilan"),
      ]),
      groupe("pilotage", "Pilotage", "dashboards", [
        rapport("Échéancier", "echeancier", { query: { type: "client" } }),
        rapport("Prévision de trésorerie", "prevision-tresorerie"),
        rapport("Tableaux de pilotage", "pilotage"),
      ]),
      lien(
        {
          libelle: "Immobilisations",
          to: { name: "immobilisations.liste" },
          actifPour: ["immobilisations"],
          permission: "immobilisation.consulter",
        },
        "immobilisations",
      ),
      lien(
        {
          libelle: "Provisions",
          to: { name: "provisions.liste" },
          actifPour: ["provisions"],
          permission: "provision.consulter",
        },
        "provisions",
      ),
      lien(
        {
          libelle: "Régularisations (CCA/PCA)",
          to: { name: "regularisations.liste" },
          actifPour: ["regularisations"],
          permission: "regularisation.consulter",
        },
        "regularisations",
      ),
      lien(
        {
          libelle: "Trésorerie",
          to: { name: "tresorerie.comptes-bancaires" },
          actifPour: ["tresorerie"],
          permission: "compte_bancaire.consulter",
        },
        "tresorerie",
      ),
      lien(
        { libelle: "Stocks", to: { name: "stocks.liste" }, actifPour: ["stocks"], permission: "article.consulter" },
        "stocks",
      ),
    ],
  },
  {
    titre: "Tiers",
    elements: [
      lien(
        {
          libelle: "Clients",
          to: { name: "tiers.liste", query: { role: "client" } },
          cles: ["role"],
          permission: "tiers.consulter",
        },
        "tiers",
      ),
      lien(
        {
          libelle: "Fournisseurs",
          to: { name: "tiers.liste", query: { role: "fournisseur" } },
          cles: ["role"],
          permission: "tiers.consulter",
        },
        "fournisseurs",
      ),
      lien(
        {
          libelle: "Tous les tiers",
          to: { name: "tiers.liste" },
          actifPour: ["tiers"],
          cles: ["role"],
          permission: "tiers.consulter",
        },
        "tiers",
      ),
      lien(
        {
          libelle: "Interlocuteurs",
          to: { name: "interlocuteurs.liste" },
          permission: "interlocuteur.consulter",
        },
        "interlocuteurs",
      ),
    ],
  },
  {
    titre: "Paie",
    elements: [
      lien(
        { libelle: "Employés", to: { name: "paie.employes" }, actifPour: ["paie.employe"], permission: "employe.consulter" },
        "employes",
      ),
      lien(
        { libelle: "Rubriques de paie", to: { name: "paie.rubriques" }, permission: "rubrique_paie.consulter" },
        "rubriques-paie",
      ),
      lien(
        { libelle: "Bulletins de paie", to: { name: "paie.bulletins" }, actifPour: ["paie.bulletin"], permission: "bulletin.consulter" },
        "bulletins-paie",
      ),
    ],
  },
  {
    titre: "Échanges",
    elements: [
      lien({ libelle: "Documents", to: { name: "documents.liste" }, permission: "document.consulter" }, "documents"),
      lien(
        {
          libelle: "Demandes clients",
          to: { name: "portail_client.demandes" },
          permission: "portail_client.consulter",
        },
        "portail-client",
      ),
    ],
  },
  {
    titre: "Administration",
    elements: [
      groupe("multi-societes", "Multi-sociétés", "entreprises", [
        { libelle: "Entreprises", to: { name: "entreprises.liste" }, actifPour: ["entreprises"], admin: true },
      ]),
      groupe("utilisateurs-roles", "Utilisateurs & rôles", "utilisateurs-admin", [
        { libelle: "Utilisateurs", to: { name: "utilisateurs.liste" }, admin: true },
        { libelle: "Rôles & permissions", to: { name: "droits.roles" }, admin: true },
        { libelle: "Affectations", to: { name: "droits.affectations" }, permission: "droits.consulter" },
      ]),
      lien(
        {
          libelle: "Journal d'activité",
          to: { name: "journal_activite.page" },
          permission: "journal_activite.consulter",
        },
        "journal-activite",
      ),
      groupe("parametres", "Paramètres", "parametres", [
        { libelle: "Mon profil", to: { name: "utilisateurs.mon-profil" } },
        {
          libelle: "Préférences de notification",
          to: { name: "notifications.preferences" },
          permission: "notification.consulter",
        },
      ]),
    ],
  },
]);

function visible(e: Entree): boolean {
  if (e.admin && !estAdministrateurPlateforme.value) return false;
  if (e.permission && !aPermission(e.permission)) return false;
  return true;
}

const sectionsVisibles = computed(() =>
  sections.value
    .map((s) => {
      const elements = s.elements
        .map((el): ElementMenu | null => {
          if (el.type === "lien") return el.lien && visible(el.lien) ? el : null;
          const enfants = (el.groupe?.enfants ?? []).filter(visible);
          return enfants.length > 0 && el.groupe ? { type: "groupe", groupe: { ...el.groupe, enfants } } : null;
        })
        .filter((el): el is ElementMenu => el !== null);
      return { ...s, elements };
    })
    .filter((s) => s.elements.length > 0),
);

function estActif(e: Entree): boolean {
  const nom = typeof route.name === "string" ? route.name : "";
  const memeRoute = nom === e.to.name || (e.actifPour ?? []).some((p) => nom === p || nom.startsWith(p + "."));
  if (!memeRoute) return false;
  return (e.cles ?? []).every((cle) => {
    const attendue = e.to.query?.[cle] ?? e.defauts?.[cle] ?? "";
    const courante = route.query[cle];
    const valeur = typeof courante === "string" ? courante : (e.defauts?.[cle] ?? "");
    return valeur === attendue;
  });
}

// Un groupe est ouvert si l'utilisateur l'a déplié, ou s'il contient la
// page courante (sauf s'il l'a explicitement replié).
const ouverture = ref<Record<string, boolean>>({});
function groupeContientActif(g: Groupe): boolean {
  return g.enfants.some(estActif);
}
function groupeOuvert(g: Groupe): boolean {
  return ouverture.value[g.id] ?? groupeContientActif(g);
}
function basculer(g: Groupe): void {
  ouverture.value = { ...ouverture.value, [g.id]: !groupeOuvert(g) };
}
</script>

<template>
  <nav class="flex-1 space-y-5 overflow-y-auto px-3 py-4" aria-label="Navigation principale">
    <section v-for="section in sectionsVisibles" :key="section.titre">
      <p class="mb-1 px-3 text-[11px] font-semibold uppercase tracking-wider text-[var(--color-sidebar-title)]">
        {{ section.titre }}
      </p>

      <ul class="space-y-0.5">
        <li v-for="(el, i) in section.elements" :key="el.lien?.libelle ?? el.groupe?.id ?? i">
          <!-- Entrée simple -->
          <router-link
            v-if="el.type === 'lien' && el.lien"
            :to="el.lien.to"
            class="flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors"
            :class="
              estActif(el.lien)
                ? 'bg-[var(--color-sidebar-active)] font-medium text-[var(--color-sidebar-text)]'
                : 'text-[var(--color-sidebar-text-muted)] hover:bg-[var(--color-sidebar-hover)] hover:text-[var(--color-sidebar-text)]'
            "
            @click="emit('navigation')"
          >
            <IconeNav :nom="el.lien.icone" />
            <span class="truncate">{{ el.lien.libelle }}</span>
          </router-link>

          <!-- Groupe repliable -->
          <template v-else-if="el.type === 'groupe' && el.groupe">
            <button
              type="button"
              class="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm transition-colors hover:bg-[var(--color-sidebar-hover)] hover:text-[var(--color-sidebar-text)]"
              :class="
                groupeContientActif(el.groupe)
                  ? 'text-[var(--color-sidebar-text)]'
                  : 'text-[var(--color-sidebar-text-muted)]'
              "
              :aria-expanded="groupeOuvert(el.groupe)"
              @click="basculer(el.groupe)"
            >
              <IconeNav :nom="el.groupe.icone" />
              <span class="flex-1 truncate">{{ el.groupe.libelle }}</span>
              <svg
                viewBox="0 0 20 20"
                fill="none"
                stroke="currentColor"
                stroke-width="1.8"
                stroke-linecap="round"
                stroke-linejoin="round"
                class="h-3.5 w-3.5 shrink-0 transition-transform"
                :class="groupeOuvert(el.groupe) ? 'rotate-180' : ''"
              >
                <path d="m5 8 5 5 5-5" />
              </svg>
            </button>

            <ul v-if="groupeOuvert(el.groupe)" class="mt-0.5 space-y-0.5 pl-4">
              <li v-for="enfant in el.groupe.enfants" :key="enfant.libelle">
                <router-link
                  :to="enfant.to"
                  class="flex items-center gap-3 rounded-lg px-3 py-1.5 text-sm transition-colors"
                  :class="
                    estActif(enfant)
                      ? 'bg-[var(--color-sidebar-active)] font-medium text-[var(--color-sidebar-text)]'
                      : 'text-[var(--color-sidebar-text-muted)] hover:bg-[var(--color-sidebar-hover)] hover:text-[var(--color-sidebar-text)]'
                  "
                  @click="emit('navigation')"
                >
                  <span class="h-1.5 w-1.5 shrink-0 rounded-full bg-current opacity-70" />
                  <span class="truncate">{{ enfant.libelle }}</span>
                </router-link>
              </li>
            </ul>
          </template>
        </li>
      </ul>
    </section>
  </nav>
</template>