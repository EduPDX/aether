import { useQuery } from "@tanstack/react-query";
import { CornerLeftUp, Folder, HardDrive } from "lucide-react";
import { useState } from "react";
import { Button, Modal, Spinner } from "../../components/ui";
import { api } from "../../lib/api";

/** Browses directories ON THE SERVER MACHINE (where the Core runs). */
export function FolderBrowser({
  open,
  onClose,
  onPick,
}: {
  open: boolean;
  onClose: () => void;
  onPick: (path: string) => void;
}) {
  const [path, setPath] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["browse", path],
    queryFn: () => api.browse(path),
    enabled: open,
  });

  const data = query.data;
  const atRoots = !data?.path;

  return (
    <Modal open={open} onClose={onClose} title="Escolher pasta no servidor">
      <p className="mb-2 text-xs text-muted">
        Estas são as pastas da <b>máquina onde o Aether roda</b> (o servidor), não do seu
        computador.
      </p>

      <div className="mb-2 flex items-center gap-2 rounded-md border border-border bg-surface-2 px-2 py-1.5 text-xs">
        <HardDrive size={13} className="shrink-0 text-muted" />
        <span className="truncate font-mono">{data?.path ?? "Locais"}</span>
      </div>

      <div className="h-64 overflow-y-auto rounded-md border border-border bg-surface">
        {query.isLoading && <Spinner />}
        {query.isError && (
          <p className="p-3 text-xs text-danger">Erro ao listar: {String(query.error)}</p>
        )}
        {data && (
          <div className="p-1">
            {!atRoots && data.parent && (
              <button
                className="flex w-full cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm text-muted hover:bg-surface-2 hover:text-text"
                onClick={() => setPath(data.parent)}
              >
                <CornerLeftUp size={14} /> ..
              </button>
            )}
            {data.entries.map((entry) => (
              <button
                key={entry.path}
                className="flex w-full cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm text-muted hover:bg-surface-2 hover:text-text"
                onClick={() => setPath(entry.path)}
              >
                <Folder size={14} className="shrink-0 text-info" />
                <span className="truncate">{entry.name}</span>
              </button>
            ))}
            {!atRoots && data.entries.length === 0 && (
              <p className="p-3 text-xs text-muted">Nenhuma subpasta aqui.</p>
            )}
          </div>
        )}
      </div>

      <div className="mt-3 flex items-center justify-between gap-2">
        <span className="truncate text-xs text-muted">
          {data?.path ? (
            <>
              Selecionar: <span className="font-mono">{data.path}</span>
            </>
          ) : (
            "Entre em uma pasta para poder selecioná-la"
          )}
        </span>
        <span className="flex shrink-0 gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            variant="primary"
            disabled={!data?.path}
            onClick={() => {
              if (data?.path) {
                onPick(data.path);
                onClose();
              }
            }}
          >
            Usar esta pasta
          </Button>
        </span>
      </div>
    </Modal>
  );
}
