/** Preferências de visualização dos gráficos. */

import { useSyncExternalStore } from "react";
import type { CategoryKind, SeriesKind } from "../components/BarChart";

const SERIES_KEY = "aether.chartKind";
const CATEGORY_KEY = "aether.categoryKind";
export const CHART_EVENT = "aether:chartkind";

export const SERIES_OPTIONS: { id: SeriesKind; label: string; hint: string }[] = [
  { id: "area", label: "Área", hint: "Linha com preenchimento — destaca o volume" },
  { id: "linha", label: "Linha", hint: "Traço limpo, bom para comparar variação" },
  { id: "suave", label: "Suave", hint: "Curva arredondada, menos ruído visual" },
  { id: "degrau", label: "Degrau", hint: "Cada leitura vale até a próxima amostra" },
];

export const CATEGORY_OPTIONS: { id: CategoryKind; label: string; hint: string }[] = [
  { id: "rosca", label: "Rosca", hint: "Proporção com o total no centro" },
  { id: "pizza", label: "Pizza", hint: "Disco cheio, ênfase na fatia maior" },
  { id: "barras", label: "Barras", hint: "Melhor para comparar valores e ranquear" },
];

const SERIES_IDS = new Set<string>(SERIES_OPTIONS.map((o) => o.id));
const CATEGORY_IDS = new Set<string>(CATEGORY_OPTIONS.map((o) => o.id));

export function preferredSeriesKind(): SeriesKind {
  const v = localStorage.getItem(SERIES_KEY);
  // "barras" era uma opção de série temporal e deixou de ser: quem tinha essa
  // preferência salva cai no padrão em vez de ficar com um gráfico inválido.
  return v && SERIES_IDS.has(v) ? (v as SeriesKind) : "area";
}

export function setSeriesKind(kind: SeriesKind): void {
  localStorage.setItem(SERIES_KEY, kind);
  window.dispatchEvent(new Event(CHART_EVENT));
}

export function preferredCategoryKind(): CategoryKind {
  const v = localStorage.getItem(CATEGORY_KEY);
  return v && CATEGORY_IDS.has(v) ? (v as CategoryKind) : "rosca";
}

export function setCategoryKind(kind: CategoryKind): void {
  localStorage.setItem(CATEGORY_KEY, kind);
  window.dispatchEvent(new Event(CHART_EVENT));
}

function subscribe(fn: () => void): () => void {
  window.addEventListener(CHART_EVENT, fn);
  return () => window.removeEventListener(CHART_EVENT, fn);
}

/** Reagem à troca feita nas configurações sem precisar remontar a tela. */
export function useSeriesKind(): SeriesKind {
  return useSyncExternalStore(subscribe, preferredSeriesKind);
}

export function useCategoryKind(): CategoryKind {
  return useSyncExternalStore(subscribe, preferredCategoryKind);
}
