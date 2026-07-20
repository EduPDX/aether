import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  FolderOpen,
  Info,
  RotateCcw,
  Trash2,
  X,
} from "lucide-react";
import { useState } from "react";
import { Badge, Button, Spinner } from "../../components/ui";
import { FileIcon } from "../files/FileIcon";
import { useDialog } from "../../components/Dialog";
import type { Instance, TrashItem } from "../../lib/api";
import { api, formatBytes } from "../../lib/api";

/** "há 3 dias" comunica melhor que uma data absoluta para algo recém-apagado. */
function quando(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const min = Math.floor(ms / 60000);
  if (min < 1) return "agora há pouco";
  if (min < 60) return `há ${min} min`;
  const h = Math.floor(min / 60);
  if (h < 24) return `há ${h} h`;
  const d = Math.floor(h / 24);
  return d === 1 ? "ontem" : `há ${d} dias`;
}

/** Pasta de origem, para diferenciar dois arquivos de mesmo nome. */
function pastaDe(caminho: string): string {
  const corte = caminho.lastIndexOf("/");
  return corte === -1 ? "/" : caminho.slice(0, corte);
}

export function TrashView({ instance }: { instance: Instance }) {
  const qc = useQueryClient();
  const dialog = useDialog();
  const [erro, setErro] = useState("");

  const query = useQuery({
    queryKey: ["trash", instance.id],
    queryFn: () => api.listTrash(instance.id),
  });

  const invalidar = () => {
    qc.invalidateQueries({ queryKey: ["trash", instance.id] });
    // O explorador precisa reaparecer com o item de volta.
    qc.invalidateQueries({ queryKey: ["files", instance.id] });
    qc.invalidateQueries({ queryKey: ["content", instance.id] });
  };

  const restaurar = useMutation({
    mutationFn: (item: TrashItem) => api.restoreTrash(instance.id, item.id),
    onSuccess: invalidar,
    onError: (e) => setErro(String(e)),
  });

  const apagar = useMutation({
    mutationFn: (item: TrashItem) => api.purgeTrash(instance.id, item.id),
    onSuccess: invalidar,
    onError: (e) => setErro(String(e)),
  });

  const esvaziar = useMutation({
    mutationFn: () => api.emptyTrash(instance.id),
    onSuccess: invalidar,
    onError: (e) => setErro(String(e)),
  });

  if (query.isLoading) return <Spinner />;
  const itens = query.data?.items ?? [];
  const total = query.data?.total_bytes ?? 0;

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <div className="sticky top-0 z-10 flex items-center gap-3 border-b border-border bg-bg px-4 py-2">
        <Trash2 size={15} />
        <span className="text-sm font-semibold">Lixeira</span>
        {itens.length > 0 && (
          <span className="text-xs text-muted">
            {itens.length} item(ns) · {formatBytes(total)}
          </span>
        )}
        {erro && <span className="text-xs text-danger">{erro}</span>}
        <Button
          className="ml-auto"
          variant="ghost"
          disabled={itens.length === 0 || esvaziar.isPending}
          onClick={async () => {
            const ok = await dialog.confirm({
              title: "Esvaziar a lixeira",
              message: `${itens.length} item(ns), ${formatBytes(total)}. Isto não tem volta.`,
              confirmText: "Esvaziar",
              tone: "danger",
            });
            if (ok) esvaziar.mutate();
          }}
        >
          <X size={13} /> Esvaziar
        </Button>
      </div>

      <div className="mx-auto w-full max-w-4xl space-y-3 p-4">
        <div className="flex items-start gap-2.5 rounded-lg border border-border bg-surface-2 px-3 py-2 text-xs text-muted">
          <Info size={14} className="mt-0.5 shrink-0" />
          <span>
            O que você apaga em Arquivos e em Mods para aqui, e volta para o mesmo
            lugar ao restaurar. A limpeza automática remove o que passa de 30 dias.
          </span>
        </div>

        {itens.length === 0 ? (
          <p className="py-16 text-center text-sm text-muted">
            A lixeira está vazia.
          </p>
        ) : (
          <div className="divide-y divide-border overflow-hidden rounded-xl border border-border">
            {itens.map((item) => (
              <div key={item.id} className="flex items-center gap-3 bg-surface px-4 py-2.5">
                {item.is_dir ? (
                  <FolderOpen size={18} className="shrink-0 text-muted" />
                ) : (
                  <FileIcon name={item.name} isDir={false} size={18} />
                )}

                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm">{item.name}</span>
                    {item.is_dir && <Badge tone="neutral">pasta</Badge>}
                  </div>
                  <div className="truncate text-[11px] text-muted">
                    <code>{pastaDe(item.original_path)}</code> ·{" "}
                    {formatBytes(item.size_bytes)} · {quando(item.trashed_at)}
                  </div>
                </div>

                <span className="flex shrink-0 gap-1.5">
                  <Button
                    variant="ghost"
                    title={`Devolver para ${item.original_path}`}
                    disabled={restaurar.isPending}
                    onClick={() => {
                      setErro("");
                      restaurar.mutate(item);
                    }}
                  >
                    <RotateCcw size={13} /> Restaurar
                  </Button>
                  <Button
                    variant="ghost"
                    title="Apagar de vez"
                    disabled={apagar.isPending}
                    onClick={async () => {
                      const ok = await dialog.confirm({
                        title: "Apagar de vez",
                        message: `“${item.name}” some para sempre. Isto não tem volta.`,
                        confirmText: "Apagar",
                        tone: "danger",
                      });
                      if (ok) {
                        setErro("");
                        apagar.mutate(item);
                      }
                    }}
                  >
                    <Trash2 size={13} />
                  </Button>
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
