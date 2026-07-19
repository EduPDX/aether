import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, History, KeyRound, Plus, Shield, Trash2, X } from "lucide-react";
import { useState } from "react";
import { useDialog } from "../../components/Dialog";
import { Badge, Button, Input, Modal, Select, Spinner } from "../../components/ui";
import { api, can } from "../../lib/api";
import { useAuth } from "../auth/AuthGate";

const ROLE_TONE: Record<string, "green" | "blue" | "orange" | "neutral"> = {
  owner: "green",
  admin: "blue",
  moderator: "orange",
  viewer: "neutral",
};

const ROLE_DESC: Record<string, string> = {
  owner: "Controle total, incluindo usuários",
  admin: "Gerencia servidor, mods, arquivos e sync",
  moderator: "Liga/desliga e usa o console",
  viewer: "Somente leitura",
};

export function UsersView() {
  const qc = useQueryClient();
  const { user: me } = useAuth();
  const dialog = useDialog();
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");

  const query = useQuery({ queryKey: ["users"], queryFn: api.users });
  const remove = useMutation({
    mutationFn: (id: string) => api.deleteUser(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
    onError: (e) => setError(String(e)),
  });

  if (query.isLoading) return <Spinner />;
  if (query.isError)
    return (
      <div className="p-6 text-sm text-muted">
        Apenas o dono da instalação pode gerenciar usuários.
      </div>
    );

  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="mx-auto w-full max-w-3xl">
        <div className="mb-3 flex items-center gap-3">
          <h2 className="text-sm font-semibold">Usuários</h2>
          <span className="text-xs text-muted">Quem pode acessar o painel e com qual poder</span>
          <span className="ml-auto">
            <Button variant="primary" onClick={() => setOpen(true)}>
              <Plus size={14} /> Novo usuário
            </Button>
          </span>
        </div>
        {error && <p className="mb-2 text-xs text-danger">{error}</p>}

        <div className="space-y-2">
          {(query.data ?? []).map((u) => (
            <div
              key={u.id}
              className="flex items-center gap-3 rounded-lg border border-border bg-surface px-4 py-3"
            >
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent-dim text-sm font-bold text-black">
                {u.username.charAt(0).toUpperCase()}
              </span>
              <div className="min-w-0">
                <div className="truncate text-sm font-medium">
                  {u.username}
                  {u.id === me?.id && <span className="ml-2 text-[11px] text-muted">(você)</span>}
                </div>
                <div className="text-[11px] text-muted">{ROLE_DESC[u.role] ?? u.role}</div>
              </div>
              <Badge tone={ROLE_TONE[u.role] ?? "neutral"}>{u.role}</Badge>
              <span className="ml-auto">
                {u.role !== "owner" && u.id !== me?.id && (
                  <Button
                    variant="danger"
                    onClick={async () => {
                      const ok = await dialog.confirm({
                        title: "Remover usuário",
                        message: `“${u.username}” perde o acesso ao painel imediatamente.`,
                        confirmText: "Remover",
                        tone: "danger",
                      });
                      if (ok) remove.mutate(u.id);
                    }}
                  >
                    <Trash2 size={13} />
                  </Button>
                )}
              </span>
            </div>
          ))}
        </div>
      </div>
      <CreateUserDialog open={open} onClose={() => setOpen(false)} />
    </div>
  );
}

function CreateUserDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("moderator");
  const [error, setError] = useState("");

  const create = useMutation({
    mutationFn: () => api.createUser(username.trim(), password, role),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      setUsername("");
      setPassword("");
      setError("");
      onClose();
    },
    onError: (e) => setError(String(e)),
  });

  return (
    <Modal open={open} onClose={onClose} title="Novo usuário">
      <div className="space-y-3">
        <div>
          <label className="mb-1 block text-xs text-muted">Usuário</label>
          <Input className="w-full" value={username} onChange={(e) => setUsername(e.target.value)} />
        </div>
        <div>
          <label className="mb-1 block text-xs text-muted">Senha (mín. 8 caracteres)</label>
          <Input
            className="w-full"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-muted">Papel</label>
          <Select className="w-full" value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="admin">admin — gerencia tudo do servidor</option>
            <option value="moderator">moderator — liga/desliga e console</option>
            <option value="viewer">viewer — somente leitura</option>
          </Select>
        </div>
        {error && <p className="text-xs text-danger">{error}</p>}
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            variant="primary"
            disabled={username.trim().length < 3 || password.length < 8 || create.isPending}
            onClick={() => create.mutate()}
          >
            Criar
          </Button>
        </div>
      </div>
    </Modal>
  );
}

export function AuditView() {
  const query = useQuery({ queryKey: ["audit"], queryFn: () => api.audit(200) });
  if (query.isLoading) return <Spinner />;
  if (query.isError)
    return <div className="p-6 text-sm text-muted">Você não tem permissão para ver a auditoria.</div>;

  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="mx-auto w-full max-w-4xl">
        <div className="mb-3 flex items-center gap-3">
          <h2 className="text-sm font-semibold">Auditoria</h2>
          <span className="text-xs text-muted">Tudo que alterou o sistema, e por quem</span>
        </div>
        <div className="overflow-hidden rounded-lg border border-border">
          <table className="w-full text-left text-xs">
            <thead className="bg-surface-2 text-muted">
              <tr>
                <th className="px-3 py-2 font-semibold">Quando</th>
                <th className="px-3 py-2 font-semibold">Usuário</th>
                <th className="px-3 py-2 font-semibold">Ação</th>
                <th className="px-3 py-2 font-semibold">Origem</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border bg-surface">
              {(query.data ?? []).map((e) => (
                <tr key={e.id} className="hover:bg-surface-2">
                  <td className="px-3 py-1.5 whitespace-nowrap text-muted">
                    {new Date(e.created_at).toLocaleString("pt-BR")}
                  </td>
                  <td className="px-3 py-1.5">{e.username ?? "—"}</td>
                  <td className="px-3 py-1.5 font-mono">{e.action}</td>
                  <td className="px-3 py-1.5 text-muted">{e.ip ?? "—"}</td>
                </tr>
              ))}
              {(query.data ?? []).length === 0 && (
                <tr>
                  <td colSpan={4} className="px-3 py-6 text-center text-muted">
                    Nada registrado ainda.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

/** O que cada permissão significa em português, na ordem em que é exibida. */
const CAPACIDADES: { perm: string; label: string }[] = [
  { perm: "instances.read", label: "Ver servidores e seus status" },
  { perm: "content.read", label: "Ver a lista de mods" },
  { perm: "content.write", label: "Adicionar, ativar e remover mods" },
  { perm: "power.use", label: "Ligar e desligar servidores" },
  { perm: "console.use", label: "Usar o console e enviar comandos" },
  { perm: "files.read", label: "Navegar pelos arquivos" },
  { perm: "files.write", label: "Editar, enviar e apagar arquivos" },
  { perm: "config.write", label: "Alterar configurações do servidor" },
  { perm: "sync.write", label: "Gerenciar perfis de sincronização" },
  { perm: "audit.read", label: "Ver o registro de auditoria" },
  { perm: "users.write", label: "Gerenciar usuários do painel" },
];

/** Perfil do usuário — exibido como uma seção das configurações. */
export function ProfileContent() {
  const { user } = useAuth();

  // O próprio usuário sempre pode ver a própria atividade; quem não tem
  // audit.read recebe 403 e a seção simplesmente não aparece.
  const podeAuditar = can(user, "audit.read");
  const atividade = useQuery({
    queryKey: ["audit", "me"],
    queryFn: () => api.audit(200),
    enabled: podeAuditar,
    retry: false,
  });

  const minhas = (atividade.data ?? []).filter((e) => e.username === user?.username).slice(0, 8);
  const permitidas = CAPACIDADES.filter((c) => can(user, c.perm));

  return (
    <div className="flex w-full flex-col gap-4">
      {/* Cabeçalho em faixa: o avatar em coluna estreita espremia o texto e
          quebrava "Controle total, incluindo usuários" no meio. */}
      <div className="flex flex-wrap items-center gap-5 rounded-xl border border-border bg-surface p-6">
        <span className="flex h-20 w-20 shrink-0 items-center justify-center rounded-full bg-accent-dim text-3xl font-bold text-black">
          {user?.username.charAt(0).toUpperCase()}
        </span>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2.5">
            <span className="text-2xl font-bold">{user?.username}</span>
            <Badge tone={ROLE_TONE[user?.role ?? ""] ?? "neutral"}>{user?.role}</Badge>
          </div>
          <p className="mt-1 text-sm text-muted">{ROLE_DESC[user?.role ?? ""]}</p>
        </div>
        <div className="ml-auto flex gap-8 text-sm">
          <div>
            <div className="text-[11px] font-semibold tracking-wider text-muted uppercase">
              Permissões
            </div>
            <div className="mt-1 text-2xl font-bold tabular-nums">
              {permitidas.length}
              <span className="text-base font-normal text-muted">/{CAPACIDADES.length}</span>
            </div>
          </div>
          <div>
            <div className="text-[11px] font-semibold tracking-wider text-muted uppercase">
              Sessão
            </div>
            <div className="mt-1 text-2xl font-bold text-accent">ativa</div>
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <div className="rounded-xl border border-border bg-surface p-5">
          <div className="flex items-center gap-2 text-base font-semibold">
            <Shield size={16} /> O que você pode fazer
          </div>
          {/* Coluna única: os rótulos são frases e em duas colunas estreitas
              elas quebravam em pontos arbitrários. */}
          <ul className="mt-3 space-y-1.5 text-sm">
            {CAPACIDADES.map((c) => {
              const ok = can(user, c.perm);
              return (
                <li
                  key={c.perm}
                  className={`flex items-start gap-2.5 rounded-md px-2 py-1.5 ${
                    ok ? "bg-surface-2 text-text" : "text-muted/70"
                  }`}
                >
                  {ok ? (
                    <Check size={15} className="mt-px shrink-0 text-accent" />
                  ) : (
                    <X size={15} className="mt-px shrink-0" />
                  )}
                  <span className={ok ? "" : "line-through decoration-muted/40"}>{c.label}</span>
                </li>
              );
            })}
          </ul>
        </div>

        <div className="flex flex-col gap-4">
          <div className="rounded-xl border border-border bg-surface p-5">
            <div className="flex items-center gap-2 text-base font-semibold">
              <KeyRound size={16} /> Sessão e acesso
            </div>
            <dl className="mt-3 space-y-2 text-sm">
              {[
                ["Renovação automática", "ativa"],
                ["Token de acesso expira em", "30 minutos"],
                ["Sessão completa dura", "7 dias"],
              ].map(([rotulo, valor]) => (
                <div
                  key={rotulo}
                  className="flex items-center justify-between gap-4 border-b border-border pb-2 last:border-0 last:pb-0"
                >
                  <dt className="text-muted">{rotulo}</dt>
                  <dd className="shrink-0 font-medium">{valor}</dd>
                </div>
              ))}
            </dl>
            <p className="mt-3 text-xs text-muted">
              Trocar a senha ainda não é possível pelo painel — peça ao dono da instalação.
            </p>
          </div>

          {podeAuditar && (
            <div className="rounded-xl border border-border bg-surface p-5">
              <div className="flex items-center gap-2 text-base font-semibold">
                <History size={16} /> Sua atividade recente
              </div>
              {minhas.length === 0 ? (
                <p className="mt-3 text-sm text-muted">
                  {atividade.isLoading ? "Carregando…" : "Nada registrado ainda."}
                </p>
              ) : (
                <ul className="mt-3 space-y-1.5">
                  {minhas.map((e) => (
                    <li
                      key={e.id}
                      className="flex items-center gap-3 rounded-md bg-surface-2 px-3 py-2 text-sm"
                    >
                      <span className="truncate font-mono text-xs">{e.action}</span>
                      <span className="ml-auto shrink-0 text-xs whitespace-nowrap text-muted">
                        {new Date(e.created_at).toLocaleString("pt-BR")}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
