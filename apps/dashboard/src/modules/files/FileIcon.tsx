import {
  FileArchive,
  FileAudio,
  FileCode,
  FileCog,
  FileImage,
  FileText,
  FileVideo,
  Folder,
  Package,
} from "lucide-react";
import { useSyncExternalStore } from "react";
import type { IconPack } from "../../lib/icons";
import { currentIconPack, subscribeIconPack } from "../../lib/icons";

const BY_EXT: Record<string, { Icon: typeof FileText; color: string }> = {
  jar: { Icon: Package, color: "text-warn" },
  zip: { Icon: FileArchive, color: "text-warn" },
  gz: { Icon: FileArchive, color: "text-warn" },
  tar: { Icon: FileArchive, color: "text-warn" },
  json: { Icon: FileCode, color: "text-info" },
  mcmeta: { Icon: FileCode, color: "text-info" },
  js: { Icon: FileCode, color: "text-info" },
  toml: { Icon: FileCog, color: "text-accent" },
  properties: { Icon: FileCog, color: "text-accent" },
  cfg: { Icon: FileCog, color: "text-accent" },
  conf: { Icon: FileCog, color: "text-accent" },
  yml: { Icon: FileCog, color: "text-accent" },
  yaml: { Icon: FileCog, color: "text-accent" },
  ini: { Icon: FileCog, color: "text-accent" },
  sh: { Icon: FileCode, color: "text-accent" },
  bat: { Icon: FileCode, color: "text-accent" },
  log: { Icon: FileText, color: "text-muted" },
  txt: { Icon: FileText, color: "text-muted" },
  md: { Icon: FileText, color: "text-muted" },
  png: { Icon: FileImage, color: "text-danger" },
  jpg: { Icon: FileImage, color: "text-danger" },
  jpeg: { Icon: FileImage, color: "text-danger" },
  gif: { Icon: FileImage, color: "text-danger" },
  ogg: { Icon: FileAudio, color: "text-danger" },
  wav: { Icon: FileAudio, color: "text-danger" },
  mp4: { Icon: FileVideo, color: "text-danger" },
};

/** Rótulo humano do tipo, para a coluna "Tipo". */
export function fileKind(name: string, isDir: boolean): string {
  if (isDir) return "Pasta";
  const ext = name.split(".").pop()?.toLowerCase() ?? "";
  const nomes: Record<string, string> = {
    jar: "Mod / Java",
    json: "JSON",
    toml: "Configuração",
    properties: "Configuração",
    cfg: "Configuração",
    yml: "Configuração",
    yaml: "Configuração",
    log: "Log",
    txt: "Texto",
    md: "Markdown",
    zip: "Compactado",
    png: "Imagem",
    jpg: "Imagem",
    sh: "Script",
    bat: "Script",
    disabled: "Desativado",
  };
  return nomes[ext] ?? (ext ? ext.toUpperCase() : "Arquivo");
}

function useIconPack() {
  return useSyncExternalStore(subscribeIconPack, currentIconPack);
}

export function FileIcon({
  name,
  isDir,
  size = 15,
  pack,
}: {
  name: string;
  isDir: boolean;
  size?: number;
  /** Força um pacote (usado nas prévias das configurações). */
  pack?: IconPack;
}) {
  const active = useIconPack();
  const chosen = pack ?? active;

  const ext = name.split(".").pop()?.toLowerCase() ?? "";
  const base = isDir
    ? { Icon: Folder, color: "text-info" }
    : (BY_EXT[ext] ?? { Icon: FileText, color: "text-muted" });
  const { Icon } = base;

  const color =
    chosen === "neutro" ? "text-muted" : chosen === "destaque" ? "text-accent" : base.color;

  // Os pacotes com pastilha ocupam mais espaço que o ícone nu; o contêiner
  // cresce junto para as duas variantes ficarem alinhadas na mesma grade.
  if (chosen === "solido" || chosen === "contraste") {
    const preenchido = chosen === "contraste";
    return (
      <span
        className={`flex shrink-0 items-center justify-center rounded-lg ${color} ${
          preenchido ? "bg-current" : "bg-current/15"
        }`}
        style={{ width: size * 1.35, height: size * 1.35 }}
      >
        <Icon
          size={size * 0.72}
          // No preenchido o ícone é vazado: herda o fundo da página.
          className={preenchido ? "text-bg" : color}
        />
      </span>
    );
  }

  if (chosen === "pastel") {
    return <Icon size={size} strokeWidth={1.4} className={`shrink-0 ${color} opacity-70`} />;
  }

  return <Icon size={size} className={`shrink-0 ${color}`} />;
}
