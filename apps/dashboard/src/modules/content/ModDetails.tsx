import { ExternalLink, Package } from "lucide-react";
import { Badge, Modal } from "../../components/ui";
import type { ContentItem } from "../../lib/api";
import { formatBytes } from "../../lib/api";

function Linha({ rotulo, children }: { rotulo: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-3 border-b border-border py-1.5 last:border-0">
      <span className="w-28 shrink-0 text-[11px] text-muted">{rotulo}</span>
      <span className="min-w-0 flex-1 text-xs break-words">{children}</span>
    </div>
  );
}

/** Ficha completa do mod: tudo que o analisador extraiu do .jar. */
export function ModDetails({
  item,
  onClose,
}: {
  item: ContentItem | null;
  onClose: () => void;
}) {
  if (!item) return null;
  const m = item.metadata;
  const obrigatorias = m.dependencies.filter((d) => d.mandatory);
  const opcionais = m.dependencies.filter((d) => !d.mandatory);

  return (
    <Modal open onClose={onClose} title={m.display_name || item.file} size="lg">
      <div className="flex gap-4">
        {item.icon_url ? (
          <img
            src={item.icon_url}
            alt=""
            className="h-20 w-20 shrink-0 rounded-lg bg-surface-2 object-contain [image-rendering:pixelated]"
          />
        ) : (
          <span className="flex h-20 w-20 shrink-0 items-center justify-center rounded-lg bg-surface-2">
            <Package size={30} className="text-muted" />
          </span>
        )}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            {m.version && <Badge tone="neutral">v{m.version}</Badge>}
            {m.game_version && <Badge tone="green">MC {m.game_version}</Badge>}
            {m.loader && <Badge tone="orange">{m.loader}</Badge>}
            <Badge tone={item.enabled ? "green" : "neutral"}>
              {item.enabled ? "ativado" : "desativado"}
            </Badge>
            {item.duplicate && <Badge tone="orange">duplicado</Badge>}
            {m.client_only && <Badge tone="blue">só cliente</Badge>}
          </div>
          {m.description && (
            <p className="mt-2 text-xs leading-relaxed text-muted">{m.description}</p>
          )}
        </div>
      </div>

      <div className="mt-4">
        {m.content_id && <Linha rotulo="Identificador"><code>{m.content_id}</code></Linha>}
        {m.authors && <Linha rotulo="Autores">{m.authors}</Linha>}
        {m.license && <Linha rotulo="Licença">{m.license}</Linha>}
        <Linha rotulo="Arquivo"><code>{item.file}</code></Linha>
        <Linha rotulo="Tamanho">{formatBytes(item.size_bytes)}</Linha>
        <Linha rotulo="Modificado">
          {new Date(item.mtime * 1000).toLocaleString("pt-BR")}
        </Linha>
        {m.homepage && (
          <Linha rotulo="Site">
            <a
              href={m.homepage}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-1 text-accent hover:underline"
            >
              {m.homepage} <ExternalLink size={11} />
            </a>
          </Linha>
        )}
        {m.error && (
          <Linha rotulo="Erro de leitura">
            <span className="text-danger">{m.error}</span>
          </Linha>
        )}
      </div>

      {m.dependencies.length > 0 && (
        <div className="mt-4">
          <h3 className="mb-1.5 text-xs font-semibold">
            Dependências <span className="text-muted">({m.dependencies.length})</span>
          </h3>
          <div className="flex flex-wrap gap-1.5">
            {obrigatorias.map((d) => (
              <Badge key={d.content_id} tone="neutral" title="Obrigatória">
                {d.content_id}
                {d.version_range && ` ${d.version_range}`}
              </Badge>
            ))}
            {opcionais.map((d) => (
              <span
                key={d.content_id}
                className="rounded px-1.5 py-0.5 text-[11px] text-muted/70 ring-1 ring-border"
                title="Opcional"
              >
                {d.content_id}
              </span>
            ))}
          </div>
        </div>
      )}
    </Modal>
  );
}
