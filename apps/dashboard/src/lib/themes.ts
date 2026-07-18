/** Temas nomeados — conceito portado do finance-frontend: um conjunto
 *  consistente de tokens por tema, aplicado em CSS variables e persistido. */

export interface ThemeTokens {
  bg: string;
  surface: string;
  surface2: string;
  surface3: string;
  border: string;
  text: string;
  muted: string;
  accent: string;
  accentDim: string;
  danger: string;
  warn: string;
  info: string;
}

export interface Theme {
  label: string;
  dark: boolean;
  tokens: ThemeTokens;
}

export const THEMES = {
  aether: {
    label: "Aether",
    dark: true,
    tokens: {
      bg: "#0e1013", surface: "#15181e", surface2: "#1c2028", surface3: "#232936",
      border: "#272d38", text: "#e6e9ef", muted: "#8b93a3",
      accent: "#4ade80", accentDim: "#22c55e",
      danger: "#f87171", warn: "#fbbf24", info: "#60a5fa",
    },
  },
  nord: {
    label: "Nord",
    dark: true,
    tokens: {
      bg: "#2e3440", surface: "#3b4252", surface2: "#434c5e", surface3: "#4c566a",
      border: "#4c566a", text: "#eceff4", muted: "#a9b1c2",
      accent: "#88c0d0", accentDim: "#5e81ac",
      danger: "#bf616a", warn: "#ebcb8b", info: "#81a1c1",
    },
  },
  dracula: {
    label: "Dracula",
    dark: true,
    tokens: {
      bg: "#282a36", surface: "#343746", surface2: "#3d4055", surface3: "#44475a",
      border: "#4d5066", text: "#f8f8f2", muted: "#a5abc0",
      accent: "#bd93f9", accentDim: "#9a6ff0",
      danger: "#ff5555", warn: "#f1fa8c", info: "#8be9fd",
    },
  },
  catppuccin: {
    label: "Catppuccin",
    dark: true,
    tokens: {
      bg: "#1e1e2e", surface: "#282839", surface2: "#313244", surface3: "#45475a",
      border: "#45475a", text: "#cdd6f4", muted: "#a6adc8",
      accent: "#a6e3a1", accentDim: "#84cc8a",
      danger: "#f38ba8", warn: "#f9e2af", info: "#89b4fa",
    },
  },
  midnight: {
    label: "Midnight",
    dark: true,
    tokens: {
      bg: "#0b1120", surface: "#111a2e", surface2: "#16233c", surface3: "#1e2f4d",
      border: "#22314d", text: "#e2e8f0", muted: "#8ea0bd",
      accent: "#38bdf8", accentDim: "#0ea5e9",
      danger: "#fb7185", warn: "#fcd34d", info: "#818cf8",
    },
  },
  synthwave: {
    label: "Synthwave",
    dark: true,
    tokens: {
      bg: "#1a1030", surface: "#241640", surface2: "#2e1d52", surface3: "#3b2668",
      border: "#402a70", text: "#f5e6ff", muted: "#b39ccc",
      accent: "#ff6ec7", accentDim: "#e94db0",
      danger: "#ff4d6d", warn: "#ffd166", info: "#61dafb",
    },
  },
  hacker: {
    label: "Hacker",
    dark: true,
    tokens: {
      bg: "#050a05", surface: "#0b140b", surface2: "#111d11", surface3: "#182a18",
      border: "#1d331d", text: "#c6f6c6", muted: "#6f9c6f",
      accent: "#39ff14", accentDim: "#2bcc10",
      danger: "#ff5f56", warn: "#f5d90a", info: "#5ad1ff",
    },
  },
  oceano: {
    label: "Oceano",
    dark: true,
    tokens: {
      bg: "#0a1a24", surface: "#0f2632", surface2: "#143240", surface3: "#1b4152",
      border: "#1e4757", text: "#e0f2f1", muted: "#8fb3bd",
      accent: "#2dd4bf", accentDim: "#14b8a6",
      danger: "#f87171", warn: "#fbbf24", info: "#38bdf8",
    },
  },
  coffee: {
    label: "Coffee",
    dark: true,
    tokens: {
      bg: "#1c1512", surface: "#261d18", surface2: "#33261f", surface3: "#42322a",
      border: "#4a382e", text: "#f0e6dd", muted: "#b09a89",
      accent: "#d2a679", accentDim: "#b8875a",
      danger: "#e07a5f", warn: "#e9c46a", info: "#8ab6d6",
    },
  },
  geada: {
    label: "Geada (claro)",
    dark: false,
    tokens: {
      bg: "#f4f7fb", surface: "#ffffff", surface2: "#eef2f8", surface3: "#dfe6f0",
      border: "#d3dbe6", text: "#1b2534", muted: "#5c6b80",
      accent: "#0f766e", accentDim: "#0d9488",
      danger: "#b91c1c", warn: "#a16207", info: "#1d4ed8",
    },
  },
  lavanda: {
    label: "Lavanda (claro)",
    dark: false,
    tokens: {
      bg: "#f8f7ff", surface: "#ffffff", surface2: "#f1eeff", surface3: "#e4defb",
      border: "#d8d0f5", text: "#2e1065", muted: "#6b5b95",
      accent: "#6d28d9", accentDim: "#7c3aed",
      danger: "#be123c", warn: "#a16207", info: "#1d4ed8",
    },
  },
} as const satisfies Record<string, Theme>;

export type ThemeName = keyof typeof THEMES;
export const THEME_NAMES = Object.keys(THEMES) as ThemeName[];
const STORAGE_KEY = "aether.theme";

export function currentTheme(): ThemeName {
  const saved = localStorage.getItem(STORAGE_KEY) as ThemeName | null;
  return saved && saved in THEMES ? saved : "aether";
}

/** Escreve os tokens do tema nas CSS variables que o Tailwind consome. */
export function applyTheme(name: ThemeName): void {
  const theme = THEMES[name] ?? THEMES.aether;
  const t = theme.tokens;
  const root = document.documentElement;
  const map: Record<string, string> = {
    "--color-bg": t.bg,
    "--color-surface": t.surface,
    "--color-surface-2": t.surface2,
    "--color-surface-3": t.surface3,
    "--color-border": t.border,
    "--color-text": t.text,
    "--color-muted": t.muted,
    "--color-accent": t.accent,
    "--color-accent-dim": t.accentDim,
    "--color-danger": t.danger,
    "--color-warn": t.warn,
    "--color-info": t.info,
  };
  for (const [key, value] of Object.entries(map)) root.style.setProperty(key, value);
  root.style.colorScheme = theme.dark ? "dark" : "light";
  localStorage.setItem(STORAGE_KEY, name);
}

/** Paleta categórica dos gráficos — validada (CVD ΔE 14.5, banda de
 *  luminosidade e contraste OK). Ordem fixa: nunca reciclar/rotacionar. */
export const CHART_CATEGORICAL = ["#d97706", "#3b82f6", "#059669", "#ec4899"] as const;
