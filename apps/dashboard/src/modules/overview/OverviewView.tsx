import { useQueries, useQuery } from "@tanstack/react-query";
import { Boxes, HardDrive, Package, Server } from "lucide-react";
import { useState } from "react";
import type { ReactNode } from "react";
import { Gauge, HBarChart, Legend, TimeSeries } from "../../components/BarChart";
import type { SeriesKind } from "../../components/BarChart";
import { Badge, Select, Spinner } from "../../components/ui";
import type { ContentItem, Instance } from "../../lib/api";
import { api, formatBytes } from "../../lib/api";
import { chartPalette } from "../../lib/themes";

function StatTile({
  icon,
  label,
  value,
  sub,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <div className="flex items-center gap-2 text-muted">
        {icon}
        <span className="text-[11px] font-semibold tracking-wider uppercase">{label}</span>
      </div>
      {/* Número-herói: a leitura principal do bloco. */}
      <div className="mt-1.5 text-2xl font-bold tabular-nums">{value}</div>
      {sub && <div className="text-[11px] text-muted">{sub}</div>}
    </div>
  );
}

function Panel({ title, children, aside }: { title: string; children: ReactNode; aside?: ReactNode }) {
  return (
    <section className="rounded-xl border border-border bg-surface p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold">{title}</h3>
        {aside}
      </div>
      {children}
    </section>
  );
}

const STATE_LABEL: Record<string, string> = {
  running: "online",
  stopped: "parado",
  starting: "iniciando",
  stopping: "parando",
  crashed: "crashou",
};

export function OverviewView({ instances }: { instances: Instance[] }) {
  const [seriesKind, setSeriesKind] = useState<SeriesKind>("area");
  const palette = chartPalette();

  const metrics = useQuery({
    queryKey: ["metrics"],
    queryFn: api.metrics,
    refetchInterval: 5000,
  });

  const statuses = useQuery({
    queryKey: ["instances"],
    queryFn: api.instances,
    refetchInterval: 15000,
  });

  // Conteúdo de cada instância, em paralelo (cacheado pelo Core).
  const contentQueries = useQueries({
    queries: instances.map((i) => ({
      queryKey: ["content", i.id],
      queryFn: () => api.content(i.id),
      retry: false,
    })),
  });

  const loading = contentQueries.some((q) => q.isLoading);
  const all: { instance: Instance; items: ContentItem[] }[] = instances.map((inst, idx) => ({
    instance: inst,
    items: (contentQueries[idx]?.data as ContentItem[] | undefined) ?? [],
  }));

  const items = all.flatMap((a) => a.items);
  const totalSize = items.reduce((s, i) => s + i.size_bytes, 0);
  const enabled = items.filter((i) => i.enabled).length;
  const live = (statuses.data ?? instances).filter((i) => i.state === "running").length;

  // Magnitude por entidade (loader) — cores categóricas em ordem fixa.
  const loaderCounts = new Map<string, number>();
  for (const i of items) {
    const l = i.metadata.loader || "Desconhecido";
    loaderCounts.set(l, (loaderCounts.get(l) ?? 0) + 1);
  }
  const loaders = [...loaderCounts.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([label, value], idx) => ({
      label,
      value,
      color: palette[idx % palette.length],
    }));

  // Ranking: maiores mods (série única → cor de destaque, sem legenda).
  // O mesmo mod pode estar em várias instâncias: conta uma vez só.
  const byName = new Map<string, ContentItem>();
  for (const i of items) {
    const key = i.metadata.content_id || i.file.toLowerCase();
    const prev = byName.get(key);
    if (!prev || i.size_bytes > prev.size_bytes) byName.set(key, i);
  }
  const biggest = [...byName.values()]
    .sort((a, b) => b.size_bytes - a.size_bytes)
    .slice(0, 8)
    .map((i) => ({
      label: i.metadata.display_name || i.file,
      value: i.size_bytes,
      hint: `${i.metadata.display_name} — ${formatBytes(i.size_bytes)}`,
    }));

  const perInstance = all.map((a) => ({
    label: a.instance.name,
    value: a.items.length,
    hint: `${a.instance.name}: ${a.items.length} mods`,
  }));

  if (loading && items.length === 0) return <Spinner />;

  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-4">
        {metrics.data && (
          <>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <Gauge
                percent={metrics.data.host.cpu_percent}
                label="CPU"
                detail={`${metrics.data.host.cpu_count} núcleos${
                  metrics.data.host.load_avg.length
                    ? ` · carga ${metrics.data.host.load_avg[0].toFixed(2)}`
                    : ""
                }`}
                color={palette[0]}
              />
              <Gauge
                percent={metrics.data.host.mem_percent}
                label="Memória RAM"
                detail={`${formatBytes(metrics.data.host.mem_used)} de ${formatBytes(
                  metrics.data.host.mem_total,
                )}`}
                color={palette[1]}
              />
              <Gauge
                percent={metrics.data.host.disk_percent}
                label="Armazenamento"
                detail={`${formatBytes(metrics.data.host.disk_used)} de ${formatBytes(
                  metrics.data.host.disk_total,
                )}`}
                color={palette[2]}
              />
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <Panel
                title="CPU ao longo do tempo"
                aside={
                  <Select
                    className="py-1 text-xs"
                    value={seriesKind}
                    onChange={(e) => setSeriesKind(e.target.value as SeriesKind)}
                    title="Tipo de gráfico"
                  >
                    <option value="area">Área</option>
                    <option value="linha">Linha</option>
                    <option value="barras">Barras</option>
                  </Select>
                }
              >
                <TimeSeries
                  points={metrics.data.history.map((h) => h.cpu)}
                  kind={seriesKind}
                  color={palette[0]}
                  format={(n) => `${n.toFixed(0)}%`}
                />
              </Panel>
              <Panel title="Memória ao longo do tempo">
                <TimeSeries
                  points={metrics.data.history.map((h) => h.mem_percent)}
                  kind={seriesKind}
                  color={palette[1]}
                  format={(n) => `${n.toFixed(0)}%`}
                />
              </Panel>
            </div>

            {metrics.data.instances.some((i) => i.running) && (
              <Panel title="Consumo por servidor">
                <HBarChart
                  data={metrics.data.instances
                    .filter((i) => i.running)
                    .map((i, idx) => ({
                      label: i.name,
                      value: i.mem_bytes,
                      color: palette[idx % palette.length],
                      hint: `${i.name}: ${formatBytes(i.mem_bytes)} · CPU ${i.cpu_percent}%`,
                    }))}
                  format={formatBytes}
                />
              </Panel>
            )}
          </>
        )}

        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatTile
            icon={<Server size={14} />}
            label="Instâncias"
            value={String(instances.length)}
            sub={`${live} online agora`}
          />
          <StatTile
            icon={<Package size={14} />}
            label="Mods"
            value={String(items.length)}
            sub={`${enabled} ativados`}
          />
          <StatTile
            icon={<HardDrive size={14} />}
            label="Tamanho total"
            value={formatBytes(totalSize)}
            sub="somando todas as instâncias"
          />
          <StatTile
            icon={<Boxes size={14} />}
            label="Loaders"
            value={String(loaders.length)}
            sub={loaders.map((l) => l.label).join(", ") || "—"}
          />
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <Panel
            title="Mods por loader"
            aside={<Legend items={loaders.map((l) => ({ label: l.label, color: l.color }))} />}
          >
            <HBarChart data={loaders} />
          </Panel>

          <Panel title="Mods por instância">
            <HBarChart data={perInstance} />
          </Panel>
        </div>

        <Panel title="Maiores mods" aside={<span className="text-[11px] text-muted">top 8</span>}>
          <HBarChart data={biggest} format={formatBytes} />
        </Panel>

        <Panel title="Servidores">
          <div className="flex flex-col gap-1.5">
            {(statuses.data ?? instances).map((i) => (
              <div
                key={i.id}
                className="flex items-center gap-3 rounded-lg border border-border bg-surface-2 px-3 py-2"
              >
                <span className="truncate text-sm font-medium">{i.name}</span>
                <Badge tone={i.state === "running" ? "green" : i.state === "crashed" ? "red" : "neutral"}>
                  {STATE_LABEL[i.state] ?? i.state}
                </Badge>
                <span className="ml-auto truncate font-mono text-[11px] text-muted">
                  {i.root_dir}
                </span>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  );
}
