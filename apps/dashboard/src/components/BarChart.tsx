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
          key={d.label}
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

/** Legenda — obrigatória com 2+ entidades, para identidade nunca ser só cor. */
export function Legend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
      {items.map((it) => (
        <span key={it.label} className="flex items-center gap-1.5 text-[11px] text-muted">
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

export type SeriesKind = "linha" | "area" | "barras";

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
        {kind === "barras" ? (
          pts.map((p, i) => (
            <rect
              key={i}
              x={p.x - w / points.length / 2 + 0.3}
              y={p.y}
              width={Math.max(w / points.length - 0.6, 0.4)}
              height={height - p.y}
              fill={color}
              rx="0.4"
            />
          ))
        ) : (
          <>
            {kind === "area" && (
              <polygon
                points={`0,${height} ${line} ${w},${height}`}
                fill={color}
                opacity="0.18"
              />
            )}
            <polyline
              points={line}
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
