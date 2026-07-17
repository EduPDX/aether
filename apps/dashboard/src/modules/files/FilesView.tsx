import Editor from "@monaco-editor/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ChevronRight,
  File,
  FilePlus,
  Folder,
  FolderPlus,
  Pencil,
  Save,
  Trash2,
  X,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Button, Spinner } from "../../components/ui";
import type { Instance } from "../../lib/api";
import { api, formatBytes } from "../../lib/api";
import { languageFor } from "../../lib/monaco";

function join(dir: string, name: string): string {
  return dir ? `${dir}/${name}` : name;
}

export function FilesView({ instance }: { instance: Instance }) {
  const qc = useQueryClient();
  const [path, setPath] = useState("");
  const [openFile, setOpenFile] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState("");

  const listing = useQuery({
    queryKey: ["files", instance.id, path],
    queryFn: () => api.listFiles(instance.id, path),
  });

  const invalidate = () =>
    qc.invalidateQueries({ queryKey: ["files", instance.id, path] });

  async function open(file: string) {
    setError("");
    try {
      const res = await api.readFile(instance.id, file);
      setOpenFile(file);
      setContent(res.content);
      setDirty(false);
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    }
  }

  const save = useCallback(async () => {
    if (openFile === null) return;
    setError("");
    try {
      await api.writeFile(instance.id, openFile, content);
      setDirty(false);
      invalidate();
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openFile, content, instance.id]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        save();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [save]);

  const op = useMutation({
    mutationFn: ({
      kind,
      target,
      newName,
    }: {
      kind: "mkdir" | "rename" | "delete";
      target: string;
      newName?: string;
    }) => api.fileOp(instance.id, kind, target, newName),
    onSuccess: invalidate,
    onError: (e) => setError(String(e)),
  });

  const crumbs = path ? path.split("/") : [];

  return (
    <div className="flex h-full min-h-0">
      {/* Lista de arquivos */}
      <div className="flex w-72 shrink-0 flex-col border-r border-border">
        <div className="flex items-center gap-1 border-b border-border px-2 py-1.5 text-xs">
          <button className="cursor-pointer text-muted hover:text-text" onClick={() => setPath("")}>
            {instance.name}
          </button>
          {crumbs.map((c, i) => (
            <span key={i} className="flex items-center gap-1">
              <ChevronRight size={11} className="text-muted" />
              <button
                className="cursor-pointer text-muted hover:text-text"
                onClick={() => setPath(crumbs.slice(0, i + 1).join("/"))}
              >
                {c}
              </button>
            </span>
          ))}
          <span className="ml-auto flex gap-1">
            <button
              title="Novo arquivo"
              className="cursor-pointer p-1 text-muted hover:text-text"
              onClick={() => {
                const name = prompt("Nome do novo arquivo:");
                if (name) {
                  setOpenFile(join(path, name));
                  setContent("");
                  setDirty(true);
                }
              }}
            >
              <FilePlus size={14} />
            </button>
            <button
              title="Nova pasta"
              className="cursor-pointer p-1 text-muted hover:text-text"
              onClick={() => {
                const name = prompt("Nome da nova pasta:");
                if (name) op.mutate({ kind: "mkdir", target: join(path, name) });
              }}
            >
              <FolderPlus size={14} />
            </button>
          </span>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-1">
          {listing.isLoading && <Spinner />}
          {listing.data?.map((entry) => (
            <div
              key={entry.name}
              className="group flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-sm text-muted hover:bg-surface-2 hover:text-text"
              onClick={() =>
                entry.is_dir ? setPath(join(path, entry.name)) : open(join(path, entry.name))
              }
            >
              {entry.is_dir ? (
                <Folder size={14} className="shrink-0 text-info" />
              ) : (
                <File size={14} className="shrink-0" />
              )}
              <span className="min-w-0 flex-1 truncate">{entry.name}</span>
              <span className="hidden text-[10px] group-hover:block">
                {!entry.is_dir && formatBytes(entry.size)}
              </span>
              <button
                title="Renomear"
                className="hidden cursor-pointer text-muted hover:text-text group-hover:block"
                onClick={(e) => {
                  e.stopPropagation();
                  const name = prompt("Novo nome:", entry.name);
                  if (name && name !== entry.name)
                    op.mutate({ kind: "rename", target: join(path, entry.name), newName: name });
                }}
              >
                <Pencil size={12} />
              </button>
              <button
                title="Mover para a lixeira"
                className="hidden cursor-pointer text-muted hover:text-danger group-hover:block"
                onClick={(e) => {
                  e.stopPropagation();
                  if (confirm(`Mover "${entry.name}" para a lixeira?`))
                    op.mutate({ kind: "delete", target: join(path, entry.name) });
                }}
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))}
          {listing.data?.length === 0 && (
            <p className="p-3 text-xs text-muted">Pasta vazia.</p>
          )}
        </div>
      </div>

      {/* Editor */}
      <div className="flex min-w-0 flex-1 flex-col">
        {openFile === null ? (
          <div className="flex h-full items-center justify-center text-sm text-muted">
            Selecione um arquivo para editar.
          </div>
        ) : (
          <>
            <div className="flex items-center gap-2 border-b border-border px-3 py-1.5">
              <span className="truncate text-xs font-medium">
                {openFile}
                {dirty && <span className="text-warn"> ●</span>}
              </span>
              {error && <span className="truncate text-xs text-danger">{error}</span>}
              <span className="ml-auto flex gap-1.5">
                <Button variant="primary" disabled={!dirty} onClick={save} title="Ctrl+S">
                  <Save size={13} /> Salvar
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => {
                    if (!dirty || confirm("Descartar alterações não salvas?")) {
                      setOpenFile(null);
                      setDirty(false);
                    }
                  }}
                >
                  <X size={13} />
                </Button>
              </span>
            </div>
            <div className="min-h-0 flex-1">
              <Editor
                path={openFile}
                language={languageFor(openFile)}
                value={content}
                theme="vs-dark"
                options={{ fontSize: 13, minimap: { enabled: false }, wordWrap: "on" }}
                onChange={(v) => {
                  setContent(v ?? "");
                  setDirty(true);
                }}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
