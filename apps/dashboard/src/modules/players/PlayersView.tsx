import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Ban,
  LogOut,
  ShieldCheck,
  UserPlus,
  UserX,
} from "lucide-react";
import { useState } from "react";
import { Badge, Button, Panel, Spinner } from "../../components/ui";
import { useDialog } from "../../components/Dialog";
import type { Instance, PlayerAction, PlayerEntry, PlayerList } from "../../lib/api";
import { api } from "../../lib/api";

const ICONE = {
  allow: <ShieldCheck size={15} />,
  admin: <ShieldCheck size={15} />,
  banned: <Ban size={15} />,
} as const;

/** O que o botão "adicionar" de cada lista faz. */
const ADICIONAR: Record<PlayerList["kind"], { action: PlayerAction; rotulo: string }> = {
  allow: { action: "allow_add", rotulo: "Liberar jogador" },
  admin: { action: "admin_add", rotulo: "Tornar operador" },
  banned: { action: "ban", rotulo: "Banir jogador" },
};

const REMOVER: Record<PlayerList["kind"], { action: PlayerAction; titulo: string }> = {
  allow: { action: "allow_remove", titulo: "Remover da whitelist" },
  admin: { action: "admin_remove", titulo: "Remover operador" },
  banned: { action: "unban", titulo: "Desbanir" },
};

export function PlayersView({ instance }: { instance: Instance }) {
  const qc = useQueryClient();
  const dialog = useDialog();
  const [erro, setErro] = useState("");
  const [aviso, setAviso] = useState("");

  const query = useQuery({
    queryKey: ["players", instance.id],
    queryFn: () => api.players(instance.id),
  });

  // Estado ao vivo, não o que veio na prop: se o servidor subir enquanto a tela
  // está aberta, o botão de expulsar precisa aparecer sem recarregar.
  const status = useQuery({
    queryKey: ["status", instance.id],
    queryFn: () => api.status(instance.id),
  });
  const rodando = (status.data?.state ?? instance.state) === "running";

  const agir = useMutation({
    mutationFn: (v: { action: PlayerAction; name: string; reason?: string }) =>
      api.playerAction(instance.id, v.action, v.name, v.reason ?? ""),
    onSuccess: (res) => {
      setErro("");
      // A diferença importa: por console vale agora; por arquivo, no próximo boot.
      setAviso(
        res.applied_via === "console"
          ? "Aplicado no servidor — já vale."
          : "Gravado no arquivo — vale quando o servidor iniciar.",
      );
      setTimeout(() => setAviso(""), 4000);
      qc.invalidateQueries({ queryKey: ["players", instance.id] });
    },
    onError: (e) => {
      setAviso("");
      setErro(String(e instanceof Error ? e.message : e));
    },
  });

  async function adicionar(lista: PlayerList) {
    const { action, rotulo } = ADICIONAR[lista.kind];
    const nome = await dialog.promptText({
      title: rotulo,
      input: { label: "Nome do jogador", placeholder: "ex.: EduPDX" },
      confirmText: "Confirmar",
    });
    if (!nome) return;

    let motivo = "";
    if (action === "ban") {
      motivo =
        (await dialog.promptText({
          title: "Motivo do banimento",
          input: { label: "Motivo (aparece para o jogador)", initialValue: "" },
          confirmText: "Banir",
        })) ?? "";
    }
    agir.mutate({ action, name: nome, reason: motivo });
  }

  async function remover(lista: PlayerList, entry: PlayerEntry) {
    const { action, titulo } = REMOVER[lista.kind];
    const ok = await dialog.confirm({
      title: titulo,
      message: `“${entry.name}”`,
      confirmText: "Confirmar",
      tone: lista.kind === "banned" ? "default" : "danger",
    });
    if (ok) agir.mutate({ action, name: entry.name });
  }

  async function expulsar(entry: PlayerEntry) {
    const motivo = await dialog.promptText({
      title: `Expulsar ${entry.name}`,
      input: { label: "Motivo (opcional)", initialValue: "" },
      confirmText: "Expulsar",
    });
    if (motivo !== null) agir.mutate({ action: "kick", name: entry.name, reason: motivo });
  }

  if (query.isLoading) return <Spinner />;
  const listas = query.data?.lists ?? [];
  if (listas.length === 0)
    return (
      <div className="p-6 text-sm text-muted">
        Este provider não gerencia jogadores.
      </div>
    );

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <div className="sticky top-0 z-10 flex items-center gap-3 border-b border-border bg-bg px-4 py-2">
        <span className="text-sm font-semibold">Jogadores</span>
        <Badge tone={rodando ? "green" : "neutral"}>
          {rodando ? "servidor no ar" : "servidor parado"}
        </Badge>
        {aviso && <span className="text-xs text-muted">{aviso}</span>}
        {erro && <span className="text-xs text-danger">{erro}</span>}
      </div>

      <div className="mx-auto w-full max-w-4xl space-y-4 p-4">
        {!rodando && (
          <p className="rounded-lg border border-border bg-surface-2 px-3 py-2 text-xs text-muted">
            Com o servidor parado as mudanças são gravadas nos arquivos e passam a
            valer no próximo início. Expulsar só funciona com o servidor no ar.
          </p>
        )}

        {listas.map((lista) => (
          <Panel
            key={lista.kind}
            title={lista.label}
            icon={ICONE[lista.kind]}
            hint={`${lista.entries.length} jogador(es)`}
            bodyClassName="px-0 pb-0"
            aside={
              <Button variant="ghost" onClick={() => adicionar(lista)} disabled={agir.isPending}>
                <UserPlus size={13} /> Adicionar
              </Button>
            }
          >
            {/* A whitelist desligada é o caso que engana: a lista está cheia e
                o servidor ignora tudo. */}
            {lista.kind === "allow" && !lista.enforced && (
              <div className="flex items-start gap-2.5 border-t border-warn/40 bg-warn/10 px-4 py-2.5 text-xs">
                <AlertTriangle size={15} className="mt-0.5 shrink-0 text-warn" />
                <span>
                  A whitelist está <strong>desligada</strong> (<code>white-list=false</code>).
                  Qualquer um entra, mesmo com esta lista preenchida. Ligue em Config.
                </span>
              </div>
            )}

            <div className="divide-y divide-border border-t border-border">
              {lista.entries.length === 0 ? (
                <p className="px-4 py-6 text-center text-xs text-muted">Ninguém aqui.</p>
              ) : (
                lista.entries.map((entry) => (
                  <div key={entry.id || entry.name} className="flex items-center gap-3 px-4 py-2">
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm">{entry.name}</div>
                      {entry.detail && (
                        <div className="truncate text-[11px] text-muted">{entry.detail}</div>
                      )}
                    </div>
                    <span className="flex shrink-0 gap-1">
                      {rodando && lista.kind !== "banned" && (
                        <Button
                          variant="ghost"
                          title="Expulsar agora"
                          onClick={() => expulsar(entry)}
                          disabled={agir.isPending}
                        >
                          <LogOut size={13} />
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        title={REMOVER[lista.kind].titulo}
                        onClick={() => remover(lista, entry)}
                        disabled={agir.isPending}
                      >
                        <UserX size={13} />
                      </Button>
                    </span>
                  </div>
                ))
              )}
            </div>
          </Panel>
        ))}
      </div>
    </div>
  );
}
