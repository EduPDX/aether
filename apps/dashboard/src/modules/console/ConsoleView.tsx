import { FitAddon } from "@xterm/addon-fit";
import { Terminal } from "@xterm/xterm";
import "@xterm/xterm/css/xterm.css";
import { useQuery } from "@tanstack/react-query";
import { Activity, Cpu, MemoryStick, SendHorizontal, TerminalSquare } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button, Input, Panel, StatTile } from "../../components/ui";
import type { Instance } from "../../lib/api";
import { api, formatBytes } from "../../lib/api";
import { subscribeTopic } from "../../lib/ws";

const STATE_LABEL: Record<string, string> = {
  running: "Online",
  stopped: "Parado",
  starting: "Iniciando",
  stopping: "Parando",
  crashed: "Crashou",
};

const LEVEL_COLORS: Record<string, string> = {
  ERROR: "\x1b[31m",
  FATAL: "\x1b[31m",
  WARN: "\x1b[33m",
  INFO: "\x1b[0m",
  DEBUG: "\x1b[90m",
  CMD: "\x1b[36m",
};

function paint(line: string, level: string): string {
  const color = LEVEL_COLORS[level] ?? "\x1b[0m";
  return `${color}${line}\x1b[0m`;
}

export function ConsoleView({ instance }: { instance: Instance }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);
  const [command, setCommand] = useState("");
  const historyRef = useRef<string[]>([]);
  const historyIdx = useRef(-1);

  const metrics = useQuery({ queryKey: ["metrics"], queryFn: api.metrics, refetchInterval: 5000 });
  const proc = metrics.data?.instances.find((i) => i.instance_id === instance.id);

  useEffect(() => {
    // O terminal segue o tema do app em vez de cores fixas: trocar de tema
    // deixava o console destoando do resto da interface.
    const css = getComputedStyle(document.documentElement);
    const token = (name: string, fallback: string) =>
      css.getPropertyValue(`--color-${name}`).trim() || fallback;

    const term = new Terminal({
      convertEol: true,
      disableStdin: true,
      fontSize: 12.5,
      fontFamily: "Cascadia Mono, Consolas, monospace",
      scrollback: 3000,
      lineHeight: 1.25,
      letterSpacing: 0.2,
      cursorBlink: false,
      theme: {
        background: token("bg", "#0e1013"),
        foreground: token("text", "#d6dae2"),
        selectionBackground: token("surface-3", "#334155") + "99",
        red: token("danger", "#ff5c7a"),
        brightRed: token("danger", "#ff5c7a"),
        yellow: token("warn", "#ffc63d"),
        brightYellow: token("warn", "#ffc63d"),
        cyan: token("info", "#4cc9f0"),
        brightCyan: token("info", "#4cc9f0"),
        green: token("accent", "#22e39b"),
        brightGreen: token("accent", "#22e39b"),
        brightBlack: token("muted", "#94accd"),
      },
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(containerRef.current!);
    fit.fit();
    termRef.current = term;

    const onResize = () => fit.fit();
    window.addEventListener("resize", onResize);
    // O terminal agora fica dentro de um painel flex: a janela pode não mudar
    // de tamanho mas o contêiner sim (abrir/fechar sidebar, painel de status).
    const observer = new ResizeObserver(onResize);
    observer.observe(containerRef.current!);

    api.logs(instance.id).then(({ lines }) => {
      for (const line of lines) term.writeln(line);
    });

    const unsubscribe = subscribeTopic(`instance.${instance.id}.console`, (msg) => {
      term.writeln(paint(String(msg.payload.line ?? ""), String(msg.payload.level ?? "")));
    });

    return () => {
      unsubscribe();
      observer.disconnect();
      window.removeEventListener("resize", onResize);
      term.dispose();
      termRef.current = null;
    };
  }, [instance.id]);

  async function send() {
    const cmd = command.trim();
    if (!cmd) return;
    historyRef.current.push(cmd);
    historyIdx.current = -1;
    setCommand("");
    try {
      await api.command(instance.id, cmd);
    } catch (e) {
      termRef.current?.writeln(`\x1b[31m${String(e)}\x1b[0m`);
    }
  }

  function onKeyDown(e: React.KeyboardEvent) {
    const hist = historyRef.current;
    if (e.key === "Enter") send();
    else if (e.key === "ArrowUp" && hist.length > 0) {
      e.preventDefault();
      historyIdx.current =
        historyIdx.current === -1
          ? hist.length - 1
          : Math.max(0, historyIdx.current - 1);
      setCommand(hist[historyIdx.current]);
    } else if (e.key === "ArrowDown" && historyIdx.current !== -1) {
      e.preventDefault();
      historyIdx.current += 1;
      if (historyIdx.current >= hist.length) {
        historyIdx.current = -1;
        setCommand("");
      } else {
        setCommand(hist[historyIdx.current]);
      }
    }
  }

  const rodando = proc?.running ?? instance.state === "running";

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <div className="grid grid-cols-3 gap-3">
        <StatTile
          icon={<Activity size={14} />}
          label="Estado"
          value={STATE_LABEL[instance.state] ?? instance.state}
          sub={proc?.pid ? `PID ${proc.pid}` : "sem processo ativo"}
          tone={
            instance.state === "running" ? "accent" : instance.state === "crashed" ? "danger" : undefined
          }
        />
        <StatTile
          icon={<Cpu size={14} />}
          label="CPU"
          value={rodando ? `${(proc?.cpu_percent ?? 0).toFixed(0)}%` : "—"}
          sub="processo do servidor"
        />
        <StatTile
          icon={<MemoryStick size={14} />}
          label="Memória"
          value={rodando ? formatBytes(proc?.mem_bytes ?? 0) : "—"}
          sub="incluindo subprocessos"
        />
      </div>

      {/* min-h-0 em toda a cadeia: sem isso o xterm empurra o layout e some o input. */}
      <Panel
        title="Console"
        icon={<TerminalSquare size={15} />}
        hint="saída ao vivo do servidor"
        className="flex min-h-0 flex-1 flex-col"
        bodyClassName="flex min-h-0 flex-1 flex-col gap-2 px-4 pb-4"
      >
        <div
          ref={containerRef}
          className="min-h-0 flex-1 overflow-hidden rounded-lg border border-border bg-bg p-2"
        />
        <div className="flex gap-2">
          <Input
            className="flex-1 font-mono text-xs"
            placeholder="Comando do servidor (Enter para enviar, ↑↓ histórico)"
            value={command}
            onChange={(e) => setCommand(e.target.value)}
            onKeyDown={onKeyDown}
          />
          <Button variant="primary" onClick={send} disabled={!command.trim()}>
            <SendHorizontal size={14} />
          </Button>
        </div>
      </Panel>
    </div>
  );
}
