import { Check, Palette } from "lucide-react";
import { useEffect, useState } from "react";
import { Donut, TimeSeries } from "../../components/BarChart";
import type { SeriesKind } from "../../components/BarChart";
import { Select } from "../../components/ui";
import type { ThemeName } from "../../lib/themes";
import { THEMES, THEME_NAMES, applyTheme, currentTheme } from "../../lib/themes";

const CHART_KEY = "aether.chartKind";

export function preferredChartKind(): SeriesKind {
  const v = localStorage.getItem(CHART_KEY) as SeriesKind | null;
  return v === "linha" || v === "barras" || v === "area" ? v : "area";
}

/** Série de exemplo para a prévia reagir ao tipo escolhido. */
const SERIE = [12, 18, 15, 27, 34, 30, 45, 38, 52, 47, 61, 55, 48, 40, 33];

const AMOSTRA = [
  { label: "Forge", value: 279 },
  { label: "Fabric", value: 38 },
  { label: "NeoForge", value: 12 },
];

export function SettingsView() {
  const [theme, setTheme] = useState<ThemeName>(currentTheme);
  const [chartKind, setChartKind] = useState<SeriesKind>(preferredChartKind);

  useEffect(() => applyTheme(theme), [theme]);
  useEffect(() => {
    localStorage.setItem(CHART_KEY, chartKind);
    window.dispatchEvent(new Event("aether:chartkind"));
  }, [chartKind]);

  const preview = THEMES[theme];

  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-4">
        <section className="rounded-xl border border-border bg-surface p-4">
          <div className="mb-1 flex items-center gap-2">
            <Palette size={15} />
            <h2 className="text-sm font-semibold">Tema</h2>
          </div>
          <p className="mb-3 text-[11px] text-muted">
            Muda a interface inteira e a paleta dos gráficos. Fica salvo neste navegador.
          </p>

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
            {THEME_NAMES.map((name) => {
              const t = THEMES[name];
              const active = name === theme;
              return (
                <button
                  key={name}
                  onClick={() => setTheme(name)}
                  className={`cursor-pointer rounded-lg border p-2 text-left transition-all ${
                    active ? "border-accent ring-1 ring-accent" : "border-border hover:border-muted"
                  }`}
                  style={{ background: t.tokens.surface }}
                >
                  <div className="flex items-center gap-1.5">
                    <span className="flex gap-1">
                      {t.chart.slice(0, 4).map((c) => (
                        <span
                          key={c}
                          className="inline-block h-3 w-3 rounded-full"
                          style={{ background: c }}
                        />
                      ))}
                    </span>
                    {active && <Check size={13} style={{ color: t.tokens.accent }} />}
                  </div>
                  <div className="mt-1.5 text-xs font-medium" style={{ color: t.tokens.text }}>
                    {t.label}
                  </div>
                  <div className="mt-1 h-1 w-full rounded" style={{ background: t.tokens.accent }} />
                </button>
              );
            })}
          </div>
        </section>

        <section className="rounded-xl border border-border bg-surface p-4">
          <div className="mb-1 flex flex-wrap items-center gap-3">
            <h2 className="text-sm font-semibold">Gráficos</h2>
            <Select
              className="py-1 text-xs"
              value={chartKind}
              onChange={(e) => setChartKind(e.target.value as SeriesKind)}
            >
              <option value="area">Área</option>
              <option value="linha">Linha</option>
              <option value="barras">Barras</option>
            </Select>
            <span className="text-[11px] text-muted">
              tipo padrão das séries temporais na Visão geral
            </span>
          </div>

          <div className="mt-3 grid gap-4 sm:grid-cols-2">
            <div>
              <div className="mb-2 text-[11px] text-muted">Prévia — rosca</div>
              <Donut data={AMOSTRA.map((d, i) => ({ ...d, color: preview.chart[i] }))} />
            </div>
            <div>
              <div className="mb-2 text-[11px] text-muted">
                Prévia — série temporal ({chartKind})
              </div>
              {/* Reage ao seletor: era estática e não mudava com a escolha. */}
              <TimeSeries
                points={SERIE}
                kind={chartKind}
                color={preview.chart[0]}
                format={(n) => `${n.toFixed(0)}%`}
                height={110}
              />
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
