import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, HardDrive, Layers, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useDialog } from "../../components/Dialog";
import { Badge, Button, Panel, Spinner } from "../../components/ui";
import { api } from "../../lib/api";
import { subscribeTopic } from "../../lib/ws";

function formatBytes(n: number): string {
  if (n >= 1024 ** 3) return `${(n / 1024 ** 3).toFixed(1)} GB`;
  if (n >= 1024 ** 2) return `${(n / 1024 ** 2).toFixed(0)} MB`;
  return `${(n / 1024).toFixed(0)} KB`;
}

/**
 * Gerenciador de imagens de container: o que os providers pedem, o que já
 * está no disco e o que está sendo baixado. O progresso chega pelo tópico
 * ``images.pull`` do WebSocket — baixar imagem leva minutos e a request de
 * pull responde na hora (202).
 */
export function ImagesView() {
  const qc = useQueryClient();
  const dialog = useDialog();
  const query = useQuery({ queryKey: ["images"], queryFn: api.images });
  const [progresso, setProgresso] = useState<Record<string, string>>({});
  const [error, setError] = useState("");

  useEffect(() => {
    return subscribeTopic("images.pull", (msg) => {
      const ev = msg.payload;
      const image = String(ev.image ?? "");
      if (!image) return;
      if (ev.status === "done" || ev.status === "error") {
        setProgresso((p) => {
          const { [image]: _, ...resto } = p;
          return resto;
        });
        if (ev.status === "error") setError(`pull de ${image} falhou: ${ev.error}`);
        qc.invalidateQueries({ queryKey: ["images"] });
      } else if (ev.status === "progress") {
        const detail = (ev.detail ?? {}) as { status?: string; progress?: string };
        setProgresso((p) => ({
          ...p,
          [image]: [detail.status, detail.progress].filter(Boolean).join(" "),
        }));
      } else {
        setProgresso((p) => ({ ...p, [image]: "iniciando…" }));
      }
    });
  }, [qc]);

  const pull = useMutation({
    mutationFn: (image: string) => api.pullImage(image),
    onMutate: (image) => {
      setError("");
      setProgresso((p) => ({ ...p, [image]: "iniciando…" }));
    },
    onError: (e) => setError(String(e)),
  });

  const remove = useMutation({
    mutationFn: (image: string) => api.removeImage(image),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["images"] }),
    onError: (e) => setError(String(e)),
  });

  if (query.isError)
    return (
      <div className="p-6 text-sm text-muted">
        Não foi possível listar as imagens — o Docker está instalado e rodando na máquina do
        Core? ({String(query.error)})
      </div>
    );
  // data pode ser undefined fora de isLoading/isError (retry em andamento);
  // renderizar sem o guard derruba a árvore inteira.
  // data pode ser undefined fora de isLoading/isError (retry em andamento);
  // renderizar sem o guard derruba a árvore inteira.
  const data = query.data;
  if (!data) return <Spinner />;
  const instaladas = new Set(data.installed.flatMap((i) => i.tags.map((t) => t.split(":")[0])));

  return (
    <div className="mx-auto w-full max-w-4xl space-y-4 overflow-y-auto p-4">
      {error && <p className="text-xs text-danger">{error}</p>}

      <Panel
        title="Imagens dos providers"
        icon={<Layers size={15} />}
        hint="O que cada jogo usa para rodar em container."
        bodyClassName="px-0 pb-0"
      >
        <div className="divide-y divide-border border-t border-border">
          {data.referenced.map((ref) => {
            const baixando = progresso[ref.image] !== undefined || data.pulling.includes(ref.image);
            const instalada = instaladas.has(ref.image.split(":")[0]);
            return (
              <div key={ref.provider_id} className="flex items-center gap-3 px-4 py-2.5">
                <div className="min-w-0 flex-1">
                  <div className="text-sm">
                    <code>{ref.image}</code>
                  </div>
                  <div className="text-[11px] text-muted">
                    provider: {ref.provider_id}
                    {baixando && progresso[ref.image] && ` — ${progresso[ref.image]}`}
                  </div>
                </div>
                {instalada && <Badge tone="green">instalada</Badge>}
                {baixando ? (
                  <Badge tone="orange">baixando…</Badge>
                ) : (
                  <Button
                    disabled={pull.isPending}
                    onClick={() => pull.mutate(ref.image)}
                    title={instalada ? "Baixar de novo (atualizar)" : "Baixar imagem"}
                  >
                    <Download size={14} /> {instalada ? "Atualizar" : "Baixar"}
                  </Button>
                )}
              </div>
            );
          })}
          {data.referenced.length === 0 && (
            <p className="px-4 py-3 text-sm text-muted">
              Nenhum provider instalado declara imagem de container.
            </p>
          )}
        </div>
      </Panel>

      <Panel
        title="Instaladas no Docker"
        icon={<HardDrive size={15} />}
        bodyClassName="px-0 pb-0"
      >
        <div className="divide-y divide-border border-t border-border">
          {data.installed.map((img) => (
            <div key={img.id} className="flex items-center gap-3 px-4 py-2.5">
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm">
                  <code>{img.tags.join(", ") || img.id.slice(0, 19)}</code>
                </div>
                <div className="text-[11px] text-muted">{formatBytes(img.size_bytes)}</div>
              </div>
              <Button
                variant="danger"
                disabled={remove.isPending}
                onClick={async () => {
                  const alvo = img.tags[0] ?? img.id;
                  const ok = await dialog.confirm({
                    title: "Remover imagem",
                    message: `“${alvo}” sai do disco. Instâncias que a usam vão baixá-la de novo na próxima inicialização.`,
                    confirmText: "Remover",
                    tone: "danger",
                  });
                  if (ok) remove.mutate(alvo);
                }}
              >
                <Trash2 size={14} />
              </Button>
            </div>
          ))}
          {data.installed.length === 0 && (
            <p className="px-4 py-3 text-sm text-muted">Nenhuma imagem no disco ainda.</p>
          )}
        </div>
      </Panel>
    </div>
  );
}
