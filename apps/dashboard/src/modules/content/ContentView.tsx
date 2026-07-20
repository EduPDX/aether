import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Boxes, CheckCircle2, Copy, Download, HardDrive, LayoutGrid, List, Package, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { useDialog } from "../../components/Dialog";
import { UploadButton } from "../../components/UploadButton";
import { Button, Input, Panel, Segmented, Select, Spinner, StatTile } from "../../components/ui";
import type { ContentItem, Instance } from "../../lib/api";
import { api, formatBytes } from "../../lib/api";
import { useProvider } from "../../lib/providers";
import { ModCard } from "./ModCard";
import { ModDetails } from "./ModDetails";
import { ModTable } from "./ModTable";

type StatusFilter = "all" | "enabled" | "disabled";
type SortKey = "name" | "size" | "mtime";
type ViewMode = "grid" | "list";

const VIEW_KEY = "aether.content.view";

const VIEW_OPTIONS = [
  { value: "grid" as const, icon: <LayoutGrid size={15} />, label: "Cartões" },
  { value: "list" as const, icon: <List size={15} />, label: "Lista compacta" },
];

export function ContentView({
  instance,
  contentType = "mod",
}: {
  instance: Instance;
  contentType?: string;
}) {
  const qc = useQueryClient();
  const dialog = useDialog();
  const [search, setSearch] = useState("");
  const [loader, setLoader] = useState("all");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [sort, setSort] = useState<SortKey>("name");
  const [dupsOnly, setDupsOnly] = useState(false);
  const [detail, setDetail] = useState<ContentItem | null>(null);
  const [view, setView] = useState<ViewMode>(
    () => (localStorage.getItem(VIEW_KEY) as ViewMode | null) ?? "grid",
  );

  function changeView(next: ViewMode) {
    setView(next);
    localStorage.setItem(VIEW_KEY, next);
  }

  const query = useQuery({
    queryKey: ["content", instance.id, contentType],
    queryFn: () => api.content(instance.id, contentType),
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["content", instance.id, contentType] });
  const toggle = useMutation({
    mutationFn: (file: string) => api.toggle(instance.id, file, contentType),
    onSettled: invalidate,
  });
  const trash = useMutation({
    mutationFn: (file: string) => api.trash(instance.id, file, contentType),
    onSettled: invalidate,
  });

  const provider = useProvider(instance.provider_id);
  const tipo = provider?.content_types.find((t) => t.id === contentType);
  const uploadDir =
    instance.content_dirs[contentType] === "."
      ? ""
      : (instance.content_dirs[contentType] ?? tipo?.default_directory ?? "mods");
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

  async function askTrash(item: ContentItem) {
    const ok = await dialog.confirm({
      title: "Mover para a lixeira",
      message: `“${item.metadata.display_name}” sai da pasta de mods. O arquivo vai para a lixeira do Aether, não é apagado.`,
      confirmText: "Mover",
      tone: "danger",
    });
    if (ok) trash.mutate(item.file);
  }

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

  // O rótulo vem do provider: cada jogo chama seu conteúdo do próprio jeito.
  const titulo = tipo?.label ?? "Conteúdo";

  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="mx-auto flex w-full max-w-[1900px] flex-col gap-4">
        {/* Mesma leitura de topo da Visão geral: números-herói antes da lista. */}
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatTile
            icon={<Package size={14} />}
            label="Mods"
            value={String(stats.total)}
            sub={filtered.length === stats.total ? "nenhum filtro ativo" : `${filtered.length} após filtros`}
          />
          <StatTile
            icon={<CheckCircle2 size={14} />}
            label="Ativados"
            value={String(stats.enabled)}
            sub={stats.disabled > 0 ? `${stats.disabled} desativados` : "todos ativos"}
            tone="accent"
          />
          <StatTile
            icon={<HardDrive size={14} />}
            label="Tamanho"
            value={formatBytes(stats.size)}
            sub="somando todos os arquivos"
          />
          <StatTile
            icon={stats.dups > 0 ? <Copy size={14} /> : <Boxes size={14} />}
            label={stats.dups > 0 ? "Duplicados" : "Loaders"}
            value={stats.dups > 0 ? String(stats.dups) : String(loaders.length)}
            sub={stats.dups > 0 ? "mesmo mod em dois arquivos" : loaders.join(", ") || "—"}
            tone={stats.dups > 0 ? "warn" : undefined}
          />
        </div>

        <Panel
          title={titulo}
          hint={`${filtered.length} de ${stats.total} exibidos`}
          bodyClassName="px-0 pb-0"
          aside={
            <span className="flex items-center gap-1.5">
              <Segmented value={view} onChange={changeView} options={VIEW_OPTIONS} />
              <UploadButton
                instanceId={instance.id}
                path={uploadDir}
                label="Adicionar mods"
                accept=".jar"
              />
              <Button variant="ghost" onClick={exportList} title="Exportar lista .txt">
                <Download size={14} /> Exportar
              </Button>
            </span>
          }
        >
      <div className="flex flex-wrap items-center gap-2 border-y border-border px-4 py-3">
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
      </div>

      {filtered.length === 0 ? (
        <div className="py-16 text-center text-sm text-muted">
          Nenhum mod encontrado com os filtros atuais.
        </div>
      ) : view === "list" ? (
        <ModTable
          items={filtered}
          onToggle={(file) => toggle.mutate(file)}
          onTrash={askTrash}
          onOpen={setDetail}
        />
      ) : (
        <div className="grid grid-cols-1 gap-2.5 p-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {filtered.map((item) => (
            <ModCard
              key={item.file}
              item={item}
              onToggle={() => toggle.mutate(item.file)}
              onTrash={() => askTrash(item)}
              onOpen={() => setDetail(item)}
            />
          ))}
        </div>
      )}
        </Panel>

        <ModDetails item={detail} onClose={() => setDetail(null)} />
      </div>
    </div>
  );
}
