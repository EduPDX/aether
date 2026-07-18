import { Check } from "lucide-react";
import type { FileEntry } from "../../lib/api";
import { formatBytes } from "../../lib/api";
import { FileIcon } from "./FileIcon";

export type IconSize = "md" | "lg";

const TILE: Record<IconSize, { min: string; icon: number; pad: string }> = {
  md: { min: "104px", icon: 34, pad: "p-2.5" },
  lg: { min: "148px", icon: 52, pad: "p-3.5" },
};

/**
 * Visão em ícones grandes, no espírito do "Ícones grandes" do Explorer:
 * o ícone é a âncora visual e o nome vem abaixo, quebrando em até duas linhas.
 */
export function FileGrid({
  entries,
  selected,
  size = "lg",
  onOpen,
  onToggleSelect,
}: {
  entries: FileEntry[];
  selected: Set<string>;
  size?: IconSize;
  onOpen: (entry: FileEntry) => void;
  onToggleSelect: (name: string, checked: boolean) => void;
}) {
  const t = TILE[size];
  return (
    <div
      className="grid gap-2 p-3"
      style={{ gridTemplateColumns: `repeat(auto-fill, minmax(${t.min}, 1fr))` }}
    >
      {entries.map((entry) => {
        const isSel = selected.has(entry.name);
        return (
          <button
            key={entry.name}
            onDoubleClick={() => onOpen(entry)}
            onClick={(e) => {
              // Ctrl/Shift/clique no marcador = seleção; clique simples abre.
              if (e.ctrlKey || e.metaKey || e.shiftKey) onToggleSelect(entry.name, !isSel);
              else onOpen(entry);
            }}
            title={`${entry.name}${entry.is_dir ? "" : ` — ${formatBytes(entry.size)}`}`}
            className={`group relative flex cursor-pointer flex-col items-center gap-1.5 rounded-lg border ${
              t.pad
            } text-center transition-colors ${
              isSel
                ? "border-accent bg-accent/10"
                : "border-transparent hover:border-border hover:bg-surface-2"
            }`}
          >
            {/* Marcador de seleção: sempre visível quando marcado, no hover caso contrário. */}
            <span
              role="checkbox"
              aria-checked={isSel}
              aria-label={`Selecionar ${entry.name}`}
              onClick={(e) => {
                e.stopPropagation();
                onToggleSelect(entry.name, !isSel);
              }}
              className={`absolute top-1.5 left-1.5 flex h-4 w-4 items-center justify-center rounded border transition-opacity ${
                isSel
                  ? "border-accent bg-accent text-black opacity-100"
                  : "border-border bg-surface opacity-0 group-hover:opacity-100"
              }`}
            >
              {isSel && <Check size={11} strokeWidth={3} />}
            </span>

            <FileIcon name={entry.name} isDir={entry.is_dir} size={t.icon} />

            <span className="line-clamp-2 w-full text-[11px] leading-tight break-words">
              {entry.name}
            </span>
            <span className="text-[10px] text-muted">
              {entry.is_dir ? "Pasta" : formatBytes(entry.size)}
            </span>
          </button>
        );
      })}
    </div>
  );
}
