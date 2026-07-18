import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2, CircleAlert, Laptop, Server, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { Badge, Button, Panel, Spinner, StatTile } from "../../components/ui";
import type { ContentItem, Instance } from "../../lib/api";
import { api, formatBytes } from "../../lib/api";

function Linha({ item, acao }: { item: ContentItem; acao?: React.ReactNode }) {
  const m = item.metadata;
  return (
    <div className="flex items-center gap-3 rounded-md border border-border bg-surface-2 px-3 py-2">
      {item.icon_url ? (
        <img
          src={item.icon_url}
          alt=""
          className="h-8 w-8 shrink-0 rounded bg-surface-3 object-contain [image-rendering:pixelated]"
        />
      ) : (
        <div className="h-8 w-8 shrink-0 rounded bg-surface-3" />
      )}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-medium">{m.display_name}</span>
          {m.client_only && <Badge tone="blue">client-only</Badge>}
        </div>
        <div className="truncate text-[11px] text-muted">
          {m.version && `v${m.version} · `}
          {item.file} · {formatBytes(item.size_bytes)}
        </div>
      </div>
      {acao}
    </div>
  );
}

/**
 * Diferença entre os mods do servidor e os do perfil de cliente da MESMA
 * instância — o que responde "por que o jogo crashou ao entrar no mundo?"
 * antes de o jogador descobrir crashando.
 */
export function ServerClientDiff({ instance }: { instance: Instance }) {
  const qc = useQueryClient();
  const [erro, setErro] = useState("");

  const query = useQuery({
    queryKey: ["diff", instance.id],
    queryFn: () => api.compare(instance.id, instance.id, "mod", "mod_client"),
  });

  const copiar = useMutation({
    mutationFn: ({ file, para }: { file: string; para: "cliente" | "servidor" }) =>
      api.copy(
        instance.id,
        instance.id,
        file,
        para === "cliente" ? "mod" : "mod_client",
        para === "cliente" ? "mod_client" : "mod",
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["diff", instance.id] });
      qc.invalidateQueries({ queryKey: ["content"] });
    },
    onError: (e) => setErro(String(e instanceof Error ? e.message : e)),
  });

  if (query.isLoading) return <Spinner />;
  if (query.isError)
    return (
      <div className="p-6 text-sm text-danger">
        Erro ao comparar: {String(query.error)}
        <p className="mt-2 text-xs text-muted">
          Confira se a instância tem a pasta do perfil de cliente configurada.
        </p>
      </div>
    );

  const d = query.data!;
  // Um mod marcado client-only ausente no servidor é esperado, não problema:
  // shader, minimapa e afins nunca rodam no servidor.
  const soNoClienteEsperado = d.only_in_b.filter((i) => i.metadata.client_only);
  const soNoClienteInesperado = d.only_in_b.filter((i) => !i.metadata.client_only);
  const problemas = d.only_in_a.length + d.version_diffs.length;

  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="mx-auto flex w-full max-w-[1900px] flex-col gap-4">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatTile
            icon={<TriangleAlert size={14} />}
            label="Faltando no cliente"
            value={String(d.only_in_a.length)}
            sub="o servidor exige, o cliente não tem"
            tone={d.only_in_a.length > 0 ? "danger" : undefined}
          />
          <StatTile
            icon={<CircleAlert size={14} />}
            label="Versão diferente"
            value={String(d.version_diffs.length)}
            sub="mesmo mod, versões que não batem"
            tone={d.version_diffs.length > 0 ? "warn" : undefined}
          />
          <StatTile
            icon={<Laptop size={14} />}
            label="Só no cliente"
            value={String(d.only_in_b.length)}
            sub={`${soNoClienteEsperado.length} marcados client-only`}
          />
          <StatTile
            icon={<CheckCircle2 size={14} />}
            label="Situação"
            value={problemas === 0 ? "OK" : String(problemas)}
            sub={problemas === 0 ? "nada a corrigir" : "pontos de atenção"}
            tone={problemas === 0 ? "accent" : "warn"}
          />
        </div>

        {erro && <p className="text-xs text-danger">{erro}</p>}

        {problemas === 0 && (
          <Panel title="Tudo alinhado">
            <p className="text-sm text-muted">
              Todo mod do servidor tem correspondente no perfil de cliente, nas mesmas versões.
              O que existe só no cliente é conteúdo visual, que não afeta a conexão.
            </p>
          </Panel>
        )}

        {d.only_in_a.length > 0 && (
          <Panel
            title="Faltando no cliente"
            icon={<Server size={15} />}
            hint="O servidor carrega estes mods e o perfil de cliente não. É a causa mais comum de o jogo recusar a entrada no mundo."
          >
            <div className="space-y-1.5">
              {d.only_in_a.map((item) => (
                <Linha
                  key={item.file}
                  item={item}
                  acao={
                    <Button
                      variant="primary"
                      disabled={copiar.isPending}
                      onClick={() => copiar.mutate({ file: item.file, para: "cliente" })}
                    >
                      <ArrowRight size={13} /> Enviar ao cliente
                    </Button>
                  }
                />
              ))}
            </div>
          </Panel>
        )}

        {d.version_diffs.length > 0 && (
          <Panel
            title="Versões que não batem"
            icon={<CircleAlert size={15} />}
            hint="Mesmo mod dos dois lados, em versões diferentes — costuma quebrar com erro de método ausente."
          >
            <div className="space-y-1.5">
              {d.version_diffs.map((v) => (
                <div
                  key={v.content_id}
                  className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md border border-border bg-surface-2 px-3 py-2 text-sm"
                >
                  <span className="font-medium">{v.content_id}</span>
                  <span className="flex items-center gap-1.5 text-xs text-muted">
                    <Server size={12} /> servidor
                    <b className="text-text">v{v.a.version || "?"}</b>
                    <Laptop size={12} className="ml-1.5" /> cliente
                    <b className="text-text">v{v.b.version || "?"}</b>
                  </span>
                  <Button
                    className="ml-auto"
                    disabled={copiar.isPending}
                    onClick={() => {
                      if (
                        confirm(
                          `Substituir a versão do cliente pela do servidor (${v.a.file})?\n\n` +
                            `O arquivo antigo do cliente (${v.b.file}) continua lá — remova-o na aba de mods do cliente.`,
                        )
                      )
                        copiar.mutate({ file: v.a.file, para: "cliente" });
                    }}
                  >
                    <ArrowRight size={13} /> Usar a do servidor
                  </Button>
                </div>
              ))}
            </div>
          </Panel>
        )}

        {soNoClienteInesperado.length > 0 && (
          <Panel
            title="Só no cliente"
            icon={<Laptop size={15} />}
            hint="Não estão marcados como client-only. Normalmente é conteúdo visual e não há problema, mas se algum precisar rodar no servidor, envie."
          >
            <div className="space-y-1.5">
              {soNoClienteInesperado.map((item) => (
                <Linha
                  key={item.file}
                  item={item}
                  acao={
                    <Button
                      disabled={copiar.isPending}
                      onClick={() => copiar.mutate({ file: item.file, para: "servidor" })}
                    >
                      <ArrowRight size={13} /> Enviar ao servidor
                    </Button>
                  }
                />
              ))}
            </div>
          </Panel>
        )}

        {soNoClienteEsperado.length > 0 && (
          <Panel
            title="Exclusivos do cliente"
            icon={<Laptop size={15} />}
            hint="Marcados como client-only pelo próprio mod — shaders, minimapas e afins. Não devem ir para o servidor."
          >
            <div className="space-y-1.5">
              {soNoClienteEsperado.map((item) => (
                <Linha key={item.file} item={item} />
              ))}
            </div>
          </Panel>
        )}
      </div>
    </div>
  );
}
