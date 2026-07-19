import Editor from "@monaco-editor/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowUpDown,
  ChevronRight,
  CornerLeftUp,
  Download,
  FilePlus,
  FolderPlus,
  Grid2x2,
  LayoutGrid,
  List,
  Pencil,
  Save,
  Trash2,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useDialog } from "../../components/Dialog";
import { UploadButton } from "../../components/UploadButton";
import { Button, Segmented, Select, Spinner } from "../../components/ui";
import type { FileEntry, Instance } from "../../lib/api";
import { api, formatBytes } from "../../lib/api";
import { languageFor } from "../../lib/monaco";
import { FileGrid } from "./FileGrid";
import { FileIcon, fileKind } from "./FileIcon";

function join(dir: string, name: string): string {
  return dir ? `${dir}/${name}` : name;
}

type SortKey = "name" | "size" | "mtime";
type ViewMode = "lg" | "md" | "list";

const VIEW_KEY = "aether.files.view";

const VIEW_OPTIONS = [
  { value: "lg" as const, icon: <LayoutGrid size={15} />, label: "Ícones grandes" },
  { value: "md" as const, icon: <Grid2x2 size={15} />, label: "Ícones médios" },
  { value: "list" as const, icon: <List size={15} />, label: "Lista com detalhes" },
];

export function FilesView({ instance }: { instance: Instance }) {
  const qc = useQueryClient();
  const dialog = useDialog();
  const [path, setPath] = useState("");
  const [openFile, setOpenFile] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState("");
  const [sort, setSort] = useState<SortKey>("name");
  const [asc, setAsc] = useState(true);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState("");
  const [view, setView] = useState<ViewMode>(
    () => (localStorage.getItem(VIEW_KEY) as ViewMode | null) ?? "lg",
  );

  function changeView(next: ViewMode) {
    setView(next);
    localStorage.setItem(VIEW_KEY, next);
  }

  function toggleSelect(name: string, checked: boolean) {
    const next = new Set(selected);
    if (checked) next.add(name);
    else next.delete(name);
    setSelected(next);
  }

  const listing = useQuery({
    queryKey: ["files", instance.id, path],
    queryFn: () => api.listFiles(instance.id, path),
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["files", instance.id, path] });

  // Trocar de pasta limpa a seleção: ela é por diretório.
  useEffect(() => setSelected(new Set()), [path]);

  const rows = useMemo(() => {
    const data = [...(listing.data ?? [])];
    const dir = asc ? 1 : -1;
    data.sort((a, b) => {
      // Pastas sempre antes dos arquivos, como no Explorer.
      if (a.is_dir !== b.is_dir) return a.is_dir ? -1 : 1;
      if (sort === "size") return (a.size - b.size) * dir;
      if (sort === "mtime") return (a.mtime - b.mtime) * dir;
      return a.name.localeCompare(b.name, "pt-BR") * dir;
    });
    return data;
  }, [listing.data, sort, asc]);

  function toggleSort(key: SortKey) {
    if (sort === key) setAsc(!asc);
    else {
      setSort(key);
      setAsc(true);
    }
  }

  /**
   * Entrega o download ao próprio navegador.
   *
   * Antes isto buscava por fetch e montava um Blob: o arquivo inteiro ia para
   * a memória da aba antes de ser salvo, o que não sobrevive a uma pasta de
   * vários GB — era por isso que baixar o mundo não funcionava. Agora pede um
   * link assinado curto e navega até ele, então o navegador grava direto em
   * disco, com barra de progresso e sem limite prático de tamanho.
   */
  async function download(rel: string) {
    setError("");
    setBusy(rel);
    try {
      const { token } = await api.downloadToken(instance.id, rel);
      const url = `${api.downloadUrl(instance.id, rel)}&token=${encodeURIComponent(token)}`;
      const a = document.createElement("a");
      a.href = url;
      a.rel = "noopener";
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setBusy("");
    }
  }

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
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s" && openFile !== null) {
        e.preventDefault();
        save();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [save, openFile]);

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

  async function deleteSelected() {
    const nomes = [...selected];
    const ok = await dialog.confirm({
      title: "Mover para a lixeira",
      message: `${nomes.length} item(ns) selecionado(s) vão para a lixeira do Aether.`,
      confirmText: "Mover",
      tone: "danger",
    });
    if (!ok) return;
    for (const n of nomes) await op.mutateAsync({ kind: "delete", target: join(path, n) });
    setSelected(new Set());
  }

  const crumbs = path ? path.split("/") : [];
  const allSelected = rows.length > 0 && selected.size === rows.length;

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* Barra de caminho e ações */}
      <div className="flex flex-wrap items-center gap-1 border-b border-border px-3 py-2 text-xs">
        {path && (
          <button
            title="Subir um nível"
            className="cursor-pointer rounded p-1 text-muted hover:bg-surface-2 hover:text-text"
            onClick={() => setPath(crumbs.slice(0, -1).join("/"))}
          >
            <CornerLeftUp size={14} />
          </button>
        )}
        <button
          className="cursor-pointer rounded px-1.5 py-0.5 font-medium text-muted hover:bg-surface-2 hover:text-text"
          onClick={() => setPath("")}
        >
          {instance.name}
        </button>
        {crumbs.map((c, i) => (
          <span key={i} className="flex items-center">
            <ChevronRight size={11} className="text-muted/60" />
            <button
              className="cursor-pointer rounded px-1.5 py-0.5 text-muted hover:bg-surface-2 hover:text-text"
              onClick={() => setPath(crumbs.slice(0, i + 1).join("/"))}
            >
              {c}
            </button>
          </span>
        ))}

        <span className="ml-auto flex items-center gap-1.5">
          {/* Na grade não há cabeçalho de coluna para clicar: o seletor supre isso. */}
          {openFile === null && view !== "list" && (
            <Select
              className="py-1 text-xs"
              title="Ordenar por"
              value={`${sort}:${asc ? "asc" : "desc"}`}
              onChange={(e) => {
                const [k, dir] = e.target.value.split(":");
                setSort(k as SortKey);
                setAsc(dir === "asc");
              }}
            >
              <option value="name:asc">Nome (A–Z)</option>
              <option value="name:desc">Nome (Z–A)</option>
              <option value="size:desc">Maiores primeiro</option>
              <option value="size:asc">Menores primeiro</option>
              <option value="mtime:desc">Mais recentes</option>
              <option value="mtime:asc">Mais antigos</option>
            </Select>
          )}
          {openFile === null && (
            <Segmented value={view} onChange={changeView} options={VIEW_OPTIONS} />
          )}
          <UploadButton instanceId={instance.id} path={path} label="Enviar" />
          <button
            title="Novo arquivo"
            className="cursor-pointer rounded p-1.5 text-muted hover:bg-surface-2 hover:text-text"
            onClick={async () => {
              const name = await dialog.promptText({
                title: "Novo arquivo",
                input: { label: "Nome do arquivo", placeholder: "config.toml" },
                confirmText: "Criar",
              });
              if (name) {
                setOpenFile(join(path, name));
                setContent("");
                setDirty(true);
              }
            }}
          >
            <FilePlus size={15} />
          </button>
          <button
            title="Nova pasta"
            className="cursor-pointer rounded p-1.5 text-muted hover:bg-surface-2 hover:text-text"
            onClick={async () => {
              const name = await dialog.promptText({
                title: "Nova pasta",
                input: { label: "Nome da pasta", placeholder: "datapacks" },
                confirmText: "Criar",
              });
              if (name) op.mutate({ kind: "mkdir", target: join(path, name) });
            }}
          >
            <FolderPlus size={15} />
          </button>
          <button
            title="Baixar esta pasta (.zip)"
            className="cursor-pointer rounded p-1.5 text-muted hover:bg-surface-2 hover:text-text"
            onClick={() => download(path)}
          >
            <Download size={15} />
          </button>
        </span>
      </div>

      {/* Ações em lote */}
      {selected.size > 0 && (
        <div className="flex items-center gap-2 border-b border-border bg-surface-2 px-3 py-1.5 text-xs">
          <span className="font-medium">{selected.size} selecionado(s)</span>
          <Button
            variant="default"
            onClick={async () => {
              for (const n of selected) await download(join(path, n));
            }}
          >
            <Download size={13} /> Baixar
          </Button>
          <Button variant="danger" onClick={deleteSelected}>
            <Trash2 size={13} /> Mover para a lixeira
          </Button>
          <button
            className="ml-auto cursor-pointer text-muted hover:text-text"
            onClick={() => setSelected(new Set())}
          >
            limpar seleção
          </button>
        </div>
      )}

      {error && <div className="border-b border-border px-3 py-1.5 text-xs text-danger">{error}</div>}

      <div className="flex min-h-0 flex-1">
        {/* Tabela de arquivos */}
        <div
          className={`flex min-h-0 flex-col ${
            openFile !== null ? "w-80 shrink-0 border-r border-border" : "flex-1"
          }`}
        >
          <div className="min-h-0 flex-1 overflow-auto">
            {listing.isLoading && <Spinner />}

            {/* Com o editor aberto a coluna fica estreita demais para a grade. */}
            {openFile === null && view !== "list" && rows.length > 0 && (
              <FileGrid
                entries={rows}
                selected={selected}
                size={view}
                onOpen={(entry) =>
                  entry.is_dir ? setPath(join(path, entry.name)) : open(join(path, entry.name))
                }
                onToggleSelect={toggleSelect}
              />
            )}

            {(openFile !== null || view === "list") && (
            <table className="w-full text-left text-xs">
              <thead className="sticky top-0 z-10 bg-surface-2 text-muted">
                <tr>
                  <th className="w-8 px-2 py-1.5">
                    <input
                      type="checkbox"
                      className="accent-(--color-accent-dim)"
                      checked={allSelected}
                      onChange={(e) =>
                        setSelected(e.target.checked ? new Set(rows.map((r) => r.name)) : new Set())
                      }
                    />
                  </th>
                  <ThSort label="Nome" active={sort === "name"} asc={asc} onClick={() => toggleSort("name")} />
                  {openFile === null && (
                    <>
                      <ThSort
                        label="Tamanho"
                        active={sort === "size"}
                        asc={asc}
                        onClick={() => toggleSort("size")}
                        className="w-28"
                      />
                      <th className="w-32 px-2 py-1.5 font-semibold">Tipo</th>
                      <ThSort
                        label="Modificado"
                        active={sort === "mtime"}
                        asc={asc}
                        onClick={() => toggleSort("mtime")}
                        className="w-40"
                      />
                    </>
                  )}
                  <th className="w-24 px-2 py-1.5" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {rows.map((entry: FileEntry) => {
                  const rel = join(path, entry.name);
                  const isSel = selected.has(entry.name);
                  return (
                    <tr
                      key={entry.name}
                      className={`group cursor-pointer ${isSel ? "bg-surface-3" : "hover:bg-surface-2"}`}
                      onClick={() => (entry.is_dir ? setPath(rel) : open(rel))}
                    >
                      <td className="px-2 py-1.5" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          className="accent-(--color-accent-dim)"
                          checked={isSel}
                          onChange={(e) => toggleSelect(entry.name, e.target.checked)}
                        />
                      </td>
                      <td className="px-2 py-1.5">
                        <span className="flex items-center gap-2">
                          <FileIcon name={entry.name} isDir={entry.is_dir} />
                          <span className="truncate" title={entry.name}>
                            {entry.name}
                          </span>
                        </span>
                      </td>
                      {openFile === null && (
                        <>
                          <td className="px-2 py-1.5 text-muted tabular-nums">
                            {entry.is_dir ? "—" : formatBytes(entry.size)}
                          </td>
                          <td className="px-2 py-1.5 text-muted">
                            {fileKind(entry.name, entry.is_dir)}
                          </td>
                          <td className="px-2 py-1.5 text-muted whitespace-nowrap">
                            {new Date(entry.mtime * 1000).toLocaleString("pt-BR")}
                          </td>
                        </>
                      )}
                      <td className="px-2 py-1.5" onClick={(e) => e.stopPropagation()}>
                        <span className="flex justify-end gap-1 opacity-0 group-hover:opacity-100">
                          <button
                            title={entry.is_dir ? "Baixar pasta (.zip)" : "Baixar"}
                            className="cursor-pointer text-muted hover:text-text"
                            onClick={() => download(rel)}
                            disabled={busy === rel}
                          >
                            <Download size={13} />
                          </button>
                          <button
                            title="Renomear"
                            className="cursor-pointer text-muted hover:text-text"
                            onClick={async () => {
                              const name = await dialog.promptText({
                                title: "Renomear",
                                input: { label: "Novo nome", initialValue: entry.name },
                                confirmText: "Renomear",
                              });
                              if (name && name !== entry.name)
                                op.mutate({ kind: "rename", target: rel, newName: name });
                            }}
                          >
                            <Pencil size={13} />
                          </button>
                          <button
                            title="Mover para a lixeira"
                            className="cursor-pointer text-muted hover:text-danger"
                            onClick={async () => {
                              const ok = await dialog.confirm({
                                title: "Mover para a lixeira",
                                message: `“${entry.name}” vai para a lixeira do Aether.`,
                                confirmText: "Mover",
                                tone: "danger",
                              });
                              if (ok) op.mutate({ kind: "delete", target: rel });
                            }}
                          >
                            <Trash2 size={13} />
                          </button>
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            )}
            {!listing.isLoading && rows.length === 0 && (
              <p className="p-6 text-center text-xs text-muted">Pasta vazia.</p>
            )}
          </div>

          <div className="border-t border-border px-3 py-1 text-[11px] text-muted">
            {rows.filter((r) => r.is_dir).length} pasta(s) · {rows.filter((r) => !r.is_dir).length}{" "}
            arquivo(s) ·{" "}
            {formatBytes(rows.reduce((s, r) => s + (r.is_dir ? 0 : r.size), 0))}
          </div>
        </div>

        {/* Editor */}
        {openFile !== null && (
          <div className="flex min-w-0 flex-1 flex-col">
            <div className="flex items-center gap-2 border-b border-border px-3 py-1.5">
              <FileIcon name={openFile} isDir={false} />
              <span className="truncate text-xs font-medium">
                {openFile}
                {dirty && <span className="text-warn"> ●</span>}
              </span>
              <span className="ml-auto flex gap-1.5">
                <Button variant="primary" disabled={!dirty} onClick={save} title="Ctrl+S">
                  <Save size={13} /> Salvar
                </Button>
                <Button
                  variant="ghost"
                  onClick={async () => {
                    const ok =
                      !dirty ||
                      (await dialog.confirm({
                        title: "Descartar alterações",
                        message: `As mudanças em ${openFile} não foram salvas e serão perdidas.`,
                        confirmText: "Descartar",
                        tone: "danger",
                      }));
                    if (ok) {
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
          </div>
        )}
      </div>
    </div>
  );
}

function ThSort({
  label,
  active,
  asc,
  onClick,
  className = "",
}: {
  label: string;
  active: boolean;
  asc: boolean;
  onClick: () => void;
  className?: string;
}) {
  return (
    <th className={`px-2 py-1.5 font-semibold ${className}`}>
      <button
        className={`flex cursor-pointer items-center gap-1 hover:text-text ${
          active ? "text-text" : ""
        }`}
        onClick={onClick}
      >
        {label}
        <ArrowUpDown size={11} className={active ? "opacity-100" : "opacity-40"} />
        {active && <span className="text-[9px]">{asc ? "▲" : "▼"}</span>}
      </button>
    </th>
  );
}
