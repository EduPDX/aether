import { useState } from "react";

export interface BarDatum {
  label: string;
  value: number;
  /** Cor da entidade. Ausente = série única (usa o accent do tema). */
  color?: string;
  hint?: string;
}

/**
 * Barras horizontais para magnitude/ranking.
 * Marcas finas, extremidade de dado arredondada (4px) ancorada na linha de
 * base, 2px de respiro entre barras, rótulo direto no fim e hover com o
 * valor exato. Sem grade: o rótulo já carrega o número.
 */
export function HBarChart({
  data,
  format = (n) => String(n),
  emptyText = "Sem dados.",
}: {
  data: BarDatum[];
  format?: (n: number) => string;
  emptyText?: string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  if (data.length === 0) return <p className="py-6 text-center text-xs text-muted">{emptyText}</p>;

  const max = Math.max(...data.map((d) => d.value), 1);

  return (
    <div className="flex flex-col gap-[2px]">
      {data.map((d, i) => (
        <div
          // Rótulo não é identidade: dois mods distintos podem ter o mesmo
          // nome de exibição e a chave duplicada fazia o React omitir linhas.
          key={`${d.label}-${i}`}
          className="group grid grid-cols-[minmax(0,9rem)_1fr_auto] items-center gap-2 rounded px-1 py-[3px] transition-colors"
          style={{ background: hover === i ? "var(--color-surface-2)" : "transparent" }}
          onMouseEnter={() => setHover(i)}
          onMouseLeave={() => setHover(null)}
          title={d.hint ?? `${d.label}: ${format(d.value)}`}
        >
          <span className="truncate text-[11.5px] text-muted" title={d.label}>
            {d.label}
          </span>
          <span className="h-2.5 w-full overflow-hidden">
            <span
              className="block h-full transition-[width] duration-300"
              style={{
                width: `${Math.max((d.value / max) * 100, 1.5)}%`,
                background: d.color ?? "var(--color-accent-dim)",
                borderRadius: "0 4px 4px 0",
              }}
            />
          </span>
          <span className="text-right font-mono text-[11px] tabular-nums text-text">
            {format(d.value)}
          </span>
        </div>
      ))}
    </div>
  );
}

/** Escolhe a forma do gráfico de categoria conforme a preferência do usuário. */
export function CategoryChart({
  data,
  kind,
  format,
  emptyText,
  size,
}: {
  data: BarDatum[];
  kind: CategoryKind;
  format?: (n: number) => string;
  emptyText?: string;
  /** Diâmetro da rosca/pizza — reduzido nas prévias das configurações. */
  size?: number;
}) {
  if (kind === "barras") return <HBarChart data={data} format={format} emptyText={emptyText} />;
  return <Donut data={data} variant={kind} size={size} />;
}

/** Legenda — obrigatória com 2+ entidades, para identidade nunca ser só cor. */
export function Legend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
      {items.map((it, i) => (
        <span key={`${it.label}-${i}`} className="flex items-center gap-1.5 text-[11px] text-muted">
          <span
            className="inline-block h-2.5 w-2.5 rounded-sm"
            style={{ background: it.color }}
            aria-hidden
          />
          {it.label}
        </span>
      ))}
    </div>
  );
}


/** Medidor de uso (0-100%) — leitura instantânea, sem virar gráfico. */
export function Gauge({
  percent,
  label,
  detail,
  color,
}: {
  percent: number;
  label: string;
  detail: string;
  color: string;
}) {
  const pct = Math.min(Math.max(percent, 0), 100);
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <div className="flex items-baseline justify-between">
        <span className="text-[11px] font-semibold tracking-wider text-muted uppercase">
          {label}
        </span>
        <span className="font-mono text-lg font-bold tabular-nums">{pct.toFixed(0)}%</span>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-surface-3">
        <div
          className="h-full transition-[width] duration-500"
          style={{ width: `${pct}%`, background: color, borderRadius: "0 4px 4px 0" }}
        />
      </div>
      <div className="mt-1.5 text-[11px] text-muted">{detail}</div>
    </div>
  );
}

/**
 * Tipos para métrica contínua no tempo (CPU, memória).
 *
 * "barras" saiu daqui de propósito: amostra de uso ao longo do tempo é um
 * sinal contínuo, e barras sugerem contagens discretas e independentes —
 * fica ruim de ler. Barras agora só existem em {@link CategoryKind}.
 */
export type SeriesKind = "area" | "linha" | "degrau" | "suave";

/** Tipos para composição/ranking por categoria (mods por loader, por instância). */
export type CategoryKind = "rosca" | "pizza" | "barras";

/** Caminho em degraus: o valor vale até a próxima amostra. */
function stepPath(pts: { x: number; y: number }[]): string {
  return pts
    .map((p, i) => (i === 0 ? `${p.x},${p.y}` : `${p.x},${pts[i - 1].y} ${p.x},${p.y}`))
    .join(" ");
}

/** Curva suave (Catmull-Rom convertida em Bézier cúbica). */
function smoothPath(pts: { x: number; y: number }[]): string {
  if (pts.length < 2) return "";
  let d = `M ${pts[0].x},${pts[0].y}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] ?? pts[i];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[i + 2] ?? p2;
    const c1x = p1.x + (p2.x - p0.x) / 6;
    const c1y = p1.y + (p2.y - p0.y) / 6;
    const c2x = p2.x - (p3.x - p1.x) / 6;
    const c2y = p2.y - (p3.y - p1.y) / 6;
    d += ` C ${c1x},${c1y} ${c2x},${c2y} ${p2.x},${p2.y}`;
  }
  return d;
}

/** Série temporal com o tipo de visualização escolhido pelo usuário. */
export function TimeSeries({
  points,
  kind,
  color,
  format = (n) => `${n}`,
  height = 120,
}: {
  points: number[];
  kind: SeriesKind;
  color: string;
  format?: (n: number) => string;
  height?: number;
}) {
  if (points.length < 2)
    return (
      <p className="py-8 text-center text-xs text-muted">
        Coletando dados… atualize em alguns segundos.
      </p>
    );

  const w = 100;
  const max = Math.max(...points, 1);
  const pts = points.map((v, i) => ({
    x: (i / (points.length - 1)) * w,
    y: height - (v / max) * (height - 8) - 4,
    v,
  }));
  const line = pts.map((p) => `${p.x},${p.y}`).join(" ");
  const step = stepPath(pts);
  const smooth = smoothPath(pts);
  const last = points[points.length - 1];

  return (
    <div>
      <div className="mb-1 flex items-baseline gap-2">
        <span className="font-mono text-xl font-bold tabular-nums">{format(last)}</span>
        <span className="text-[11px] text-muted">agora · pico {format(max)}</span>
      </div>
      <svg
        viewBox={`0 0 ${w} ${height}`}
        preserveAspectRatio="none"
        className="w-full"
        style={{ height }}
        role="img"
        aria-label={`Série temporal, valor atual ${format(last)}`}
      >
        {kind === "suave" ? (
          <>
            <path
              d={`${smooth} L ${w},${height} L 0,${height} Z`}
              fill={color}
              opacity="0.18"
            />
            <path
              d={smooth}
              fill="none"
              stroke={color}
              strokeWidth="2"
              vectorEffect="non-scaling-stroke"
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          </>
        ) : (
          <>
            {kind === "area" && (
              <polygon points={`0,${height} ${line} ${w},${height}`} fill={color} opacity="0.18" />
            )}
            <polyline
              points={kind === "degrau" ? step : line}
              fill="none"
              stroke={color}
              strokeWidth="2"
              vectorEffect="non-scaling-stroke"
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          </>
        )}
      </svg>
    </div>
  );
}

/**
 * Rosca (donut) para parte-de-todo com poucas categorias.
 * Legenda sempre presente e rótulo direto no centro — identidade nunca
 * depende só da cor. Segmentos separados por 2px de respiro.
 */
export function Donut({
  data,
  size = 168,
  variant = "rosca",
}: {
  data: { label: string; value: number; color?: string }[];
  size?: number;
  /** "pizza" preenche o miolo; o número central some por falta de espaço. */
  variant?: "rosca" | "pizza";
}) {
  const [hover, setHover] = useState<number | null>(null);
  const total = data.reduce((s, d) => s + d.value, 0);
  if (total === 0) return <p className="py-6 text-center text-xs text-muted">Sem dados.</p>;

  const pizza = variant === "pizza";
  // Na pizza o raio do traço é metade do disco e a espessura o preenche até
  // o centro; na rosca o anel é fino e sobra miolo para o número.
  const r = pizza ? 38 : 60;
  const espessura = pizza ? 76 : 20;
  const c = 2 * Math.PI * r;
  let offset = 0;
  const focused = hover !== null ? data[hover] : null;

  return (
    <div className="flex items-center gap-4">
      <svg viewBox="0 0 160 160" style={{ width: size, height: size }} className="shrink-0">
        <g transform="translate(80,80) rotate(-90)">
          {data.map((d, i) => {
            const frac = d.value / total;
            const len = Math.max(frac * c - 2, 0); // 2px de respiro entre fatias
            const dash = `${len} ${c - len}`;
            const el = (
              <circle
                key={`${d.label}-${i}`}
                r={r}
                fill="none"
                stroke={d.color ?? "var(--color-accent-dim)"}
                strokeWidth={hover === i ? espessura + 6 : espessura}
                strokeDasharray={dash}
                strokeDashoffset={-offset}
                onMouseEnter={() => setHover(i)}
                onMouseLeave={() => setHover(null)}
                style={{ transition: "stroke-width 150ms" }}
              >
                <title>{`${d.label}: ${d.value} (${(frac * 100).toFixed(1)}%)`}</title>
              </circle>
            );
            offset += frac * c;
            return el;
          })}
        </g>
        {!pizza && (
          <>
            <text
              x="80"
              y="76"
              textAnchor="middle"
              className="fill-text"
              style={{ fontSize: 22, fontWeight: 700 }}
            >
              {focused ? focused.value : total}
            </text>
            <text x="80" y="92" textAnchor="middle" className="fill-muted" style={{ fontSize: 9 }}>
              {focused ? focused.label : "total"}
            </text>
          </>
        )}
      </svg>

      <div className="flex min-w-0 flex-col gap-1">
        {data.map((d, i) => (
          <span
            key={`${d.label}-${i}`}
            className="flex items-center gap-2 text-[11px]"
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover(null)}
          >
            <span
              className="inline-block h-2.5 w-2.5 shrink-0 rounded-sm"
              style={{ background: d.color ?? "var(--color-accent-dim)" }}
            />
            <span className="truncate text-muted">{d.label}</span>
            <span className="ml-auto font-mono tabular-nums text-text">
              {((d.value / total) * 100).toFixed(0)}%
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}
