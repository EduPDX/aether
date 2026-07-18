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
