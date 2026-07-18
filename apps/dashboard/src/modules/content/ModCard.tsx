import { Trash2 } from "lucide-react";
import type { ContentItem } from "../../lib/api";
import { formatBytes } from "../../lib/api";
import { Badge, Switch } from "../../components/ui";

const FALLBACK_COLORS = ["#3b82f6", "#8b5cf6", "#ec4899", "#f97316", "#14b8a6", "#84cc16"];

function fallbackColor(name: string): string {
  let h = 0;
  for (const c of name) h = (h * 31 + c.charCodeAt(0)) | 0;
  return FALLBACK_COLORS[Math.abs(h) % FALLBACK_COLORS.length];
}

function loaderTone(loader: string): "green" | "blue" | "orange" | "neutral" {
  if (loader === "Forge") return "orange";
  if (loader === "NeoForge") return "orange";
  if (loader === "Fabric") return "blue";
  return "neutral";
}

export function ModCard({
  item,
  onToggle,
  onTrash,
  onOpen,
}: {
  item: ContentItem;
  onToggle: () => void;
  onTrash: () => void;
  onOpen?: () => void;
}) {
  const m = item.metadata;
  return (
    <div
      onClick={onOpen}
      title="Ver detalhes do mod"
      className={`group flex cursor-pointer gap-3 rounded-lg border bg-surface p-3 transition-colors hover:bg-surface-2 ${
        item.duplicate ? "border-warn/50" : "border-border"
      } ${item.enabled ? "" : "opacity-55"}`}
    >
      {item.icon_url ? (
        <img
          src={item.icon_url}
          alt=""
          className="h-12 w-12 shrink-0 rounded-md bg-surface-3 object-contain [image-rendering:pixelated]"
        />
      ) : (
        <div
          className="flex h-12 w-12 shrink-0 items-center justify-center rounded-md text-lg font-bold text-white"
          style={{ backgroundColor: fallbackColor(m.display_name) }}
        >
          {m.display_name.charAt(0).toUpperCase()}
        </div>
      )}

      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-2">
          <span className="truncate text-sm font-semibold" title={item.file}>
            {m.display_name}
          </span>
          <div className="flex shrink-0 items-center gap-1.5">
            <button
              onClick={(e) => {
                e.stopPropagation();
                onTrash();
              }}
              title="Mover para a lixeira"
              className="cursor-pointer text-muted opacity-0 transition-opacity hover:text-danger group-hover:opacity-100"
            >
              <Trash2 size={15} />
            </button>
            <span onClick={(e) => e.stopPropagation()}>
              <Switch checked={item.enabled} onChange={onToggle} title={item.enabled ? "Desativar" : "Ativar"} />
            </span>
          </div>
        </div>

        <div className="mt-1 flex flex-wrap items-center gap-1">
          {m.version && <Badge tone="neutral">v{m.version}</Badge>}
          {m.game_version && <Badge tone="green">MC {m.game_version}</Badge>}
          {m.loader && <Badge tone={loaderTone(m.loader)}>{m.loader}</Badge>}
          {item.duplicate && <Badge tone="orange">duplicado</Badge>}
          {m.client_only && <Badge tone="blue">client-only</Badge>}
          {m.error && (
            <Badge tone="red" title={m.error}>
              erro
            </Badge>
          )}
        </div>

        {m.description && (
          <p className="mt-1 line-clamp-2 text-xs text-muted" title={m.description}>
            {m.description}
          </p>
        )}
        <div className="mt-1 text-[11px] text-muted/70">
          {m.authors && <span>{m.authors} · </span>}
          {formatBytes(item.size_bytes)}
        </div>
      </div>
    </div>
  );
}
