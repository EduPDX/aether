import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeftRight, Copy } from "lucide-react";
import { useState } from "react";
import { Badge, Button, Select, Spinner } from "../../components/ui";
import type { ContentItem, Instance } from "../../lib/api";
import { api } from "../../lib/api";

function Row({ item, action }: { item: ContentItem; action?: React.ReactNode }) {
  const m = item.metadata;
  return (
    <div className="flex items-center gap-3 rounded-md border border-border bg-surface px-3 py-2">
      {item.icon_url ? (
        <img src={item.icon_url} alt="" className="h-8 w-8 rounded bg-surface-3 object-contain" />
      ) : (
        <div className="h-8 w-8 rounded bg-surface-3" />
      )}
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium">{m.display_name}</div>
        <div className="truncate text-[11px] text-muted">
          {m.version && `v${m.version} · `}
          {item.file}
        </div>
      </div>
      {action}
    </div>
  );
}

export function CompareView({ instances }: { instances: Instance[] }) {
  const qc = useQueryClient();
  const [aId, setAId] = useState(instances[0]?.id ?? "");
  const [bId, setBId] = useState(instances[1]?.id ?? "");

  const query = useQuery({
    queryKey: ["compare", aId, bId],
    queryFn: () => api.compare(aId, bId),
    enabled: Boolean(aId && bId && aId !== bId),
  });

  const copy = useMutation({
    mutationFn: ({ from, to, file }: { from: string; to: string; file: string }) =>
      api.copy(from, to, file),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ["compare"] });
      qc.invalidateQueries({ queryKey: ["content"] });
    },
  });

  const nameOf = (id: string) => instances.find((i) => i.id === id)?.name ?? "?";

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-3">
        <Select value={aId} onChange={(e) => setAId(e.target.value)}>
          {instances.map((i) => (
            <option key={i.id} value={i.id}>
              {i.name}
            </option>
          ))}
        </Select>
        <ArrowLeftRight size={15} className="text-muted" />
        <Select value={bId} onChange={(e) => setBId(e.target.value)}>
          {instances.map((i) => (
            <option key={i.id} value={i.id}>
              {i.name}
            </option>
          ))}
        </Select>
        {query.data && (
          <span className="ml-2 text-xs text-muted">
            {query.data.only_in_a.length + query.data.only_in_b.length +
              query.data.version_diffs.length}{" "}
            diferenças
          </span>
        )}
      </div>

      {aId === bId && (
        <div className="p-6 text-sm text-muted">Selecione duas instâncias diferentes.</div>
      )}
      {query.isLoading && <Spinner />}
      {query.isError && (
        <div className="p-6 text-sm text-danger">Erro: {String(query.error)}</div>
      )}

      {query.data && (
        <div className="grid gap-6 p-4 lg:grid-cols-2">
          <section>
            <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold">
              Somente em {nameOf(aId)} <Badge tone="orange">{query.data.only_in_a.length}</Badge>
            </h3>
            <div className="space-y-1.5">
              {query.data.only_in_a.map((item) => (
                <Row
                  key={item.file}
                  item={item}
                  action={
                    <Button
                      variant="default"
                      onClick={() => copy.mutate({ from: aId, to: bId, file: item.file })}
                      disabled={copy.isPending}
                    >
                      <Copy size={13} /> Copiar
                    </Button>
                  }
                />
              ))}
            </div>
          </section>

          <section>
            <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold">
              Somente em {nameOf(bId)} <Badge tone="orange">{query.data.only_in_b.length}</Badge>
            </h3>
            <div className="space-y-1.5">
              {query.data.only_in_b.map((item) => (
                <Row
                  key={item.file}
                  item={item}
                  action={
                    <Button
                      variant="default"
                      onClick={() => copy.mutate({ from: bId, to: aId, file: item.file })}
                      disabled={copy.isPending}
                    >
                      <Copy size={13} /> Copiar
                    </Button>
                  }
                />
              ))}
            </div>
          </section>

          {query.data.version_diffs.length > 0 && (
            <section className="lg:col-span-2">
              <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold">
                Versões diferentes <Badge tone="blue">{query.data.version_diffs.length}</Badge>
              </h3>
              <div className="space-y-1.5">
                {query.data.version_diffs.map((d) => (
                  <div
                    key={d.content_id}
                    className="flex items-center gap-3 rounded-md border border-border bg-surface px-3 py-2 text-sm"
                  >
                    <span className="font-medium">{d.content_id}</span>
                    <span className="text-muted">
                      {nameOf(aId)}: v{d.a.version} · {nameOf(bId)}: v{d.b.version}
                    </span>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
