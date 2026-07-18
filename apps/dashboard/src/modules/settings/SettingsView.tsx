import { BarChart3, Check, Palette, Shapes, UserRound } from "lucide-react";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Donut, TimeSeries } from "../../components/BarChart";
import type { SeriesKind } from "../../components/BarChart";
import { Panel, Select } from "../../components/ui";
import type { IconPack } from "../../lib/icons";
import { ICON_PACKS, currentIconPack, setIconPack } from "../../lib/icons";
import type { ThemeName } from "../../lib/themes";
import { THEMES, THEME_NAMES, applyTheme, currentTheme } from "../../lib/themes";
import { ProfileContent } from "../admin/AdminViews";
import { FileIcon } from "../files/FileIcon";

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

/** Arquivos de exemplo para a prévia dos pacotes de ícone. */
const AMOSTRA_ARQUIVOS: { name: string; isDir: boolean }[] = [
  { name: "config", isDir: true },
  { name: "sodium.jar", isDir: false },
  { name: "server.properties", isDir: false },
  { name: "latest.log", isDir: false },
  { name: "icon.png", isDir: false },
];

type Secao = "tema" | "icones" | "graficos" | "perfil";

const SECOES: { id: Secao; label: string; icon: ReactNode; grupo: string }[] = [
  { id: "tema", label: "Tema", icon: <Palette size={15} />, grupo: "Aparência" },
  { id: "icones", label: "Ícones", icon: <Shapes size={15} />, grupo: "Aparência" },
  { id: "graficos", label: "Gráficos", icon: <BarChart3 size={15} />, grupo: "Aparência" },
  { id: "perfil", label: "Meu perfil", icon: <UserRound size={15} />, grupo: "Conta" },
];

export function SettingsView({ initialSection = "tema" }: { initialSection?: Secao }) {
  const [secao, setSecao] = useState<Secao>(initialSection);
  const [theme, setTheme] = useState<ThemeName>(currentTheme);
  const [chartKind, setChartKind] = useState<SeriesKind>(preferredChartKind);
  const [pack, setPack] = useState<IconPack>(currentIconPack);

  useEffect(() => applyTheme(theme), [theme]);
  useEffect(() => {
    localStorage.setItem(CHART_KEY, chartKind);
    window.dispatchEvent(new Event("aether:chartkind"));
  }, [chartKind]);
  useEffect(() => setIconPack(pack), [pack]);

  const preview = THEMES[theme];
  const grupos = [...new Set(SECOES.map((s) => s.grupo))];

  return (
    <div className="flex h-full min-h-0">
      {/* Sub-navegação: novas opções entram aqui sem empilhar painéis soltos. */}
      <nav className="w-52 shrink-0 overflow-y-auto border-r border-border p-3">
        {grupos.map((grupo) => (
          <div key={grupo} className="mb-3">
            <div className="px-2 pb-1 text-[10px] font-semibold tracking-wider text-muted uppercase">
              {grupo}
            </div>
            {SECOES.filter((s) => s.grupo === grupo).map((s) => (
              <button
                key={s.id}
                onClick={() => setSecao(s.id)}
                className={`flex w-full cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors ${
                  secao === s.id
                    ? "bg-surface-3 text-text"
                    : "text-muted hover:bg-surface-2 hover:text-text"
                }`}
              >
                {s.icon}
                {s.label}
              </button>
            ))}
          </div>
        ))}
      </nav>

      <div className="min-w-0 flex-1 overflow-y-auto p-4">
        <div className="flex w-full max-w-4xl flex-col gap-4">
          {secao === "tema" && (
            <Panel
              title="Tema"
              icon={<Palette size={15} />}
              hint="Muda a interface inteira e a paleta dos gráficos. Fica salvo neste navegador."
            >
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
                      <div
                        className="mt-1 h-1 w-full rounded"
                        style={{ background: t.tokens.accent }}
                      />
                    </button>
                  );
                })}
              </div>
            </Panel>
          )}

          {secao === "icones" && (
            <Panel
              title="Ícones de arquivos e pastas"
              icon={<Shapes size={15} />}
              hint="Estilo dos ícones no gerenciador de arquivos."
            >
              <div className="grid gap-2 sm:grid-cols-3">
                {ICON_PACKS.map((p) => {
                  const active = p.id === pack;
                  return (
                    <button
                      key={p.id}
                      onClick={() => setPack(p.id)}
                      className={`cursor-pointer rounded-lg border p-3 text-left transition-all ${
                        active
                          ? "border-accent ring-1 ring-accent"
                          : "border-border hover:border-muted"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold">{p.label}</span>
                        {active && <Check size={13} className="text-accent" />}
                      </div>
                      {/* Prévia com o pacote forçado, independente do escolhido. */}
                      <div className="mt-2.5 flex items-center gap-2.5">
                        {AMOSTRA_ARQUIVOS.map((f) => (
                          <FileIcon
                            key={f.name}
                            name={f.name}
                            isDir={f.isDir}
                            size={22}
                            pack={p.id}
                          />
                        ))}
                      </div>
                      <p className="mt-2.5 text-[11px] text-muted">{p.hint}</p>
                    </button>
                  );
                })}
              </div>
            </Panel>
          )}

          {secao === "graficos" && (
            <Panel
              title="Gráficos"
              icon={<BarChart3 size={15} />}
              hint="Tipo padrão das séries temporais na Visão geral."
              aside={
                <Select
                  className="py-1 text-xs"
                  value={chartKind}
                  onChange={(e) => setChartKind(e.target.value as SeriesKind)}
                >
                  <option value="area">Área</option>
                  <option value="linha">Linha</option>
                  <option value="barras">Barras</option>
                </Select>
              }
            >
              <div className="grid gap-4 sm:grid-cols-2">
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
            </Panel>
          )}

          {secao === "perfil" && <ProfileContent />}
        </div>
      </div>
    </div>
  );
}
