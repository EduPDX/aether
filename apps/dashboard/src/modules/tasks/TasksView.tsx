import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, MessageSquare, Play, Plus, RotateCw, Trash2 } from "lucide-react";
import { useState } from "react";
import { useDialog } from "../../components/Dialog";
import { Badge, Button, Input, Panel, Select, Spinner, StatTile, Switch } from "../../components/ui";
import type { Instance, ScheduledTask, TaskInput, TaskKind, TaskSchedule } from "../../lib/api";
import { api, can } from "../../lib/api";
import { useAuth } from "../auth/AuthGate";

const DIAS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"];

const VAZIA: TaskInput = {
  kind: "restart",
  schedule: "daily",
  at_hour: 4,
  at_minute: 0,
  weekday: 0,
  enabled: true,
  command: "",
  warn_minutes: 5,
};

function quando(iso: string | null): string {
  if (!iso) return "nunca executada";
  const d = new Date(iso);
  const min = Math.round((Date.now() - d.getTime()) / 60000);
  if (min < 60) return `há ${min} min`;
  if (min < 1440) return `há ${Math.round(min / 60)} h`;
  return `há ${Math.round(min / 1440)} dias`;
}

export function TasksView({ instance }: { instance: Instance }) {
  const qc = useQueryClient();
  const dialog = useDialog();
  const { user } = useAuth();
  const podeEditar = can(user, "power.use");

  const [rascunho, setRascunho] = useState<TaskInput | null>(null);
  const [erro, setErro] = useState("");

  const query = useQuery({
    queryKey: ["tarefas", instance.id],
    queryFn: () => api.tasks(instance.id),
  });

  const invalidar = () => qc.invalidateQueries({ queryKey: ["tarefas", instance.id] });
  const falhou = (e: unknown) => setErro(String(e instanceof Error ? e.message : e));

  const criar = useMutation({
    mutationFn: (body: TaskInput) => api.createTask(instance.id, body),
    onSuccess: () => {
      setRascunho(null);
      setErro("");
      invalidar();
    },
    onError: falhou,
  });

  const atualizar = useMutation({
    mutationFn: ({ id, body }: { id: string; body: TaskInput }) =>
      api.updateTask(instance.id, id, body),
    onSuccess: invalidar,
    onError: falhou,
  });

  const remover = useMutation({
    mutationFn: (id: string) => api.deleteTask(instance.id, id),
    onSuccess: invalidar,
    onError: falhou,
  });

  const executar = useMutation({
    mutationFn: (id: string) => api.runTask(instance.id, id),
    onSuccess: () => {
      setErro("");
      invalidar();
    },
    onError: falhou,
  });

  if (query.isLoading) return <Spinner />;
  if (query.isError)
    return <div className="p-6 text-sm text-danger">Erro ao listar: {String(query.error)}</div>;

  const tarefas = query.data ?? [];
  const ativas = tarefas.filter((t) => t.enabled);

  function paraInput(t: ScheduledTask): TaskInput {
    return {
      kind: t.kind,
      schedule: t.schedule,
      at_hour: t.at_hour,
      at_minute: t.at_minute,
      weekday: t.weekday,
      enabled: t.enabled,
      command: t.command,
      warn_minutes: t.warn_minutes,
    };
  }

  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="mx-auto flex w-full max-w-[1900px] flex-col gap-4">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatTile
            icon={<CalendarClock size={14} />}
            label="Agendamentos"
            value={String(tarefas.length)}
            sub={tarefas.length ? `${ativas.length} ativo(s)` : "nenhum criado"}
          />
          <StatTile
            icon={<RotateCw size={14} />}
            label="Reinícios"
            value={String(tarefas.filter((t) => t.kind === "restart").length)}
            sub="tarefas de reinício"
          />
          <StatTile
            icon={<MessageSquare size={14} />}
            label="Comandos"
            value={String(tarefas.filter((t) => t.kind === "command").length)}
            sub="enviados ao console"
          />
          <StatTile
            icon={<Play size={14} />}
            label="Última execução"
            value={
              tarefas.some((t) => t.last_run)
                ? quando(
                    tarefas
                      .filter((t) => t.last_run)
                      .sort((a, b) => (a.last_run! < b.last_run! ? 1 : -1))[0].last_run,
                  )
                : "—"
            }
            sub="de qualquer tarefa"
          />
        </div>

        {erro && <p className="text-sm text-danger">{erro}</p>}

        <Panel
          title="Tarefas agendadas"
          icon={<CalendarClock size={15} />}
          hint="O horário é o do servidor. Uma tarefa perdida por queda do Core roda ao voltar, se ainda estiver dentro da janela — depois disso é pulada."
          aside={
            podeEditar && (
              <Button variant="primary" onClick={() => setRascunho({ ...VAZIA })}>
                <Plus size={14} /> Nova tarefa
              </Button>
            )
          }
        >
          {tarefas.length === 0 && !rascunho && (
            <p className="py-6 text-center text-sm text-muted">
              Nenhum agendamento. Um reinício diário de madrugada costuma resolver travamento
              acumulado em servidor modado.
            </p>
          )}

          <div className="space-y-1.5">
            {tarefas.map((t) => (
              <div
                key={t.id}
                className={`flex flex-wrap items-center gap-3 rounded-md border border-border bg-surface-2 px-3 py-2 ${
                  t.enabled ? "" : "opacity-60"
                }`}
              >
                {t.kind === "restart" ? (
                  <RotateCw size={16} className="shrink-0 text-warn" />
                ) : (
                  <MessageSquare size={16} className="shrink-0 text-info" />
                )}
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium">{t.description}</div>
                  <div className="text-[11px] text-muted">
                    {quando(t.last_run)}
                    {t.kind === "restart" &&
                      t.warn_minutes > 0 &&
                      ` · avisa no chat ${t.warn_minutes} min antes`}
                  </div>
                </div>
                {!t.enabled && <Badge tone="neutral">desligada</Badge>}

                {podeEditar && (
                  <span className="flex items-center gap-2">
                    <Switch
                      checked={t.enabled}
                      title={t.enabled ? "Desativar" : "Ativar"}
                      onChange={() =>
                        atualizar.mutate({
                          id: t.id,
                          body: { ...paraInput(t), enabled: !t.enabled },
                        })
                      }
                    />
                    <Button
                      title="Executar agora, sem esperar o horário"
                      disabled={executar.isPending}
                      onClick={async () => {
                        const ok = await dialog.confirm({
                          title: "Executar agora",
                          message: `“${t.description}” será executada imediatamente.`,
                          confirmText: "Executar",
                          tone: t.kind === "restart" ? "danger" : "default",
                        });
                        if (ok) executar.mutate(t.id);
                      }}
                    >
                      <Play size={13} />
                    </Button>
                    <Button
                      variant="danger"
                      onClick={async () => {
                        const ok = await dialog.confirm({
                          title: "Remover agendamento",
                          message: t.description,
                          confirmText: "Remover",
                          tone: "danger",
                        });
                        if (ok) remover.mutate(t.id);
                      }}
                    >
                      <Trash2 size={13} />
                    </Button>
                  </span>
                )}
              </div>
            ))}
          </div>

          {rascunho && (
            <div className="mt-3 rounded-lg border border-accent/50 bg-surface-2 p-3">
              <div className="flex flex-wrap items-end gap-3">
                <label className="text-xs">
                  <span className="mb-1 block text-muted">O que fazer</span>
                  <Select
                    value={rascunho.kind}
                    onChange={(e) =>
                      setRascunho({ ...rascunho, kind: e.target.value as TaskKind })
                    }
                  >
                    <option value="restart">Reiniciar o servidor</option>
                    <option value="command">Enviar um comando</option>
                  </Select>
                </label>

                <label className="text-xs">
                  <span className="mb-1 block text-muted">Quando</span>
                  <Select
                    value={rascunho.schedule}
                    onChange={(e) =>
                      setRascunho({ ...rascunho, schedule: e.target.value as TaskSchedule })
                    }
                  >
                    <option value="daily">Todo dia</option>
                    <option value="weekly">Toda semana</option>
                    <option value="hourly">Toda hora</option>
                  </Select>
                </label>

                {rascunho.schedule === "weekly" && (
                  <label className="text-xs">
                    <span className="mb-1 block text-muted">Dia</span>
                    <Select
                      value={String(rascunho.weekday)}
                      onChange={(e) =>
                        setRascunho({ ...rascunho, weekday: Number(e.target.value) })
                      }
                    >
                      {DIAS.map((d, i) => (
                        <option key={d} value={i}>
                          {d}
                        </option>
                      ))}
                    </Select>
                  </label>
                )}

                <label className="text-xs">
                  <span className="mb-1 block text-muted">
                    {rascunho.schedule === "hourly" ? "Minuto" : "Horário"}
                  </span>
                  <span className="flex items-center gap-1">
                    {rascunho.schedule !== "hourly" && (
                      <>
                        <Input
                          type="number"
                          className="w-16"
                          min={0}
                          max={23}
                          value={rascunho.at_hour}
                          onChange={(e) =>
                            setRascunho({ ...rascunho, at_hour: Number(e.target.value) })
                          }
                        />
                        <span className="text-muted">:</span>
                      </>
                    )}
                    <Input
                      type="number"
                      className="w-16"
                      min={0}
                      max={59}
                      value={rascunho.at_minute}
                      onChange={(e) =>
                        setRascunho({ ...rascunho, at_minute: Number(e.target.value) })
                      }
                    />
                  </span>
                </label>

                {rascunho.kind === "command" ? (
                  <label className="min-w-56 flex-1 text-xs">
                    <span className="mb-1 block text-muted">Comando</span>
                    <Input
                      className="w-full"
                      placeholder="say bom dia"
                      value={rascunho.command}
                      onChange={(e) => setRascunho({ ...rascunho, command: e.target.value })}
                    />
                  </label>
                ) : (
                  <label className="text-xs">
                    <span className="mb-1 block text-muted">Avisar antes (min)</span>
                    <Input
                      type="number"
                      className="w-20"
                      min={0}
                      max={30}
                      value={rascunho.warn_minutes}
                      onChange={(e) =>
                        setRascunho({ ...rascunho, warn_minutes: Number(e.target.value) })
                      }
                    />
                  </label>
                )}

                <span className="ml-auto flex gap-2">
                  <Button variant="ghost" onClick={() => setRascunho(null)}>
                    Cancelar
                  </Button>
                  <Button
                    variant="primary"
                    disabled={criar.isPending}
                    onClick={() => criar.mutate(rascunho)}
                  >
                    Criar
                  </Button>
                </span>
              </div>

              {rascunho.kind === "command" && (
                <p className="mt-2 text-[11px] text-muted">
                  O servidor precisa estar no ar para receber o comando. Comandos que derrubam o
                  servidor (<code>stop</code>) são recusados — para isso existe a tarefa de
                  reinício, que sobe de volta.
                </p>
              )}
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}
