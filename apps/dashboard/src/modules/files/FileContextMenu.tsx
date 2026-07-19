import { Download, FolderOpen, Pencil, Trash2 } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { FileEntry } from "../../lib/api";

export interface MenuTarget {
  entry: FileEntry;
  x: number;
  y: number;
}

const MARGEM = 8;

/**
 * Menu de contexto do gerenciador de arquivos.
 *
 * Existe porque a visão em ícones — que é a padrão — não tinha ação nenhuma:
 * renomear e apagar só apareciam na visão de lista, então na prática sumiam.
 * Botão direito é onde as pessoas procuram isso.
 */
export function FileContextMenu({
  target,
  onClose,
  onOpen,
  onDownload,
  onRename,
  onTrash,
}: {
  target: MenuTarget | null;
  onClose: () => void;
  onOpen: (entry: FileEntry) => void;
  onDownload: (entry: FileEntry) => void;
  onRename: (entry: FileEntry) => void;
  onTrash: (entry: FileEntry) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ x: 0, y: 0 });

  // Posiciona depois de medir: perto da borda o menu abriria para fora da tela.
  useLayoutEffect(() => {
    if (!target || !ref.current) return;
    const { width, height } = ref.current.getBoundingClientRect();
    setPos({
      x: Math.min(target.x, window.innerWidth - width - MARGEM),
      y: Math.min(target.y, window.innerHeight - height - MARGEM),
    });
  }, [target]);

  useEffect(() => {
    if (!target) return;
    const fechar = () => onClose();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    // `capture` na rolagem: o menu ficaria flutuando longe do item.
    window.addEventListener("scroll", fechar, true);
    window.addEventListener("resize", fechar);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("scroll", fechar, true);
      window.removeEventListener("resize", fechar);
      window.removeEventListener("keydown", onKey);
    };
  }, [target, onClose]);

  if (!target) return null;
  const { entry } = target;

  const itens = [
    {
      rotulo: entry.is_dir ? "Abrir" : "Editar",
      icone: <FolderOpen size={14} />,
      acao: () => onOpen(entry),
    },
    {
      rotulo: entry.is_dir ? "Baixar como .zip" : "Baixar",
      icone: <Download size={14} />,
      acao: () => onDownload(entry),
    },
    { rotulo: "Renomear", icone: <Pencil size={14} />, acao: () => onRename(entry) },
    {
      rotulo: "Mover para a lixeira",
      icone: <Trash2 size={14} />,
      acao: () => onTrash(entry),
      perigo: true,
    },
  ];

  return (
    <>
      {/* Camada que captura o clique fora — inclusive o botão direito, que
          senão abriria o menu do navegador por cima deste. */}
      <div
        className="fixed inset-0 z-50"
        onClick={onClose}
        onContextMenu={(e) => {
          e.preventDefault();
          onClose();
        }}
      />
      <div
        ref={ref}
        role="menu"
        className="fixed z-50 min-w-52 overflow-hidden rounded-lg border border-border bg-surface py-1 shadow-2xl"
        style={{ left: pos.x, top: pos.y }}
      >
        <div className="truncate border-b border-border px-3 py-1.5 text-[11px] text-muted">
          {entry.name}
        </div>
        {itens.map((item) => (
          <button
            key={item.rotulo}
            role="menuitem"
            className={`flex w-full cursor-pointer items-center gap-2.5 px-3 py-2 text-left text-sm transition-colors hover:bg-surface-2 ${
              item.perigo ? "text-danger" : "text-text"
            }`}
            onClick={() => {
              onClose();
              item.acao();
            }}
          >
            {item.icone}
            {item.rotulo}
          </button>
        ))}
      </div>
    </>
  );
}
