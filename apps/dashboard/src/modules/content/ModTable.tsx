import { Trash2 } from "lucide-react";
import type { ContentItem } from "../../lib/api";
import { formatBytes } from "../../lib/api";
import { Badge, Switch } from "../../components/ui";

/**
 * Visão densa da lista de mods. Complementa os cards: com centenas de mods,
 * a grade vira rolagem infinita — aqui cabem ~4x mais linhas na mesma tela.
 */
export function ModTable({
  items,
  onToggle,
  onTrash,
  onOpen,
}: {
  items: ContentItem[];
  onToggle: (file: string) => void;
  onTrash: (item: ContentItem) => void;
  onOpen: (item: ContentItem) => void;
}) {
  return (
    <table className="w-full text-left text-xs">
      <thead className="sticky top-0 z-10 bg-surface-2 text-muted">
        <tr>
          <th className="w-14 px-3 py-2 font-semibold">Ativo</th>
          <th className="px-3 py-2 font-semibold">Mod</th>
          <th className="w-24 px-3 py-2 font-semibold">Versão</th>
          <th className="w-20 px-3 py-2 font-semibold">MC</th>
          <th className="w-24 px-3 py-2 font-semibold">Loader</th>
          <th className="w-24 px-3 py-2 font-semibold">Tamanho</th>
          <th className="w-10 px-3 py-2" />
        </tr>
      </thead>
      <tbody className="divide-y divide-border">
        {items.map((item) => {
          const m = item.metadata;
          return (
            <tr
              key={item.file}
              onClick={() => onOpen(item)}
              title="Ver detalhes do mod"
              className={`group cursor-pointer hover:bg-surface-2 ${item.enabled ? "" : "opacity-55"}`}
            >
              <td className="px-3 py-1.5" onClick={(e) => e.stopPropagation()}>
                <Switch
                  checked={item.enabled}
                  onChange={() => onToggle(item.file)}
                  title={item.enabled ? "Desativar" : "Ativar"}
                />
              </td>
              <td className="px-3 py-1.5">
                <span className="flex min-w-0 items-center gap-2">
                  {item.icon_url ? (
                    <img
                      src={item.icon_url}
                      alt=""
                      className="h-5 w-5 shrink-0 rounded bg-surface-3 object-contain [image-rendering:pixelated]"
                    />
                  ) : (
                    <span className="h-5 w-5 shrink-0 rounded bg-surface-3" />
                  )}
                  <span className="truncate font-medium" title={item.file}>
                    {m.display_name}
                  </span>
                  {item.duplicate && <Badge tone="orange">dup</Badge>}
                  {m.client_only && <Badge tone="blue">client</Badge>}
                  {m.error && (
                    <Badge tone="red" title={m.error}>
                      erro
                    </Badge>
                  )}
                </span>
              </td>
              <td className="px-3 py-1.5 text-muted">{m.version || "—"}</td>
              <td className="px-3 py-1.5 text-muted">{m.game_version || "—"}</td>
              <td className="px-3 py-1.5 text-muted">{m.loader || "—"}</td>
              <td className="px-3 py-1.5 text-muted tabular-nums">{formatBytes(item.size_bytes)}</td>
              <td className="px-3 py-1.5" onClick={(e) => e.stopPropagation()}>
                <button
                  onClick={() => onTrash(item)}
                  title="Mover para a lixeira"
                  className="cursor-pointer text-muted opacity-0 transition-opacity group-hover:opacity-100 hover:text-danger"
                >
                  <Trash2 size={14} />
                </button>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
