import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, GitCommitHorizontal, RefreshCw } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useDialog } from "../../components/Dialog";
import { Badge, Button, Panel, Spinner } from "../../components/ui";
import { api } from "../../lib/api";
import { subscribeTopic } from "../../lib/ws";

/**
 * Atualização da própria aplicação.
 *
 * O serviço reinicia no fim, então a conexão cai de propósito: a tela trata
 * isso como sucesso esperado, não como erro, e volta a consultar até o Core
 * responder de novo.
 */
export function SystemSection() {
  const qc = useQueryClient();
  const dialog = useDialog();
  const [linhas, setLinhas] = useState<string[]>([]);
  const [etapa, setEtapa] = useState("");
  const [erro, setErro] = useState("");
  const [reiniciando, setReiniciando] = useState(false);
  const fim = useRef<HTMLDivElement>(null);

  const status = useQuery({
    queryKey: ["update-status"],
    queryFn: api.updateStatus,
    // Enquanto reinicia, insiste até o Core voltar.
    refetchInterval: reiniciando ? 3000 : false,
    retry: reiniciando ? 20 : 1,
  });

  useEffect(() => {
    return subscribeTopic("update.progress", (msg) => {
      const p = msg.payload as {
        etapa?: string;
        descricao?: string;
        linha?: string;
        erro?: string;
      };
      if (p.linha) setLinhas((l) => [...l.slice(-200), p.linha!]);
      if (p.descricao) {
        setEtapa(p.descricao);
        setLinhas((l) => [...l.slice(-200), `— ${p.descricao}`]);
      }
      if (p.etapa === "erro" && p.erro) setErro(p.erro);
    });
  }, []);

  useEffect(() => {
    fim.current?.scrollIntoView({ block: "end" });
  }, [linhas]);

  const atualizar = useMutation({
    mutationFn: api.runUpdate,
    onMutate: () => {
      setErro("");
      setLinhas([]);
    },
    onSuccess: () => {
      setReiniciando(true);
      setEtapa("Reiniciando o serviço…");
      // O Core cai em seguida; quando voltar, o status recarrega sozinho.
      setTimeout(() => {
        setReiniciando(false);
        qc.invalidateQueries({ queryKey: ["update-status"] });
      }, 20000);
    },
    onError: (e) => setErro(String(e instanceof Error ? e.message : e)),
  });

  if (status.isLoading) return <Spinner />;

  const s = status.data;
  const temAtualizacao = (s?.commits_atras ?? 0) > 0;
  const rodando = atualizar.isPending || reiniciando;

  return (
    <div className="space-y-4">
      <Panel
        title="Atualizar Aether"
        icon={<RefreshCw size={15} />}
        hint="Busca a versão mais recente na branch main e reinicia o serviço."
      >
        {!s?.gerenciavel ? (
          <div className="flex items-start gap-3 rounded-xl border border-border bg-surface-2 p-4">
            <AlertTriangle size={18} className="mt-0.5 shrink-0 text-warn" />
            <div className="min-w-0 text-[13px] text-muted">
              <p className="text-text">Esta instalação não pode se atualizar sozinha.</p>
              <p className="mt-1">{s?.motivo}</p>
            </div>
          </div>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <GitCommitHorizontal size={15} className="text-muted" />
                  <code className="text-accent">{s.commit_curto}</code>
                  <span className="text-muted">na branch {s.branch}</span>
                  {temAtualizacao ? (
                    <Badge tone="orange">
                      {s.commits_atras} atualizaç{s.commits_atras === 1 ? "ão" : "ões"} disponíve
                      {s.commits_atras === 1 ? "l" : "is"}
                    </Badge>
                  ) : (
                    <Badge tone="green">atualizado</Badge>
                  )}
                </div>
                <p className="mt-1 truncate text-[12px] text-muted" title={s.assunto}>
                  {s.assunto}
                </p>
              </div>
              <Button
                variant="primary"
                disabled={rodando || s.alteracoes_locais.length > 0}
                onClick={async () => {
                  const ok = await dialog.confirm({
                    title: "Atualizar o Aether",
                    message:
                      "O código será atualizado para a versão mais recente da main, as " +
                      "dependências reinstaladas e o serviço reiniciado.\n\n" +
                      "O banco de dados é copiado antes, e os servidores em container " +
                      "continuam rodando — só o painel fica alguns segundos fora do ar.",
                    confirmText: "Atualizar agora",
                  });
                  if (ok) atualizar.mutate();
                }}
              >
                <RefreshCw size={14} className={rodando ? "animate-spin" : ""} />
                {rodando ? "Atualizando…" : temAtualizacao ? "Atualizar agora" : "Verificar e atualizar"}
              </Button>
            </div>

            {s.alteracoes_locais.length > 0 && (
              <div className="mt-3 flex items-start gap-3 rounded-xl border border-warn/50 bg-warn/10 p-4">
                <AlertTriangle size={18} className="mt-0.5 shrink-0 text-warn" />
                <div className="min-w-0 text-[13px]">
                  <p className="font-semibold">Há alterações locais no servidor</p>
                  <p className="mt-0.5 text-muted">
                    Atualizar sobrescreveria este trabalho, então a ação está bloqueada.
                    Resolva no servidor antes de continuar.
                  </p>
                  <ul className="mt-2 space-y-0.5 font-mono text-[11px] text-muted">
                    {s.alteracoes_locais.slice(0, 10).map((arquivo) => (
                      <li key={arquivo}>{arquivo}</li>
                    ))}
                  </ul>
                </div>
              </div>
            )}
          </>
        )}

        {erro && <p className="mt-3 text-xs text-danger">{erro}</p>}
      </Panel>

      {(linhas.length > 0 || rodando) && (
        <Panel title={etapa || "Progresso"} icon={<CheckCircle2 size={15} />} bodyClassName="p-0">
          <div className="max-h-72 overflow-y-auto bg-surface-2 p-3 font-mono text-[11px] leading-relaxed">
            {linhas.map((linha, i) => (
              <div key={i} className={linha.startsWith("—") ? "text-accent" : "text-muted"}>
                {linha}
              </div>
            ))}
            <div ref={fim} />
          </div>
        </Panel>
      )}
    </div>
  );
}
