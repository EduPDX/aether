import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Archive,
  ArrowLeftRight,
  FolderOpen,
  HardDriveDownload,
  Laptop,
  Package,
  Play,
  CalendarClock,
  RefreshCcwDot,
  RotateCw,
  Skull,
  SlidersHorizontal,
  Square,
  Store,
  TerminalSquare,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useDialog } from "../../components/Dialog";
import { Badge, Button } from "../../components/ui";
import type { Instance, InstanceState } from "../../lib/api";
import { api, can } from "../../lib/api";
import { useProvider } from "../../lib/providers";
import { subscribeTopic } from "../../lib/ws";
import { useAuth } from "../auth/AuthGate";
import { BackupsView } from "../backups/BackupsView";
import { ConfigView } from "../config/ConfigView";
import { ConsoleView } from "../console/ConsoleView";
import { ContentView } from "../content/ContentView";
import { ServerClientDiff } from "../content/ServerClientDiff";
import { CatalogView } from "../sources/CatalogView";
import { TasksView } from "../tasks/TasksView";
import { FilesView } from "../files/FilesView";
import { VersionView } from "./VersionView";
import { SyncView } from "../sync/SyncView";

const STATE_LABEL: Record<InstanceState, string> = {
  stopped: "parado",
  starting: "iniciando…",
  running: "online",
  stopping: "parando…",
  crashed: "crashou",
};

const STATE_TONE: Record<InstanceState, "neutral" | "green" | "orange" | "red"> = {
  stopped: "neutral",
  starting: "orange",
  running: "green",
  stopping: "orange",
  crashed: "red",
};

type Aba = [Tab, string, React.ReactNode];

type Tab =
  | "content"
  | "client"
  | "diff"
  | "catalog"
  | "console"
  | "files"
  | "config"
  | "sync"
  | "backups"
  | "version"
  | "tasks";

export function InstanceView({ instance }: { instance: Instance }) {
  const qc = useQueryClient();
  const { user } = useAuth();
  const dialog = useDialog();
  const [tab, setTab] = useState<Tab>("content");
  const [errorMsg, setErrorMsg] = useState("");
  // As abas seguem o que o provider da instância sabe fazer — nada aqui
  // conhece um jogo específico.
  const provider = useProvider(instance.provider_id);
  const caps = provider?.capabilities;
  const tipoServidor = provider?.content_types.find((t) => t.id === "mod");
  const temCliente = provider?.content_types.some((t) => t.id === "mod_client") ?? false;

  const statusQuery = useQuery({
    queryKey: ["status", instance.id],
    queryFn: () => api.status(instance.id),
  });
  const state: InstanceState = statusQuery.data?.state ?? instance.state ?? "stopped";

  useEffect(() => {
    return subscribeTopic(`instance.${instance.id}.state`, () => {
      qc.invalidateQueries({ queryKey: ["status", instance.id] });
      qc.invalidateQueries({ queryKey: ["instances"] });
    });
  }, [instance.id, qc]);

  const power = useMutation({
    mutationFn: (action: "start" | "stop" | "restart" | "kill") =>
      api.power(instance.id, action),
    onMutate: () => setErrorMsg(""),
    onError: (e) => setErrorMsg(String(e)),
    onSettled: () => qc.invalidateQueries({ queryKey: ["status", instance.id] }),
  });

  const busy = power.isPending || state === "starting" || state === "stopping";
  const online = state === "running" || state === "starting";

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-2">
        <Badge tone={STATE_TONE[state]}>{STATE_LABEL[state]}</Badge>
        {instance.runtime === "docker" && (
          <Badge tone="neutral" title="Roda isolado num container Docker">
            container
          </Badge>
        )}

        {!online ? (
          <Button variant="primary" disabled={busy} onClick={() => power.mutate("start")}>
            <Play size={14} /> Iniciar
          </Button>
        ) : (
          <>
            <Button disabled={busy} onClick={() => power.mutate("stop")}>
              <Square size={14} /> Parar
            </Button>
            <Button disabled={busy} onClick={() => power.mutate("restart")}>
              <RotateCw size={14} /> Reiniciar
            </Button>
            <Button
              variant="danger"
              disabled={power.isPending}
              onClick={async () => {
                const ok = await dialog.confirm({
                  title: "Matar o servidor",
                  message:
                    "O servidor é encerrado na força, sem salvar. O que não tiver sido gravado no mundo se perde.",
                  confirmText: "Matar mesmo assim",
                  tone: "danger",
                });
                if (ok) power.mutate("kill");
              }}
            >
              <Skull size={14} /> Matar
            </Button>
          </>
        )}
        {errorMsg && <span className="text-xs text-danger">{errorMsg}</span>}

      </div>

      {/* Abas da instância: ícone + rótulo, com alvo de clique confortável. */}
      <div className="flex flex-wrap gap-1 border-b border-border px-3 py-1.5">
        {(
          [
            ...(tipoServidor
              ? [["content", tipoServidor.label, <Package size={16} />] as Aba]
              : []),
            ...(can(user, "content.read") && temCliente
              ? ([
                  [
                    "client",
                    provider?.content_types.find((t) => t.id === "mod_client")?.label ??
                      "Cliente",
                    <Laptop size={16} />,
                  ],
                  ["diff", "Servidor × Cliente", <ArrowLeftRight size={16} />],
                ] as Aba[])
              : []),
            ...(can(user, "content.read") && caps?.sources
              ? [["catalog", "Catálogo", <Store size={16} />] as Aba]
              : []),
            ["console", "Console", <TerminalSquare size={16} />],
            ...(can(user, "files.read")
              ? [["files", "Arquivos", <FolderOpen size={16} />] as Aba]
              : []),
            ...(can(user, "config.read") && caps?.config
              ? [["config", "Config", <SlidersHorizontal size={16} />] as Aba]
              : []),
            ...(can(user, "sync.read") && caps?.game_metadata
              ? [["sync", "Sync", <RefreshCcwDot size={16} />] as Aba]
              : []),
            ...(can(user, "backups.read") && caps?.backup
              ? [["backups", "Backups", <Archive size={16} />] as Aba]
              : []),
            ...(can(user, "power.use")
              ? [["tasks", "Agendamentos", <CalendarClock size={16} />] as Aba]
              : []),
            // Só para jogos cujo servidor o painel instala e atualiza.
            ...(can(user, "instances.write") && caps?.install
              ? [["version", "Versão", <HardDriveDownload size={16} />] as Aba]
              : []),
          ] as Aba[]
        ).map(([key, label, icone]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
              tab === key
                ? "bg-surface-3 text-text"
                : "text-muted hover:bg-surface-2 hover:text-text"
            }`}
          >
            {icone}
            {label}
          </button>
        ))}
      </div>

      <div className="min-h-0 flex-1">
        {tab === "content" && <ContentView instance={instance} contentType="mod" />}
        {tab === "client" && (
          <ContentView instance={instance} contentType="mod_client" />
        )}
        {tab === "diff" && <ServerClientDiff instance={instance} />}
        {tab === "catalog" && <CatalogView instance={instance} />}
        {tab === "console" && <ConsoleView instance={instance} />}
        {tab === "files" && <FilesView instance={instance} />}
        {tab === "config" && <ConfigView instance={instance} />}
        {tab === "sync" && <SyncView instance={instance} />}
        {tab === "backups" && <BackupsView instance={instance} />}
        {tab === "tasks" && <TasksView instance={instance} />}
        {tab === "version" && <VersionView instance={instance} />}
      </div>
    </div>
  );
}
