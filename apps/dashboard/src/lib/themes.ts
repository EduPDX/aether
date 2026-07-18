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
  /** Paleta de séries dos gráficos — cada tema tem a sua identidade. */
  chart: readonly string[];
}

export const THEMES = {
  aether: {
    label: "Aether", dark: true,
    tokens: { bg: "#0b1220", surface: "#131f36", surface2: "#1b2b4a", surface3: "#24395f",
      border: "#2b4470", text: "#eaf2ff", muted: "#94accd",
      accent: "#22e39b", accentDim: "#12c684", danger: "#ff5c7a", warn: "#ffc63d", info: "#4cc9f0" },
    chart: ["#22e39b", "#4cc9f0", "#ffc63d", "#ff5c7a", "#b78bff"],
  },
  roxo: {
    label: "Roxo", dark: true,
    tokens: { bg: "#1a143d", surface: "#251c58", surface2: "#2d245e", surface3: "#3b2f7a",
      border: "#463a8f", text: "#e0d7ff", muted: "#a89ad4",
      accent: "#a78bfa", accentDim: "#8b5cf6", danger: "#fb7185", warn: "#fbbf24", info: "#7dd3fc" },
    chart: ["#a78bfa", "#f472b6", "#38bdf8", "#fbbf24", "#4ade80"],
  },
  ametista: {
    label: "Ametista", dark: true,
    tokens: { bg: "#1e0b36", surface: "#2b1150", surface2: "#37175f", surface3: "#4a1f7d",
      border: "#5b2896", text: "#f5f3ff", muted: "#c4a6e8",
      accent: "#d8b4fe", accentDim: "#c084fc", danger: "#ff6b8b", warn: "#fcd34d", info: "#a5b4fc" },
    chart: ["#d8b4fe", "#f0abfc", "#818cf8", "#fcd34d", "#5eead4"],
  },
  synthwave: {
    label: "Synthwave", dark: true,
    tokens: { bg: "#190b2e", surface: "#251140", surface2: "#331858", surface3: "#452076",
      border: "#57298f", text: "#ffe9fb", muted: "#c39ad9",
      accent: "#ff5fd2", accentDim: "#e839b6", danger: "#ff4365", warn: "#ffd166", info: "#5bd1ff" },
    chart: ["#ff5fd2", "#5bd1ff", "#ffd166", "#a06bff", "#42e6a4"],
  },
  cyber: {
    label: "Cyber", dark: true,
    tokens: { bg: "#04141c", surface: "#07222e", surface2: "#0a3040", surface3: "#0f4256",
      border: "#12556e", text: "#d7fbff", muted: "#71b4c7",
      accent: "#00f0ff", accentDim: "#00c2cc", danger: "#ff4d6d", warn: "#ffd60a", info: "#7b61ff" },
    chart: ["#00f0ff", "#ffd60a", "#ff4d6d", "#7b61ff", "#3ddc84"],
  },
  oceano: {
    label: "Oceano", dark: true,
    tokens: { bg: "#06212b", surface: "#0a3040", surface2: "#0e3f52", surface3: "#155268",
      border: "#1a6580", text: "#dff8f5", muted: "#7fb9c4",
      accent: "#2dd4bf", accentDim: "#14b8a6", danger: "#fb7185", warn: "#fbbf24", info: "#38bdf8" },
    chart: ["#2dd4bf", "#38bdf8", "#fbbf24", "#fb7185", "#a78bfa"],
  },
  dracula: {
    label: "Dracula", dark: true,
    tokens: { bg: "#282a36", surface: "#343746", surface2: "#3d4055", surface3: "#4a4d68",
      border: "#5b5f80", text: "#f8f8f2", muted: "#b9c0dc",
      accent: "#bd93f9", accentDim: "#9d6ff5", danger: "#ff5555", warn: "#f1fa8c", info: "#8be9fd" },
    chart: ["#bd93f9", "#50fa7b", "#ffb86c", "#ff79c6", "#8be9fd"],
  },
  catppuccin: {
    label: "Catppuccin", dark: true,
    tokens: { bg: "#1e1e2e", surface: "#28283d", surface2: "#313244", surface3: "#45475a",
      border: "#585b70", text: "#cdd6f4", muted: "#a6adc8",
      accent: "#a6e3a1", accentDim: "#88d98a", danger: "#f38ba8", warn: "#f9e2af", info: "#89b4fa" },
    chart: ["#a6e3a1", "#89b4fa", "#f9e2af", "#f38ba8", "#cba6f7"],
  },
  hacker: {
    label: "Hacker", dark: true,
    tokens: { bg: "#020a02", surface: "#061606", surface2: "#0a220a", surface3: "#103010",
      border: "#164016", text: "#b8ffb8", muted: "#5fa85f",
      accent: "#39ff14", accentDim: "#22d40a", danger: "#ff3131", warn: "#faff00", info: "#00e5ff" },
    chart: ["#39ff14", "#00e5ff", "#faff00", "#ff3131", "#c77dff"],
  },
  fogo: {
    label: "Fogo", dark: true,
    tokens: { bg: "#1a0d08", surface: "#2a150c", surface2: "#3a1d10", surface3: "#4e2716",
      border: "#63321c", text: "#ffe9dd", muted: "#c99b82",
      accent: "#ff7a29", accentDim: "#e85d04", danger: "#ff3b30", warn: "#ffc300", info: "#4cc9f0" },
    chart: ["#ff7a29", "#ffc300", "#ff3b30", "#4cc9f0", "#8ac926"],
  },
  nord: {
    label: "Nord", dark: true,
    tokens: { bg: "#2e3440", surface: "#3b4252", surface2: "#434c5e", surface3: "#4c566a",
      border: "#59647a", text: "#eceff4", muted: "#a9b4c6",
      accent: "#88c0d0", accentDim: "#6da8ba", danger: "#bf616a", warn: "#ebcb8b", info: "#81a1c1" },
    chart: ["#88c0d0", "#a3be8c", "#ebcb8b", "#bf616a", "#b48ead"],
  },
  tokyo: {
    label: "Tokyo Night", dark: true,
    tokens: { bg: "#1a1b26", surface: "#24283b", surface2: "#2f334d", surface3: "#3b4261",
      border: "#4a5178", text: "#c0caf5", muted: "#8f96bd",
      accent: "#7aa2f7", accentDim: "#5d86e0", danger: "#f7768e", warn: "#e0af68", info: "#7dcfff" },
    chart: ["#7aa2f7", "#9ece6a", "#e0af68", "#f7768e", "#bb9af7"],
  },
  gruvbox: {
    label: "Gruvbox", dark: true,
    tokens: { bg: "#1d2021", surface: "#282828", surface2: "#32302f", surface3: "#3c3836",
      border: "#504945", text: "#fbf1c7", muted: "#bdae93",
      accent: "#b8bb26", accentDim: "#98971a", danger: "#fb4934", warn: "#fabd2f", info: "#83a598" },
    chart: ["#b8bb26", "#83a598", "#fabd2f", "#fb4934", "#d3869b"],
  },
  matcha: {
    label: "Matcha", dark: true,
    tokens: { bg: "#0d1a10", surface: "#132618", surface2: "#1a3421", surface3: "#23452c",
      border: "#2d5738", text: "#e3f5e7", muted: "#8fb99a",
      accent: "#7bd88f", accentDim: "#57bd6e", danger: "#ff6b6b", warn: "#ffd166", info: "#5bc0eb" },
    chart: ["#7bd88f", "#5bc0eb", "#ffd166", "#ff6b6b", "#c792ea"],
  },
  vinho: {
    label: "Vinho", dark: true,
    tokens: { bg: "#1c0a10", surface: "#2b1019", surface2: "#3a1622", surface3: "#4d1d2d",
      border: "#63263a", text: "#ffe4ec", muted: "#c88ea3",
      accent: "#ff6b9d", accentDim: "#e04578", danger: "#ff4d4d", warn: "#ffb703", info: "#7fb3ff" },
    chart: ["#ff6b9d", "#ffb703", "#7fb3ff", "#ff4d4d", "#9d8df1"],
  },
  grafite: {
    label: "Grafite", dark: true,
    tokens: { bg: "#0f0f11", surface: "#18181b", surface2: "#212124", surface3: "#2c2c31",
      border: "#3a3a41", text: "#f4f4f5", muted: "#a1a1aa",
      accent: "#e4e4e7", accentDim: "#c4c4c8", danger: "#f87171", warn: "#fbbf24", info: "#60a5fa" },
    chart: ["#e4e4e7", "#60a5fa", "#fbbf24", "#f87171", "#a78bfa"],
  },
  sakura: {
    label: "Sakura (claro)", dark: false,
    tokens: { bg: "#fff5f7", surface: "#ffffff", surface2: "#ffeaf0", surface3: "#ffd6e2",
      border: "#f7c2d4", text: "#4a1128", muted: "#96566f",
      accent: "#db2777", accentDim: "#be185d", danger: "#dc2626", warn: "#b45309", info: "#2563eb" },
    chart: ["#db2777", "#2563eb", "#b45309", "#059669", "#7c3aed"],
  },
  papel: {
    label: "Papel (claro)", dark: false,
    tokens: { bg: "#faf7f0", surface: "#ffffff", surface2: "#f3ede1", surface3: "#e8dfcc",
      border: "#d9ccb2", text: "#2d2a24", muted: "#6f6754",
      accent: "#a16207", accentDim: "#854d0e", danger: "#b91c1c", warn: "#c2410c", info: "#1d4ed8" },
    chart: ["#a16207", "#1d4ed8", "#b91c1c", "#15803d", "#7e22ce"],
  },
  lavanda: {
    label: "Lavanda (claro)", dark: false,
    tokens: { bg: "#f6f4ff", surface: "#ffffff", surface2: "#efeaff", surface3: "#e0d7fb",
      border: "#cfc2f5", text: "#2e1065", muted: "#6d5ba3",
      accent: "#7c3aed", accentDim: "#6d28d9", danger: "#dc2626", warn: "#d97706", info: "#2563eb" },
    chart: ["#7c3aed", "#2563eb", "#d97706", "#dc2626", "#059669"],
  },
  geada: {
    label: "Geada (claro)", dark: false,
    tokens: { bg: "#f2f8fb", surface: "#ffffff", surface2: "#e8f2f8", surface3: "#d5e7f0",
      border: "#bcd8e6", text: "#0d2b3a", muted: "#4a7186",
      accent: "#0891b2", accentDim: "#0e7490", danger: "#dc2626", warn: "#b45309", info: "#2563eb" },
    chart: ["#0891b2", "#2563eb", "#b45309", "#dc2626", "#7c3aed"],
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

/** Paleta de séries do tema atual (ordem fixa: nunca reciclar). */
export function chartPalette(name: ThemeName = currentTheme()): readonly string[] {
  return (THEMES[name] ?? THEMES.aether).chart;
}
