import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeftRight,
  Boxes,
  ClipboardList,
  LayoutDashboard,
  LogOut,
  Plus,
  Server,
  Settings,
  Trash2,
  UserRound,
  Users,
} from "lucide-react";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Spinner } from "./components/ui";
import { api } from "./lib/api";
import { applyTheme, currentTheme } from "./lib/themes";
import { useAuth } from "./modules/auth/AuthGate";
import { CompareView } from "./modules/content/CompareView";
import { CreateInstanceDialog } from "./modules/instances/CreateInstanceDialog";
import { InstanceView } from "./modules/instances/InstanceView";
import { useDialog } from "./components/Dialog";
import { AuditView, UsersView } from "./modules/admin/AdminViews";
import { OverviewView } from "./modules/overview/OverviewView";
import { SettingsView } from "./modules/settings/SettingsView";

type View =
  | { kind: "overview" }
  | { kind: "instance"; id: string }
  | { kind: "compare" }
  | { kind: "users" }
  | { kind: "audit" }
  | { kind: "settings" }
  | { kind: "profile" };

const TITLES: Record<string, string> = {
  overview: "Visão geral",
  compare: "Comparar instâncias",
  users: "Usuários",
  audit: "Auditoria",
  settings: "Configurações",
  profile: "Meu perfil",
};

/** Item de navegação da barra lateral. */
function NavItem({
  icon,
  label,
  active,
  onClick,
  children,
}: {
  icon: ReactNode;
  label: string;
  active: boolean;
  onClick: () => void;
  children?: ReactNode;
}) {
  return (
    <div
      onClick={onClick}
      className={`group flex w-full cursor-pointer items-center gap-2.5 rounded-lg px-3 py-2.5 text-[15px] transition-colors ${
        active ? "bg-surface-3 text-text" : "text-muted hover:bg-surface-2 hover:text-text"
      }`}
    >
      {icon}
      <span className="min-w-0 flex-1 truncate">{label}</span>
      {children}
    </div>
  );
}

/** Título de seção da barra lateral. */
function NavSection({ children }: { children: ReactNode }) {
  return (
    <div className="px-3 pt-4 pb-1.5 text-[11px] font-semibold tracking-widest text-muted/70 uppercase">
      {children}
    </div>
  );
}

export default function App() {
  const qc = useQueryClient();
  const { user, logout } = useAuth();
  const dialog = useDialog();
  const instancesQuery = useQuery({ queryKey: ["instances"], queryFn: api.instances });
  const [view, setView] = useState<View | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  const instances = instancesQuery.data ?? [];

  const removeInstance = useMutation({
    mutationFn: (id: string) => api.deleteInstance(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["instances"] }),
  });

  useEffect(() => {
    if (!view) setView({ kind: "overview" });
  }, [view]);

  useEffect(() => {
    applyTheme(currentTheme());
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        document.getElementById("content-search")?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const active = view?.kind === "instance" ? instances.find((i) => i.id === view.id) : undefined;
  const canManageUsers = user?.role === "owner";
  const canSeeAudit = user?.role === "owner" || user?.role === "admin";

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <aside className="flex w-68 shrink-0 flex-col border-r border-border bg-surface">
        <div className="flex items-center gap-2 px-4 py-4">
          <Boxes size={20} className="text-accent" />
          <span className="text-base font-bold tracking-wide">Aether</span>
          <span className="ml-auto rounded bg-surface-3 px-1.5 py-0.5 text-[10px] text-muted">
            v0.1
          </span>
        </div>

        <nav className="min-h-0 flex-1 overflow-y-auto px-2 pb-2">
          <NavSection>Painel</NavSection>
          <NavItem
            icon={<LayoutDashboard size={17} />}
            label="Visão geral"
            active={view?.kind === "overview"}
            onClick={() => setView({ kind: "overview" })}
          />

          <NavSection>Servidores</NavSection>
          {instances.map((inst) => (
            <NavItem
              key={inst.id}
              icon={
                <span className="relative shrink-0">
                  <Server size={17} />
                  <span
                    className={`absolute -right-0.5 -bottom-0.5 h-2 w-2 rounded-full border border-surface ${
                      inst.state === "running"
                        ? "bg-accent"
                        : inst.state === "crashed"
                          ? "bg-danger"
                          : inst.state === "stopped"
                            ? "bg-surface-3"
                            : "bg-warn"
                    }`}
                  />
                </span>
              }
              label={inst.name}
              active={view?.kind === "instance" && view.id === inst.id}
              onClick={() => setView({ kind: "instance", id: inst.id })}
            >
              <button
                title="Remover instância (não apaga arquivos)"
                className="hidden shrink-0 cursor-pointer text-muted hover:text-danger group-hover:block"
                onClick={async (e) => {
                  e.stopPropagation();
                  const ok = await dialog.confirm({
                    title: "Remover instância",
                    message: `“${inst.name}” sai do painel. Os arquivos no disco não são apagados.`,
                    confirmText: "Remover",
                    tone: "danger",
                  });
                  if (ok) {
                    removeInstance.mutate(inst.id);
                    if (view?.kind === "instance" && view.id === inst.id) setView(null);
                  }
                }}
              >
                <Trash2 size={13} />
              </button>
            </NavItem>
          ))}
          <NavItem
            icon={<ArrowLeftRight size={17} />}
            label="Comparar"
            active={view?.kind === "compare"}
            onClick={() => setView({ kind: "compare" })}
          />
          <NavItem
            icon={<Plus size={17} />}
            label="Nova instância"
            active={false}
            onClick={() => setCreateOpen(true)}
          />

          {(canManageUsers || canSeeAudit) && (
            <>
              <NavSection>Administração</NavSection>
              {canManageUsers && (
                <NavItem
                  icon={<Users size={17} />}
                  label="Usuários"
                  active={view?.kind === "users"}
                  onClick={() => setView({ kind: "users" })}
                />
              )}
              {canSeeAudit && (
                <NavItem
                  icon={<ClipboardList size={17} />}
                  label="Auditoria"
                  active={view?.kind === "audit"}
                  onClick={() => setView({ kind: "audit" })}
                />
              )}
            </>
          )}

          <NavSection>Você</NavSection>
          <NavItem
            icon={<Settings size={17} />}
            label="Configurações"
            active={view?.kind === "settings"}
            onClick={() => setView({ kind: "settings" })}
          />
          <NavItem
            icon={<UserRound size={17} />}
            label="Meu perfil"
            active={view?.kind === "profile"}
            onClick={() => setView({ kind: "profile" })}
          />
        </nav>

        <div className="flex items-center gap-2 border-t border-border p-3">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent-dim text-xs font-bold text-black">
            {user?.username.charAt(0).toUpperCase()}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-xs font-medium">{user?.username}</span>
            <span className="block text-[10px] text-muted">{user?.role}</span>
          </span>
          <button title="Sair" className="cursor-pointer text-muted hover:text-danger" onClick={logout}>
            <LogOut size={17} />
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-border px-4 py-3">
          <h1 className="text-sm font-semibold">
            {view ? (TITLES[view.kind] ?? active?.name ?? "—") : "—"}
          </h1>
          {active && (
            <span className="truncate text-xs text-muted" title={active.root_dir}>
              {active.root_dir}
            </span>
          )}
        </header>

        <div className="min-h-0 flex-1">
          {instancesQuery.isLoading && <Spinner />}
          {instancesQuery.isError && (
            <div className="p-6 text-sm text-danger">
              Não foi possível conectar ao Aether Core. Ele está rodando? (
              {String(instancesQuery.error)})
            </div>
          )}
          {view?.kind === "overview" && !instancesQuery.isLoading && !instancesQuery.isError && (
            <OverviewView instances={instances} />
          )}
          {view?.kind !== "overview" &&
            !instancesQuery.isLoading &&
            instances.length === 0 &&
            !instancesQuery.isError && (
              <div className="flex h-full flex-col items-center justify-center gap-3 text-muted">
                <Boxes size={40} />
                <p className="text-sm">Nenhuma instância ainda.</p>
                <button
                  className="cursor-pointer text-sm text-accent"
                  onClick={() => setCreateOpen(true)}
                >
                  Criar a primeira instância →
                </button>
              </div>
            )}
          {view?.kind === "instance" && active && (
            <InstanceView key={active.id} instance={active} />
          )}
          {view?.kind === "compare" && instances.length >= 2 && (
            <CompareView instances={instances} />
          )}
          {view?.kind === "users" && <UsersView />}
          {view?.kind === "audit" && <AuditView />}
          {view?.kind === "settings" && <SettingsView />}
          {/* O perfil virou uma seção das configurações; o atalho da barra
              lateral apenas abre essa seção direto. */}
          {view?.kind === "profile" && <SettingsView initialSection="perfil" />}
          {view?.kind === "compare" && instances.length < 2 && (
            <div className="p-6 text-sm text-muted">
              É preciso ter pelo menos duas instâncias para comparar.
            </div>
          )}
        </div>
      </main>

      <CreateInstanceDialog open={createOpen} onClose={() => setCreateOpen(false)} />
    </div>
  );
}
