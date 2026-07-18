import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Plus, Shield, Trash2, UserRound } from "lucide-react";
import { useState } from "react";
import { Badge, Button, Input, Modal, Select, Spinner } from "../../components/ui";
import { api } from "../../lib/api";
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
                    onClick={() => {
                      if (confirm(`Remover o usuário "${u.username}"?`)) remove.mutate(u.id);
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

export function ProfileView() {
  const { user } = useAuth();
  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="mx-auto w-full max-w-md space-y-3">
        <div className="rounded-xl border border-border bg-surface p-5 text-center">
          <span className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-accent-dim text-2xl font-bold text-black">
            {user?.username.charAt(0).toUpperCase()}
          </span>
          <div className="mt-3 text-lg font-bold">{user?.username}</div>
          <Badge tone={ROLE_TONE[user?.role ?? ""] ?? "neutral"}>{user?.role}</Badge>
          <p className="mt-2 text-[11px] text-muted">{ROLE_DESC[user?.role ?? ""]}</p>
        </div>
        <div className="rounded-xl border border-border bg-surface p-4">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <Shield size={14} /> Suas permissões
          </div>
          <ul className="mt-2 space-y-1 text-xs text-muted">
            <li className="flex items-center gap-2">
              <UserRound size={12} /> Papel: <b className="text-text">{user?.role}</b>
            </li>
            <li className="flex items-center gap-2">
              <KeyRound size={12} /> Sessão com renovação automática
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}
