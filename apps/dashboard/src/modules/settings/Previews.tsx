import { Boxes, LayoutDashboard, Server, Settings } from "lucide-react";
import type { IconPack } from "../../lib/icons";
import type { Theme } from "../../lib/themes";
import { FileIcon, fileKind } from "../files/FileIcon";

/**
 * Miniatura da interface desenhada com os tokens de um tema *arbitrário*.
 *
 * Usa estilo inline em vez das CSS variables de propósito: assim a prévia
 * mostra um tema sem que ele precise estar aplicado na página.
 */
export function ThemePreview({ theme }: { theme: Theme }) {
  const t = theme.tokens;
  const barras = [0.95, 0.62, 0.78, 0.4, 0.55];

  return (
    <div
      className="overflow-hidden rounded-lg border text-[9px] select-none"
      style={{ background: t.bg, borderColor: t.border, color: t.text }}
    >
      <div className="flex" style={{ height: 190 }}>
        {/* barra lateral */}
        <div
          className="flex w-[74px] shrink-0 flex-col gap-0.5 p-1.5"
          style={{ background: t.surface, borderRight: `1px solid ${t.border}` }}
        >
          <div className="mb-1 flex items-center gap-1">
            <Boxes size={10} style={{ color: t.accent }} />
            <span className="font-bold" style={{ color: t.text }}>
              Aether
            </span>
          </div>
          {[
            { icon: <LayoutDashboard size={8} />, label: "Visão geral", active: true },
            { icon: <Server size={8} />, label: "Servidor", active: false },
            { icon: <Settings size={8} />, label: "Config", active: false },
          ].map((i) => (
            <div
              key={i.label}
              className="flex items-center gap-1 rounded px-1 py-[3px]"
              style={{
                background: i.active ? t.surface3 : "transparent",
                color: i.active ? t.text : t.muted,
              }}
            >
              {i.icon}
              <span className="truncate">{i.label}</span>
            </div>
          ))}
        </div>

        {/* conteúdo */}
        <div className="flex min-w-0 flex-1 flex-col gap-1.5 p-2">
          <div className="flex gap-1.5">
            {[
              { rotulo: "CPU", valor: "42%", cor: theme.chart[0] },
              { rotulo: "RAM", valor: "6.1 GB", cor: theme.chart[1] },
            ].map((s) => (
              <div
                key={s.rotulo}
                className="flex-1 rounded-md border p-1.5"
                style={{ background: t.surface, borderColor: t.border }}
              >
                <div style={{ color: t.muted }}>{s.rotulo}</div>
                <div className="text-[13px] font-bold" style={{ color: s.cor }}>
                  {s.valor}
                </div>
              </div>
            ))}
          </div>

          <div
            className="flex-1 rounded-md border p-1.5"
            style={{ background: t.surface, borderColor: t.border }}
          >
            <div className="mb-1 font-semibold">Mods por loader</div>
            <div className="flex h-[52px] items-end gap-1">
              {barras.map((h, i) => (
                <div
                  key={i}
                  className="flex-1 rounded-sm"
                  style={{
                    height: `${h * 100}%`,
                    background: theme.chart[i % theme.chart.length],
                  }}
                />
              ))}
            </div>
          </div>

          <div className="flex gap-1">
            {[
              { txt: "online", cor: t.accent },
              { txt: "aviso", cor: t.warn },
              { txt: "erro", cor: t.danger },
            ].map((b) => (
              <span
                key={b.txt}
                className="rounded px-1 py-[1px] font-semibold"
                style={{ background: `${b.cor}26`, color: b.cor }}
              >
                {b.txt}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

const AMOSTRA: { name: string; isDir: boolean; size: string }[] = [
  { name: "config", isDir: true, size: "—" },
  { name: "mods", isDir: true, size: "—" },
  { name: "world", isDir: true, size: "—" },
  { name: "sodium-1.20.1.jar", isDir: false, size: "412 KB" },
  { name: "server.properties", isDir: false, size: "1.2 KB" },
  { name: "latest.log", isDir: false, size: "88 KB" },
  { name: "pack.mcmeta", isDir: false, size: "204 B" },
  { name: "icon.png", isDir: false, size: "16 KB" },
  { name: "backup.zip", isDir: false, size: "2.4 GB" },
  { name: "run.sh", isDir: false, size: "310 B" },
];

/** Prévia do pacote de ícones nos dois modos do gerenciador de arquivos. */
export function IconPreview({ pack }: { pack: IconPack }) {
  return (
    <div className="grid gap-3 lg:grid-cols-2">
      <div>
        <div className="mb-1.5 text-[11px] text-muted">Ícones grandes</div>
        <div className="grid grid-cols-4 gap-1.5 rounded-lg border border-border bg-bg p-2">
          {AMOSTRA.slice(0, 8).map((f) => (
            <div
              key={f.name}
              className="flex flex-col items-center gap-1 rounded-md p-1.5 text-center"
            >
              <FileIcon name={f.name} isDir={f.isDir} size={34} pack={pack} />
              <span className="line-clamp-2 text-[9px] leading-tight break-words text-muted">
                {f.name}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div>
        <div className="mb-1.5 text-[11px] text-muted">Lista com detalhes</div>
        <div className="overflow-hidden rounded-lg border border-border bg-bg">
          <table className="w-full text-left text-[10px]">
            <thead className="bg-surface-2 text-muted">
              <tr>
                <th className="px-2 py-1 font-semibold">Nome</th>
                <th className="px-2 py-1 font-semibold">Tipo</th>
                <th className="px-2 py-1 text-right font-semibold">Tamanho</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {AMOSTRA.map((f) => (
                <tr key={f.name}>
                  <td className="px-2 py-[3px]">
                    <span className="flex items-center gap-1.5">
                      <FileIcon name={f.name} isDir={f.isDir} size={13} pack={pack} />
                      <span className="truncate">{f.name}</span>
                    </span>
                  </td>
                  <td className="px-2 py-[3px] text-muted">{fileKind(f.name, f.isDir)}</td>
                  <td className="px-2 py-[3px] text-right text-muted tabular-nums">{f.size}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
