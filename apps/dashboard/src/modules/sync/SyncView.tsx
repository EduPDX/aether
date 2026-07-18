import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Plus, Trash2, UploadCloud } from "lucide-react";
import { useState } from "react";
import { Badge, Button, Input, Modal, Select, Spinner } from "../../components/ui";
import type { Instance, SyncProfileOut, SyncRule, SyncRules } from "../../lib/api";
import { api, formatBytes } from "../../lib/api";

/** Padrão correto para jogadores: entrega o PERFIL DE CLIENTE
 *  (aether-client/mods) na pasta mods/ do PC deles. */
const PRESET_CLIENTE: SyncRules = {
  rules: [
    {
      dir: "aether-client/mods",
      target: "mods",
      patterns: ["*.jar"],
      recursive: true,
      action: "require",
    },
    { dir: "config", target: "config", patterns: ["*"], recursive: true, action: "optional" },
  ],
  exclude: ["*.bak", "*.tmp"],
};

/** Espelha a pasta do servidor (útil para réplicas, não para jogadores). */
const PRESET_SERVIDOR: SyncRules = {
  rules: [{ dir: "mods", target: "mods", patterns: ["*.jar"], recursive: true, action: "require" }],
  exclude: ["*.bak", "*.tmp"],
};

function ruleSummary(rules: SyncRules): string {
  return rules.rules
    .map((r) => {
      const dest = r.target ?? r.dir;
      const seta = dest !== r.dir ? ` → ${dest}/` : "";
      return `${r.dir}/${seta} (${r.patterns.join(", ")}) ${
        r.action === "require" ? "obrigatório" : "opcional"
      }`;
    })
    .join(" · ");
}

export function SyncView({ instance }: { instance: Instance }) {
  const qc = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState("");

  const query = useQuery({
    queryKey: ["sync", instance.id],
    queryFn: () => api.syncProfiles(instance.id),
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["sync", instance.id] });

  const publish = useMutation({
    mutationFn: (pid: string) => api.publishSyncProfile(instance.id, pid),
    onSuccess: invalidate,
    onError: (e) => setError(String(e)),
  });

  const remove = useMutation({
    mutationFn: (pid: string) => api.deleteSyncProfile(instance.id, pid),
    onSuccess: invalidate,
    onError: (e) => setError(String(e)),
  });

  function copyCommand(profile: SyncProfileOut) {
    const cmd = `aether-sync ${location.origin} ${profile.id} --dir <pasta-do-minecraft>`;
    navigator.clipboard.writeText(cmd);
    setCopied(profile.id);
    setTimeout(() => setCopied(""), 2000);
  }

  if (query.isLoading) return <Spinner />;

  const profiles = query.data ?? [];

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <div className="flex items-center gap-3 border-b border-border px-4 py-2">
        <span className="text-sm font-semibold">Perfis de sincronização</span>
        <span className="text-xs text-muted">
          O que os jogadores devem espelhar desta instância
        </span>
        {error && <span className="truncate text-xs text-danger">{error}</span>}
        <span className="ml-auto">
          <Button variant="primary" onClick={() => setCreateOpen(true)}>
            <Plus size={14} /> Novo perfil
          </Button>
        </span>
      </div>

      <div className="mx-auto w-full max-w-3xl space-y-3 p-4">
        {profiles.length === 0 && (
          <div className="rounded-lg border border-border bg-surface p-6 text-center text-sm text-muted">
            Nenhum perfil ainda. Crie um para gerar o manifesto assinado que o launcher e o{" "}
            <code>aether-sync</code> consomem.
          </div>
        )}

        {profiles.map((p) => (
          <div key={p.id} className="rounded-lg border border-border bg-surface p-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold">{p.name}</span>
              <Badge tone={p.channel === "stable" ? "green" : "blue"}>{p.channel}</Badge>
              {p.published_at ? (
                <Badge tone="neutral" title={p.published_at}>
                  {p.files} arquivos · {formatBytes(p.total_size ?? 0)}
                </Badge>
              ) : (
                <Badge tone="orange">nunca publicado</Badge>
              )}
              <span className="ml-auto flex gap-1.5">
                <Button
                  variant="primary"
                  disabled={publish.isPending}
                  onClick={() => publish.mutate(p.id)}
                  title="Gera e assina o manifesto com o estado atual dos arquivos"
                >
                  <UploadCloud size={13} />
                  {publish.isPending && publish.variables === p.id
                    ? "Publicando…"
                    : p.published_at
                      ? "Republicar"
                      : "Publicar"}
                </Button>
                {p.published_at && (
                  <Button variant="ghost" onClick={() => copyCommand(p)} title="Copiar comando">
                    <Copy size={13} /> {copied === p.id ? "Copiado!" : "Comando"}
                  </Button>
                )}
                <Button
                  variant="danger"
                  onClick={() => {
                    if (confirm(`Excluir o perfil "${p.name}"?`)) remove.mutate(p.id);
                  }}
                >
                  <Trash2 size={13} />
                </Button>
              </span>
            </div>
            <p className="mt-2 text-xs text-muted">{ruleSummary(p.rules)}</p>
            {p.rules.exclude.length > 0 && (
              <p className="text-[11px] text-muted/70">Exclui: {p.rules.exclude.join(", ")}</p>
            )}
            {p.published_at && (
              <p className="mt-1 text-[11px] text-muted/70">
                Manifesto público: <code>/api/v1/public/sync/{p.id}</code>
              </p>
            )}
          </div>
        ))}
      </div>

      <CreateProfileDialog
        instance={instance}
        open={createOpen}
        onClose={() => setCreateOpen(false)}
      />
    </div>
  );
}

function CreateProfileDialog({
  instance,
  open,
  onClose,
}: {
  instance: Instance;
  open: boolean;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [name, setName] = useState("Jogadores");
  const [channel, setChannel] = useState("stable");
  const [rules, setRules] = useState<SyncRules>(PRESET_CLIENTE);
  const [error, setError] = useState("");

  const create = useMutation({
    mutationFn: () => api.createSyncProfile(instance.id, { name, channel, rules }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sync", instance.id] });
      setError("");
      onClose();
    },
    onError: (e) => setError(String(e)),
  });

  function setRule(i: number, patch: Partial<SyncRule>) {
    setRules((prev) => ({
      ...prev,
      rules: prev.rules.map((r, idx) => (idx === i ? { ...r, ...patch } : r)),
    }));
  }

  return (
    <Modal open={open} onClose={onClose} title="Novo perfil de sincronização">
      <div className="space-y-3">
        <div className="flex gap-2">
          <div className="flex-1">
            <label className="mb-1 block text-xs text-muted">Nome</label>
            <Input className="w-full" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs text-muted">Canal</label>
            <Select value={channel} onChange={(e) => setChannel(e.target.value)}>
              <option value="stable">stable</option>
              <option value="beta">beta</option>
            </Select>
          </div>
        </div>

        <div>
          <label className="mb-1 block text-xs text-muted">Modelo</label>
          <div className="flex gap-2">
            <Button variant="default" onClick={() => setRules(PRESET_CLIENTE)}>
              Perfil de cliente
            </Button>
            <Button variant="ghost" onClick={() => setRules(PRESET_SERVIDOR)}>
              Espelhar servidor
            </Button>
          </div>
          <p className="mt-1 text-[11px] text-muted/80">
            O perfil de cliente entrega os mods de <code>aether-client/mods</code> na pasta{" "}
            <code>mods</code> do jogador — é o que o launcher deve usar.
          </p>
        </div>
        <div>
          <label className="mb-1 block text-xs text-muted">
            Regras <span className="text-muted/70">(origem no servidor → destino no cliente)</span>
          </label>
          <div className="space-y-1.5">
            {rules.rules.map((rule, i) => (
              <div key={i} className="flex items-center gap-1.5">
                <Input
                  className="w-32 text-xs"
                  value={rule.dir}
                  onChange={(e) => setRule(i, { dir: e.target.value })}
                  placeholder="origem"
                />
                <span className="text-muted">→</span>
                <Input
                  className="w-24 text-xs"
                  value={rule.target ?? ""}
                  onChange={(e) => setRule(i, { target: e.target.value || null })}
                  placeholder="destino"
                />
                <Input
                  className="flex-1"
                  value={rule.patterns.join(", ")}
                  onChange={(e) =>
                    setRule(i, {
                      patterns: e.target.value.split(",").map((s) => s.trim()).filter(Boolean),
                    })
                  }
                  placeholder="*.jar"
                />
                <Select
                  value={rule.action}
                  onChange={(e) =>
                    setRule(i, { action: e.target.value as SyncRule["action"] })
                  }
                >
                  <option value="require">obrigatório</option>
                  <option value="optional">opcional</option>
                </Select>
                <button
                  className="cursor-pointer p-1 text-muted hover:text-danger"
                  onClick={() =>
                    setRules((prev) => ({
                      ...prev,
                      rules: prev.rules.filter((_, idx) => idx !== i),
                    }))
                  }
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
          </div>
          <button
            className="mt-1.5 cursor-pointer text-xs text-accent"
            onClick={() =>
              setRules((prev) => ({
                ...prev,
                rules: [
                  ...prev.rules,
                  { dir: "", target: "", patterns: ["*"], recursive: true, action: "require" },
                ],
              }))
            }
          >
            + adicionar regra
          </button>
        </div>

        <div>
          <label className="mb-1 block text-xs text-muted">Excluir (padrões, vírgula)</label>
          <Input
            className="w-full"
            value={rules.exclude.join(", ")}
            onChange={(e) =>
              setRules((prev) => ({
                ...prev,
                exclude: e.target.value.split(",").map((s) => s.trim()).filter(Boolean),
              }))
            }
          />
        </div>

        {error && <p className="text-xs text-danger">{error}</p>}
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            variant="primary"
            disabled={!name.trim() || rules.rules.length === 0 || create.isPending}
            onClick={() => create.mutate()}
          >
            Criar
          </Button>
        </div>
      </div>
    </Modal>
  );
}
