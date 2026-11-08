import type { Config } from "tailwindcss";

/**
 * Les couleurs référencent des variables CSS (voir src/styles/tokens.css)
 * plutôt que des valeurs figées : remplacer tokens.css suffit à adapter
 * toute l'application à une charte graphique existante, sans toucher à ce
 * fichier ni aux composants.
 */
export default {
  content: ["./index.html", "./src/**/*.{vue,ts}"],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "var(--color-primary)",
          hover: "var(--color-primary-hover)",
          foreground: "var(--color-primary-foreground)",
        },
        surface: {
          DEFAULT: "var(--color-surface)",
          muted: "var(--color-surface-muted)",
        },
        border: "var(--color-border)",
        text: {
          DEFAULT: "var(--color-text)",
          muted: "var(--color-text-muted)",
        },
        success: { DEFAULT: "var(--color-success)", bg: "var(--color-success-bg)" },
        warning: { DEFAULT: "var(--color-warning)", bg: "var(--color-warning-bg)" },
        danger: { DEFAULT: "var(--color-danger)", bg: "var(--color-danger-bg)" },
        info: { DEFAULT: "var(--color-info)", bg: "var(--color-info-bg)" },
      },
    },
  },
  plugins: [],
} satisfies Config;
