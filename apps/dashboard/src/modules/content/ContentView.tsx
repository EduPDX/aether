import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { UploadButton } from "../../components/UploadButton";
import { Badge, Button, Input, Select, Spinner } from "../../components/ui";
import type { ContentItem, Instance } from "../../lib/api";
import { api, formatBytes } from "../../lib/api";
import { ModCard } from "./ModCard";

type StatusFilter = "all" | "enabled" | "disabled";
type SortKey = "name" | "size" | "mtime";

export function ContentView({ instance }: { instance: Instance }) {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [loader, setLoader] = useState("all");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [sort, setSort] = useState<SortKey>("name");
  const [dupsOnly, setDupsOnly] = useState(false);

  const query = useQuery({
    queryKey: ["content", instance.id],
    queryFn: () => api.content(instance.id),
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["content", instance.id] });
  const toggle = useMutation({
    mutationFn: (file: string) => api.toggle(instance.id, file),
    onSettled: invalidate,
  });
  const trash = useMutation({
    mutationFn: (file: string) => api.trash(instance.id, file),
    onSettled: invalidate,
  });

  const items = query.data ?? [];
  const loaders = useMemo(
    () => [...new Set(items.map((i) => i.metadata.loader).filter(Boolean))].sort(),
    [items],
  );

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    let out = items.filter((i) => {
      if (q) {
        const hay =
          `${i.metadata.display_name} ${i.file} ${i.metadata.authors} ${i.metadata.description} ${i.metadata.content_id}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      if (loader !== "all" && i.metadata.loader !== loader) return false;
      if (status === "enabled" && !i.enabled) return false;
      if (status === "disabled" && i.enabled) return false;
      if (dupsOnly && !i.duplicate) return false;
      return true;
    });
    const bySort: Record<SortKey, (a: ContentItem, b: ContentItem) => number> = {
      name: (a, b) => a.metadata.display_name.localeCompare(b.metadata.display_name),
      size: (a, b) => b.size_bytes - a.size_bytes,
      mtime: (a, b) => b.mtime - a.mtime,
    };
    out = [...out].sort(bySort[sort]);
    return out;
  }, [items, search, loader, status, sort, dupsOnly]);

  const stats = useMemo(() => {
    const enabled = items.filter((i) => i.enabled).length;
    const dups = items.filter((i) => i.duplicate).length;
    const size = items.reduce((s, i) => s + i.size_bytes, 0);
    return { total: items.length, enabled, disabled: items.length - enabled, dups, size };
  }, [items]);

  function exportList() {
    const lines = [
      `# Lista de Mods — ${instance.name}`,
      `# Gerado em ${new Date().toLocaleString("pt-BR")}`,
      "",
      ...items.map((i) => {
        const st = i.enabled ? "" : "  [DESATIVADO]";
        const m = i.metadata;
        return `- ${m.display_name} (${m.version}) — MC ${m.game_version} — ${m.loader} — ${i.file}${st}`;
      }),
      "",
      `Total: ${items.length} mods`,
    ];
    const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `mods_${instance.name.toLowerCase()}.txt`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  if (query.isLoading) return <Spinner />;
  if (query.isError)
    return <div className="p-6 text-sm text-danger">Erro ao listar: {String(query.error)}</div>;

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-3">
        <div className="relative min-w-56 flex-1">
          <Search size={14} className="absolute top-1/2 left-2.5 -translate-y-1/2 text-muted" />
          <Input
            id="content-search"
            className="w-full pl-8"
            placeholder="Buscar por nome, arquivo, autor… (Ctrl+K)"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Select value={loader} onChange={(e) => setLoader(e.target.value)}>
          <option value="all">Loader: todos</option>
          {loaders.map((l) => (
            <option key={l} value={l}>
              {l}
            </option>
          ))}
        </Select>
        <Select value={status} onChange={(e) => setStatus(e.target.value as StatusFilter)}>
          <option value="all">Status: todos</option>
          <option value="enabled">Ativados</option>
          <option value="disabled">Desativados</option>
        </Select>
        <Select value={sort} onChange={(e) => setSort(e.target.value as SortKey)}>
          <option value="name">Ordenar: nome</option>
          <option value="size">Ordenar: tamanho</option>
          <option value="mtime">Ordenar: recente</option>
        </Select>
        <label className="flex cursor-pointer items-center gap-1.5 text-sm text-muted select-none">
          <input
            type="checkbox"
            checked={dupsOnly}
            onChange={(e) => setDupsOnly(e.target.checked)}
            className="accent-(--color-accent-dim)"
          />
          Só duplicados
        </label>
        <UploadButton
          instanceId={instance.id}
          path={instance.content_dirs.mod === "." ? "" : (instance.content_dirs.mod ?? "mods")}
          label="Adicionar mods"
          accept=".jar"
        />
        <Button variant="ghost" onClick={exportList} title="Exportar lista .txt">
          <Download size={14} /> Exportar
        </Button>
      </div>

      <div className="flex items-center gap-3 px-4 py-2 text-xs text-muted">
        <span>
          <b className="text-text">{filtered.length}</b> de {stats.total} mods
        </span>
        <Badge tone="green">{stats.enabled} ativados</Badge>
        {stats.disabled > 0 && <Badge tone="neutral">{stats.disabled} desativados</Badge>}
        {stats.dups > 0 && <Badge tone="orange">{stats.dups} duplicados</Badge>}
        <span className="ml-auto">{formatBytes(stats.size)} no total</span>
      </div>

      <div className="grid flex-1 auto-rows-min grid-cols-1 gap-2.5 overflow-y-auto px-4 pb-6 md:grid-cols-2 xl:grid-cols-3">
        {filtered.map((item) => (
          <ModCard
            key={item.file}
            item={item}
            onToggle={() => toggle.mutate(item.file)}
            onTrash={() => {
              if (confirm(`Mover "${item.file}" para a lixeira?`)) trash.mutate(item.file);
            }}
          />
        ))}
        {filtered.length === 0 && (
          <div className="col-span-full py-16 text-center text-sm text-muted">
            Nenhum mod encontrado com os filtros atuais.
          </div>
        )}
      </div>
    </div>
  );
}
