import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Play, RotateCw, Skull, Square } from "lucide-react";
import { useEffect, useState } from "react";
import { Badge, Button } from "../../components/ui";
import type { Instance, InstanceState } from "../../lib/api";
import { api, can } from "../../lib/api";
import { subscribeTopic } from "../../lib/ws";
import { useAuth } from "../auth/AuthGate";
import { ConfigView } from "../config/ConfigView";
import { ConsoleView } from "../console/ConsoleView";
import { ContentView } from "../content/ContentView";
import { FilesView } from "../files/FilesView";
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

type Tab = "content" | "console" | "files" | "config" | "sync";

export function InstanceView({ instance }: { instance: Instance }) {
  const qc = useQueryClient();
  const { user } = useAuth();
  const [tab, setTab] = useState<Tab>("content");
  const [errorMsg, setErrorMsg] = useState("");

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
              onClick={() => {
                if (confirm("Matar o processo imediatamente? O mundo pode não ser salvo."))
                  power.mutate("kill");
              }}
            >
              <Skull size={14} /> Matar
            </Button>
          </>
        )}
        {errorMsg && <span className="text-xs text-danger">{errorMsg}</span>}

        <div className="ml-auto flex rounded-md border border-border p-0.5">
          {(
            [
              ["content", "Conteúdo"],
              ["console", "Console"],
              ...(can(user, "files.read") ? [["files", "Arquivos"] as [Tab, string]] : []),
              ...(can(user, "config.read") ? [["config", "Config"] as [Tab, string]] : []),
              ...(can(user, "sync.read") ? [["sync", "Sync"] as [Tab, string]] : []),
            ] as [Tab, string][]
          ).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`cursor-pointer rounded px-3 py-1 text-xs font-medium transition-colors ${
                tab === key ? "bg-surface-3 text-text" : "text-muted hover:text-text"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="min-h-0 flex-1">
        {tab === "content" && <ContentView instance={instance} />}
        {tab === "console" && <ConsoleView instance={instance} />}
        {tab === "files" && <FilesView instance={instance} />}
        {tab === "config" && <ConfigView instance={instance} />}
        {tab === "sync" && <SyncView instance={instance} />}
      </div>
    </div>
  );
}
