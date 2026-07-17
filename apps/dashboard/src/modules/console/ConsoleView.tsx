import { FitAddon } from "@xterm/addon-fit";
import { Terminal } from "@xterm/xterm";
import "@xterm/xterm/css/xterm.css";
import { SendHorizontal } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button, Input } from "../../components/ui";
import type { Instance } from "../../lib/api";
import { api } from "../../lib/api";
import { subscribeTopic } from "../../lib/ws";

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

  useEffect(() => {
    const term = new Terminal({
      convertEol: true,
      disableStdin: true,
      fontSize: 12.5,
      fontFamily: "Cascadia Mono, Consolas, monospace",
      scrollback: 3000,
      theme: {
        background: "#0e1013",
        foreground: "#d6dae2",
        selectionBackground: "#33415588",
      },
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(containerRef.current!);
    fit.fit();
    termRef.current = term;

    const onResize = () => fit.fit();
    window.addEventListener("resize", onResize);

    api.logs(instance.id).then(({ lines }) => {
      for (const line of lines) term.writeln(line);
    });

    const unsubscribe = subscribeTopic(`instance.${instance.id}.console`, (msg) => {
      term.writeln(paint(String(msg.payload.line ?? ""), String(msg.payload.level ?? "")));
    });

    return () => {
      unsubscribe();
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

  return (
    <div className="flex h-full flex-col">
      <div ref={containerRef} className="min-h-0 flex-1 p-2" />
      <div className="flex gap-2 border-t border-border p-2">
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
    </div>
  );
}
