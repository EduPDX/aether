import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowUpCircle, HardDriveDownload, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { useDialog } from "../../components/Dialog";
import { Badge, Button, Panel, Select, Spinner } from "../../components/ui";
import type { Instance } from "../../lib/api";
import { api } from "../../lib/api";

/**
 * Versão do Minecraft: mostra a atual e troca para outra.
 *
 * Diferente do 7 Days (que roda um instalador), aqui a versão é a env do
 * container itzg: trocar grava no provider_data e vale na próxima subida, quando
 * o itzg baixa a versão nova. Por isso é imediato, sem barra de progresso.
 *
 * O aviso de mods é o coração da tela: num servidor com loader, trocar a versão
 * quebra todos os mods, que são presos à versão.
 */
export function MinecraftVersionView({ instance }: { instance: Instance }) {
  const qc = useQueryClient();
  const dialog = useDialog();
  const [alvo, setAlvo] = useState("");
  const [erro, setErro] = useState("");
  const [ok, setOk] = useState("");

  const estado = useQuery({
    queryKey: ["game-version", instance.id],
    queryFn: () => api.gameVersion(instance.id),
  });

  const trocar = useMutation({
    mutationFn: (version: string) => api.setGameVersion(instance.id, version),
    onSuccess: (res) => {
      setErro("");
      setOk(
        `Versão fixada em ${res.version}` +
          (res.backed_up ? " (backup criado)" : "") +
          ". O download acontece quando você iniciar o servidor.",
      );
      setAlvo("");
      qc.invalidateQueries({ queryKey: ["game-version", instance.id] });
      qc.invalidateQueries({ queryKey: ["instances"] });
    },
    onError: (e) => {
      setOk("");
      setErro(String(e instanceof Error ? e.message : e));
    },
  });

  if (estado.isLoading) return <Spinner />;
  if (estado.isError)
    return (
      <div className="p-6 text-sm text-muted">
        Este jogo não troca de versão pelo painel. ({String(estado.error)})
      </div>
    );

  const dados = estado.data!;
  const estaveis = dados.available.filter((v) => v.stable);
  const snapshots = dados.available.filter((v) => !v.stable);
  const escolhida = alvo || dados.current;
  const mudou = Boolean(escolhida) && escolhida !== dados.current;

  return (
    <div className="mx-auto w-full max-w-3xl space-y-4 overflow-y-auto p-4">
      <Panel
        title="Versão do Minecraft"
        icon={<HardDriveDownload size={15} />}
        hint="A versão nova é baixada quando o servidor inicia."
      >
        <div className="flex flex-wrap items-center gap-3">
          <div className="min-w-0 flex-1 text-sm">
            {dados.current ? (
              <>
                Versão atual: <code className="text-accent">{dados.current}</code>
              </>
            ) : (
              <span className="text-muted">Versão ainda não definida.</span>
            )}
          </div>
          <Select
            value={escolhida}
            disabled={dados.running || dados.available.length === 0}
            onChange={(e) => setAlvo(e.target.value)}
          >
            {dados.available.length === 0 && (
              <option value="">(não foi possível listar as versões)</option>
            )}
            {estaveis.map((v) => (
              <option key={v.id} value={v.id}>
                {v.label}
              </option>
            ))}
            {snapshots.length > 0 && (
              <optgroup label="Snapshots (instáveis)">
                {snapshots.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.label}
                  </option>
                ))}
              </optgroup>
            )}
          </Select>
          <Button
            variant="primary"
            disabled={dados.running || !mudou || trocar.isPending}
            onClick={async () => {
              const confirmado = await dialog.confirm({
                title: `Trocar para ${escolhida}`,
                message: dados.modded
                  ? "ATENÇÃO: este servidor usa mods, e eles são presos à versão. " +
                    "Trocar a versão do Minecraft vai QUEBRAR todos os seus mods — o " +
                    "servidor não vai iniciar até você atualizar cada mod para a versão " +
                    "nova.\n\nUm backup é criado antes de qualquer mudança. Continuar?"
                  : "Um backup é criado antes de trocar. O mundo e a configuração são " +
                    "preservados; o Minecraft converte o mundo para a versão nova ao iniciar.\n\n" +
                    "Continuar?",
                confirmText: "Fazer backup e trocar",
                tone: dados.modded ? "danger" : "default",
              });
              if (confirmado) trocar.mutate(escolhida);
            }}
          >
            <ArrowUpCircle size={14} /> Trocar versão
          </Button>
        </div>
        {ok && <p className="mt-2 text-xs text-accent">{ok}</p>}
        {erro && <p className="mt-2 text-xs text-danger">{erro}</p>}
      </Panel>

      {dados.modded && (
        <div className="flex items-start gap-3 rounded-xl border border-danger/40 bg-danger/10 p-4 text-[13px]">
          <AlertTriangle size={18} className="mt-0.5 shrink-0 text-danger" />
          <div className="space-y-1">
            <p className="font-medium text-danger">Servidor com mods</p>
            <p className="text-muted">
              Os mods desta instância só funcionam na versão para a qual foram feitos.
              Ao trocar a versão do Minecraft, atualize também cada mod (na aba Mods ou
              pelo Catálogo) — senão o servidor crasha ao iniciar.
            </p>
          </div>
        </div>
      )}

      <div className="flex items-start gap-3 rounded-xl border border-border bg-surface-2 p-4 text-[13px] text-muted">
        <ShieldCheck size={18} className="mt-0.5 shrink-0 text-accent" />
        <p>
          <b className="text-text">O que a troca preserva:</b> mundo, configuração
          (server.properties) e dados dos jogadores. Só os arquivos do jogo mudam,
          baixados pela imagem ao iniciar.
        </p>
      </div>

      {dados.running && (
        <p className="text-xs text-warn">
          <Badge tone="orange">servidor no ar</Badge> Pare o servidor para trocar a versão.
        </p>
      )}
    </div>
  );
}
