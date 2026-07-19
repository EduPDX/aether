import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Archive,
  CalendarClock,
  Clock,
  Download,
  HardDrive,
  Info,
  RotateCcw,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import { useState } from "react";
import { Badge, Button, Input, Panel, Select, Spinner, StatTile } from "../../components/ui";
import type { BackupEntry, BackupSchedule, Instance } from "../../lib/api";
import { api, can, formatBytes, getAccessToken } from "../../lib/api";
import { useAuth } from "../auth/AuthGate";

const AGENDA: { valor: BackupSchedule; label: string }[] = [
  { valor: "off", label: "Desligado" },
  { valor: "hourly", label: "A cada hora" },
  { valor: "daily", label: "Diariamente" },
  { valor: "weekly", label: "Semanalmente" },
];

function quando(iso: string): string {
  const d = new Date(iso);
  const minutos = Math.round((Date.now() - d.getTime()) / 60000);
  if (minutos < 1) return "agora";
  if (minutos < 60) return `há ${minutos} min`;
  const horas = Math.round(minutos / 60);
  if (horas < 24) return `há ${horas} h`;
  return `há ${Math.round(horas / 24)} dias`;
}

export function BackupsView({ instance }: { instance: Instance }) {
  const qc = useQueryClient();
  const { user } = useAuth();
  const podeEscrever = can(user, "backups.write");
  const [nota, setNota] = useState("");
  const [erro, setErro] = useState("");
  const [aviso, setAviso] = useState("");

  const query = useQuery({
    queryKey: ["backups", instance.id],
    queryFn: () => api.backups(instance.id),
  });

  const invalidar = () => qc.invalidateQueries({ queryKey: ["backups", instance.id] });
  const falhou = (e: unknown) => setErro(String(e instanceof Error ? e.message : e));

  const criar = useMutation({
    mutationFn: () => api.createBackup(instance.id, nota),
    onSuccess: () => {
      setNota("");
      setErro("");
      invalidar();
    },
    onError: falhou,
  });

  const apagar = useMutation({
    mutationFn: (id: string) => api.deleteBackup(instance.id, id),
    onSuccess: invalidar,
    onError: falhou,
  });

  const restaurar = useMutation({
    mutationFn: (id: string) => api.restoreBackup(instance.id, id),
    onSuccess: (r) => {
      setErro("");
      setAviso(
        `${r.restored_files} arquivo(s) restaurado(s). O estado anterior foi guardado num backup de segurança.`,
      );
      invalidar();
    },
    onError: falhou,
  });

  const agendar = useMutation({
    mutationFn: ({ schedule, keep }: { schedule: BackupSchedule; keep: number }) =>
      api.setBackupPolicy(instance.id, schedule, keep),
    onSuccess: invalidar,
    onError: falhou,
  });

  async function baixar(b: BackupEntry) {
    const res = await fetch(api.backupDownloadUrl(instance.id, b.id), {
      headers: { Authorization: `Bearer ${getAccessToken()}` },
    });
    if (!res.ok) return falhou(new Error(`falha ao baixar (${res.status})`));
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = b.file_name;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  if (query.isLoading) return <Spinner />;
  if (query.isError)
    return <div className="p-6 text-sm text-danger">Erro ao listar backups: {String(query.error)}</div>;

  const { backups, policy, spec } = query.data!;
  const total = backups.reduce((s, b) => s + b.size_bytes, 0);
  const ultimo = backups[0];
  const rodando = instance.state === "running";

  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="mx-auto flex w-full max-w-[1900px] flex-col gap-4">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatTile
            icon={<Archive size={14} />}
            label="Backups"
            value={String(backups.length)}
            sub={backups.length ? "guardados nesta instância" : "nenhum ainda"}
            tone={backups.length === 0 ? "danger" : undefined}
          />
          <StatTile
            icon={<Clock size={14} />}
            label="Mais recente"
            value={ultimo ? quando(ultimo.created_at) : "—"}
            sub={ultimo ? new Date(ultimo.created_at).toLocaleString("pt-BR") : "nunca"}
            tone={!ultimo ? "danger" : undefined}
          />
          <StatTile
            icon={<HardDrive size={14} />}
            label="Espaço usado"
            value={formatBytes(total)}
            sub="somando todos os arquivos"
          />
          <StatTile
            icon={<CalendarClock size={14} />}
            label="Automático"
            value={AGENDA.find((a) => a.valor === policy.schedule)?.label ?? policy.schedule}
            sub={policy.schedule === "off" ? "nada agendado" : `mantendo ${policy.keep}`}
            tone={policy.schedule === "off" ? "warn" : "accent"}
          />
        </div>

        {erro && <p className="text-sm text-danger">{erro}</p>}
        {aviso && <p className="text-sm text-accent">{aviso}</p>}

        {podeEscrever && (
          <Panel
            title="Novo backup"
            icon={<Archive size={15} />}
            hint={spec.summary}
            aside={
              <span className="flex items-center gap-2">
                <Input
                  className="w-56"
                  placeholder="Anotação (opcional)"
                  value={nota}
                  maxLength={200}
                  onChange={(e) => setNota(e.target.value)}
                />
                <Button
                  variant="primary"
                  disabled={criar.isPending}
                  onClick={() => criar.mutate()}
                >
                  <Archive size={14} /> {criar.isPending ? "Salvando…" : "Fazer backup"}
                </Button>
              </span>
            }
          >
            {rodando && (
              <p className="flex items-start gap-2 text-xs text-muted">
                <Info size={14} className="mt-px shrink-0" />
                O servidor está no ar. O Aether envia <code>save-all flush</code> e{" "}
                <code>save-off</code> antes de copiar e <code>save-on</code> depois, para o mundo
                não ser gravado no meio da cópia.
              </p>
            )}
          </Panel>
        )}

        <Panel
          title="Backup automático"
          icon={<CalendarClock size={15} />}
          hint="Backups manuais nunca são apagados pela retenção — só os automáticos."
          aside={
            podeEscrever && (
              <span className="flex items-center gap-2">
                <Select
                  className="py-1 text-xs"
                  value={policy.schedule}
                  onChange={(e) =>
                    agendar.mutate({
                      schedule: e.target.value as BackupSchedule,
                      keep: policy.keep,
                    })
                  }
                >
                  {AGENDA.map((a) => (
                    <option key={a.valor} value={a.valor}>
                      {a.label}
                    </option>
                  ))}
                </Select>
                <label className="flex items-center gap-1.5 text-xs text-muted">
                  <span>manter</span>
                  <Input
                    type="number"
                    className="w-16 py-1"
                    min={0}
                    max={365}
                    defaultValue={policy.keep}
                    onBlur={(e) =>
                      agendar.mutate({
                        schedule: policy.schedule,
                        keep: Number(e.target.value) || 0,
                      })
                    }
                  />
                </label>
              </span>
            )
          }
        >
          <p className="text-xs text-muted">
            {policy.schedule === "off"
              ? "Nenhum backup automático está agendado para esta instância."
              : `Um backup é criado ${AGENDA.find((a) => a.valor === policy.schedule)?.label.toLowerCase()}, mantendo os ${policy.keep} mais recentes.`}
          </p>
        </Panel>

        <Panel title="Backups guardados" icon={<ShieldCheck size={15} />}>
          {backups.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted">
              Nenhum backup ainda. Faça o primeiro antes de mexer em qualquer coisa importante.
            </p>
          ) : (
            <div className="space-y-1.5">
              {backups.map((b) => (
                <div
                  key={b.id}
                  className="flex flex-wrap items-center gap-3 rounded-md border border-border bg-surface-2 px-3 py-2"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-medium">
                        {new Date(b.created_at).toLocaleString("pt-BR")}
                      </span>
                      <Badge tone={b.kind === "manual" ? "blue" : "neutral"}>
                        {b.kind === "manual" ? "manual" : "automático"}
                      </Badge>
                      <span className="text-xs text-muted">{quando(b.created_at)}</span>
                    </div>
                    <div className="truncate text-[11px] text-muted">
                      {formatBytes(b.size_bytes)} · {b.file_name}
                      {b.note && ` · ${b.note}`}
                    </div>
                  </div>

                  <span className="flex gap-1.5">
                    <Button onClick={() => baixar(b)} title="Baixar o .zip">
                      <Download size={13} />
                    </Button>
                    {podeEscrever && (
                      <>
                        <Button
                          disabled={restaurar.isPending || rodando}
                          title={
                            rodando
                              ? "Pare o servidor para restaurar"
                              : "Restaurar este backup sobre a instância"
                          }
                          onClick={() => {
                            if (
                              confirm(
                                `Restaurar o backup de ${new Date(b.created_at).toLocaleString("pt-BR")}?\n\n` +
                                  "Os arquivos atuais serão sobrescritos. Um backup de segurança do estado de agora será criado antes.",
                              )
                            )
                              restaurar.mutate(b.id);
                          }}
                        >
                          <RotateCcw size={13} /> Restaurar
                        </Button>
                        <Button
                          variant="danger"
                          disabled={apagar.isPending}
                          onClick={() => {
                            if (confirm(`Apagar o backup ${b.file_name}? Isso não tem volta.`))
                              apagar.mutate(b.id);
                          }}
                        >
                          <Trash2 size={13} />
                        </Button>
                      </>
                    )}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="O que entra no backup" icon={<Info size={15} />} hint={spec.summary}>
          <div className="grid gap-4 sm:grid-cols-2 text-xs">
            <div>
              <div className="mb-1.5 font-semibold">Incluído</div>
              <ul className="space-y-0.5 font-mono text-[11px] text-muted">
                {spec.include.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            </div>
            <div>
              <div className="mb-1.5 font-semibold">Excluído</div>
              <ul className="space-y-0.5 font-mono text-[11px] text-muted">
                {spec.exclude.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            </div>
          </div>
        </Panel>
      </div>
    </div>
  );
}
