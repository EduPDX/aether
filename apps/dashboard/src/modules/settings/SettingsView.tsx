import { Activity, BarChart3, Check, Palette, Shapes, UserRound } from "lucide-react";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { CategoryChart, TimeSeries } from "../../components/BarChart";
import type { CategoryKind, SeriesKind } from "../../components/BarChart";
import { Panel } from "../../components/ui";
import {
  CATEGORY_OPTIONS,
  SERIES_OPTIONS,
  preferredCategoryKind,
  preferredSeriesKind,
  setCategoryKind,
  setSeriesKind,
} from "../../lib/charts";
import type { IconPack } from "../../lib/icons";
import { ICON_PACKS, currentIconPack, setIconPack } from "../../lib/icons";
import type { ThemeName } from "../../lib/themes";
import { THEMES, THEME_NAMES, applyTheme, currentTheme } from "../../lib/themes";
import { ProfileContent } from "../admin/AdminViews";
import { FileIcon } from "../files/FileIcon";
import { IconPreview, ThemePreview } from "./Previews";

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

/** Cartão selecionável com prévia viva do gráfico dentro. */
function EscolhaGrafico({
  label,
  hint,
  ativo,
  onSelect,
  onHover,
  children,
}: {
  label: string;
  hint: string;
  ativo: boolean;
  onSelect: () => void;
  onHover: () => void;
  children: ReactNode;
}) {
  return (
    <button
      onClick={onSelect}
      onMouseEnter={onHover}
      onFocus={onHover}
      className={`cursor-pointer rounded-lg border p-3 text-left transition-all ${
        ativo ? "border-accent ring-1 ring-accent" : "border-border hover:border-muted"
      }`}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold">{label}</span>
        {ativo && <Check size={13} className="text-accent" />}
      </div>
      <div className="mt-2">{children}</div>
      <p className="mt-2 text-[11px] text-muted">{hint}</p>
    </button>
  );
}

export function SettingsView({ initialSection = "tema" }: { initialSection?: Secao }) {
  const [secao, setSecao] = useState<Secao>(initialSection);
  const [theme, setTheme] = useState<ThemeName>(currentTheme);
  const [serieKind, setSerie] = useState<SeriesKind>(preferredSeriesKind);
  const [catKind, setCat] = useState<CategoryKind>(preferredCategoryKind);
  const [pack, setPack] = useState<IconPack>(currentIconPack);
  // Hover apenas alimenta a prévia — não aplica nada até o clique.
  const [hoverTheme, setHoverTheme] = useState<ThemeName | null>(null);
  const [hoverPack, setHoverPack] = useState<IconPack | null>(null);
  const [hoverSerie, setHoverSerie] = useState<SeriesKind | null>(null);
  const [hoverCat, setHoverCat] = useState<CategoryKind | null>(null);

  useEffect(() => applyTheme(theme), [theme]);
  useEffect(() => setSeriesKind(serieKind), [serieKind]);
  useEffect(() => setCategoryKind(catKind), [catKind]);
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
        {/* O perfil tem listas de frases e respira melhor largo; as demais
            seções são grades de cartões e ficam estranhas muito esticadas. */}
        <div
          className={`flex w-full flex-col gap-4 ${
            secao === "perfil" ? "max-w-6xl" : "max-w-4xl"
          }`}
        >
          {secao === "tema" && (
            <>
              <Panel
                title="Prévia"
                hint={`${THEMES[hoverTheme ?? theme].label} — passe o mouse sobre um tema para espiar antes de aplicar.`}
              >
                <div className="max-w-md">
                  <ThemePreview theme={THEMES[hoverTheme ?? theme]} />
                </div>
              </Panel>

            <Panel
              title="Tema"
              icon={<Palette size={15} />}
              hint="Muda a interface inteira e a paleta dos gráficos. Fica salvo neste navegador."
            >
              <div
                className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4"
                onMouseLeave={() => setHoverTheme(null)}
              >
                {THEME_NAMES.map((name) => {
                  const t = THEMES[name];
                  const active = name === theme;
                  return (
                    <button
                      key={name}
                      onClick={() => setTheme(name)}
                      onMouseEnter={() => setHoverTheme(name)}
                      onFocus={() => setHoverTheme(name)}
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
            </>
          )}

          {secao === "icones" && (
            <>
              <Panel
                title="Prévia"
                hint={`${ICON_PACKS.find((p) => p.id === (hoverPack ?? pack))?.label} — como fica no gerenciador de arquivos.`}
              >
                <IconPreview pack={hoverPack ?? pack} />
              </Panel>

            <Panel
              title="Ícones de arquivos e pastas"
              icon={<Shapes size={15} />}
              hint="Estilo dos ícones no gerenciador de arquivos."
            >
              <div
                className="grid gap-2 sm:grid-cols-3"
                onMouseLeave={() => setHoverPack(null)}
              >
                {ICON_PACKS.map((p) => {
                  const active = p.id === pack;
                  return (
                    <button
                      key={p.id}
                      onClick={() => setPack(p.id)}
                      onMouseEnter={() => setHoverPack(p.id)}
                      onFocus={() => setHoverPack(p.id)}
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
            </>
          )}

          {secao === "graficos" && (
            <>
              <Panel
                title="Prévia — CPU e memória ao longo do tempo"
                hint={`${SERIES_OPTIONS.find((o) => o.id === (hoverSerie ?? serieKind))?.label} — é assim que a Visão geral desenha as métricas.`}
              >
                <TimeSeries
                  points={SERIE}
                  kind={hoverSerie ?? serieKind}
                  color={preview.chart[0]}
                  format={(n) => `${n.toFixed(0)}%`}
                  height={150}
                />
              </Panel>

              <Panel
                title="Séries temporais"
                icon={<Activity size={15} />}
                hint="Usado nos painéis de CPU e memória. Barras não entram aqui: uso ao longo do tempo é um sinal contínuo e barras sugerem contagens separadas."
              >
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4" onMouseLeave={() => setHoverSerie(null)}>
                  {SERIES_OPTIONS.map((o) => (
                    <EscolhaGrafico
                      key={o.id}
                      label={o.label}
                      hint={o.hint}
                      ativo={o.id === serieKind}
                      onSelect={() => setSerie(o.id)}
                      onHover={() => setHoverSerie(o.id)}
                    >
                      <TimeSeries
                        points={SERIE}
                        kind={o.id}
                        color={preview.chart[0]}
                        format={() => ""}
                        height={54}
                      />
                    </EscolhaGrafico>
                  ))}
                </div>
              </Panel>

              <Panel
                title="Prévia — mods por loader"
                hint={`${CATEGORY_OPTIONS.find((o) => o.id === (hoverCat ?? catKind))?.label} — usado nos painéis de contagem da Visão geral.`}
              >
                {/* Altura reservada: rosca/pizza medem ~168px e barras ~60px.
                    Sem isso a grade abaixo se desloca ao passar o mouse e o
                    hover salta para o cartão vizinho, piscando entre os dois. */}
                <div className="flex min-h-[168px] items-center">
                  <CategoryChart
                    data={AMOSTRA.map((d, i) => ({ ...d, color: preview.chart[i] }))}
                    kind={hoverCat ?? catKind}
                  />
                </div>
              </Panel>

              <Panel
                title="Gráficos de categoria"
                icon={<BarChart3 size={15} />}
                hint="Usado em mods por loader, mods por instância e maiores mods."
              >
                <div className="grid gap-2 sm:grid-cols-3" onMouseLeave={() => setHoverCat(null)}>
                  {CATEGORY_OPTIONS.map((o) => (
                    <EscolhaGrafico
                      key={o.id}
                      label={o.label}
                      hint={o.hint}
                      ativo={o.id === catKind}
                      onSelect={() => setCat(o.id)}
                      onHover={() => setHoverCat(o.id)}
                    >
                      <div className="pointer-events-none flex h-[104px] items-center justify-center">
                        <CategoryChart
                          data={AMOSTRA.map((d, i) => ({ ...d, color: preview.chart[i] }))}
                          kind={o.id}
                          size={96}
                        />
                      </div>
                    </EscolhaGrafico>
                  ))}
                </div>
              </Panel>
            </>
          )}

          {secao === "perfil" && <ProfileContent />}
        </div>
      </div>
    </div>
  );
}
