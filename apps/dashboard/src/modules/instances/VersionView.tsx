import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowUpCircle,
  HardDriveDownload,
  Info,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useDialog } from "../../components/Dialog";
import { Badge, Button, Panel, Select, Spinner } from "../../components/ui";
import type { Instance } from "../../lib/api";
import { api } from "../../lib/api";
import { subscribeTopic } from "../../lib/ws";

const gb = (bytes: number) => `${(bytes / 1024 ** 3).toFixed(1)} GB`;

/**
 * Versão do servidor: o que está instalado e como trocar.
 *
 * A atualização cria um backup antes de tocar em qualquer arquivo — o diálogo
 * diz isso com todas as letras, porque atualizar servidor de jogo é a operação
 * com maior potencial de estrago do painel.
 */
export function VersionView({ instance }: { instance: Instance }) {
  const qc = useQueryClient();
  const dialog = useDialog();
  const [alvo, setAlvo] = useState("");
  const [erro, setErro] = useState("");
  const [progresso, setProgresso] = useState("");

  const versao = useQuery({
    queryKey: ["version", instance.id],
    queryFn: () => api.instanceVersion(instance.id),
  });
  const disponiveis = useQuery({
    queryKey: ["versions", instance.provider_id],
    queryFn: () => api.providerVersions(instance.provider_id),
    staleTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    return subscribeTopic(`instance.${instance.id}.job`, (msg) => {
      const p = msg.payload as { status?: string; version?: string; erro?: string };
      if (p.status === "started") setProgresso(`instalando ${p.version}…`);
      if (p.status === "done") {
        setProgresso("");
        qc.invalidateQueries({ queryKey: ["version", instance.id] });
        qc.invalidateQueries({ queryKey: ["config", instance.id] });
      }
      if (p.status === "error") {
        setProgresso("");
        setErro(String(p.erro ?? "falhou"));
      }
    });
  }, [instance.id, qc]);

  const instalar = useMutation({
    mutationFn: (version: string) => api.installVersion(instance.id, version),
    onMutate: () => setErro(""),
    onError: (e) => setErro(String(e instanceof Error ? e.message : e)),
  });

  if (versao.isLoading) return <Spinner />;
  if (versao.isError)
    return (
      <div className="p-6 text-sm text-muted">
        Este jogo não gerencia versões pelo painel. ({String(versao.error)})
      </div>
    );

  const instalada = versao.data?.installed ?? "";
  const rodando = Boolean(versao.data?.installing) || Boolean(progresso) || instalar.isPending;
  const opcoes = disponiveis.data ?? [];
  const escolhida = alvo || opcoes.find((v) => v.stable)?.id || "";
  const primeira = !instalada;
  const falhaAnterior = versao.data?.error ?? "";
  const livre = versao.data?.disk_free ?? 0;
  const precisa = versao.data?.disk_required ?? 0;

  return (
    <div className="mx-auto w-full max-w-3xl space-y-4 overflow-y-auto p-4">
      <Panel
        title="Versão do servidor"
        icon={<HardDriveDownload size={15} />}
        hint="Os arquivos do jogo são baixados no volume da instância."
      >
        <div className="flex flex-wrap items-center gap-3">
          <div className="min-w-0 flex-1">
            <div className="text-sm">
              {primeira ? (
                <span className="text-muted">Servidor ainda não instalado.</span>
              ) : (
                <>
                  Instalada: <code className="text-accent">build {instalada}</code>
                </>
              )}
            </div>
            {rodando && (
              <div className="mt-1 text-[11px] text-warn">
                {progresso || "instalando…"} — acompanhe o progresso na aba Console.
              </div>
            )}
          </div>
          <Select
            value={escolhida}
            disabled={rodando || opcoes.length === 0}
            onChange={(e) => setAlvo(e.target.value)}
          >
            {opcoes.length === 0 && <option value="">(não foi possível listar as versões)</option>}
            {opcoes
              .filter((v) => v.stable)
              .map((v) => (
                <option key={v.id} value={v.id}>
                  {v.label}
                  {v.description ? ` — ${v.description}` : ""}
                </option>
              ))}
            {opcoes.some((v) => !v.stable) && (
              <optgroup label="Instáveis (podem quebrar o servidor)">
                {opcoes
                  .filter((v) => !v.stable)
                  .map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.label}
                      {v.description ? ` — ${v.description}` : ""}
                    </option>
                  ))}
              </optgroup>
            )}
          </Select>
          <Button
            variant="primary"
            disabled={rodando || !escolhida}
            onClick={async () => {
              if (!primeira) {
                const ok = await dialog.confirm({
                  title: `Atualizar para ${escolhida}`,
                  message:
                    "Um backup é criado automaticamente antes de qualquer arquivo ser tocado — " +
                    "se ele falhar, a atualização é cancelada.\n\n" +
                    "Saves, mundos, configuração e dados dos jogadores são preservados. " +
                    "A versão nova pode trazer configurações novas, que serão acrescentadas ao " +
                    "seu serverconfig.xml sem apagar o que você já ajustou.",
                  confirmText: "Fazer backup e atualizar",
                });
                if (!ok) return;
              }
              instalar.mutate(escolhida);
            }}
          >
            <ArrowUpCircle size={14} /> {primeira ? "Instalar" : "Atualizar"}
          </Button>
        </div>
        {erro && <p className="mt-2 text-xs text-danger">{erro}</p>}
      </Panel>

      {/* Instalação que falhou não pode ficar só no log: sem isto o usuário só
          descobre ao dar play, com um erro que não explica nada. */}
      {!rodando && falhaAnterior && (
        <div className="flex items-start gap-3 rounded-xl border border-danger/40 bg-danger/10 p-4 text-[13px]">
          <AlertTriangle size={18} className="mt-0.5 shrink-0 text-danger" />
          <div className="space-y-1">
            <p className="font-medium text-danger">A última instalação não terminou.</p>
            <p className="text-muted">{falhaAnterior}</p>
            <p className="text-muted">
              O servidor não vai iniciar enquanto os arquivos do jogo não estiverem completos.
              Resolva o motivo acima e instale de novo.
            </p>
          </div>
        </div>
      )}

      {precisa > 0 && (
        <p className="text-[12px] leading-relaxed text-muted">
          Espaço em disco:{" "}
          <b className={livre < precisa ? "text-danger" : "text-text"}>{gb(livre)} livres</b> — esta
          instalação precisa de {gb(precisa)}. O instalador baixa os arquivos numa pasta de trabalho
          antes de gravar os definitivos, então chega a ocupar o dobro do tamanho final.
        </p>
      )}

      <div className="flex items-start gap-3 rounded-xl border border-border bg-surface-2 p-4 text-[13px] text-muted">
        <ShieldCheck size={18} className="mt-0.5 shrink-0 text-accent" />
        <div className="space-y-1">
          <p>
            <b className="text-text">O que a atualização preserva:</b> saves, mundos, configuração
            e dados dos jogadores. Só os arquivos do jogo são substituídos.
          </p>
          <p className="flex items-start gap-1.5">
            <Info size={13} className="mt-0.5 shrink-0" />
            Versões novas costumam adicionar opções de servidor. As que aparecerem entram no seu
            arquivo de configuração com o padrão do jogo, e o que você já tinha ajustado continua
            como estava.
          </p>
        </div>
      </div>

      {instance.state !== "stopped" && (
        <p className="text-xs text-warn">
          <Badge tone="orange">servidor no ar</Badge> Pare o servidor para instalar ou atualizar.
        </p>
      )}
    </div>
  );
}
