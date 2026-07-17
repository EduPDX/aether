import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeftRight, Boxes, LogOut, Plus, Server, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Spinner } from "./components/ui";
import { api } from "./lib/api";
import { useAuth } from "./modules/auth/AuthGate";
import { CompareView } from "./modules/content/CompareView";
import { CreateInstanceDialog } from "./modules/instances/CreateInstanceDialog";
import { InstanceView } from "./modules/instances/InstanceView";

type View = { kind: "instance"; id: string } | { kind: "compare" };

export default function App() {
  const qc = useQueryClient();
  const { user, logout } = useAuth();
  const instancesQuery = useQuery({ queryKey: ["instances"], queryFn: api.instances });
  const [view, setView] = useState<View | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  const instances = instancesQuery.data ?? [];

  const removeInstance = useMutation({
    mutationFn: (id: string) => api.deleteInstance(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["instances"] }),
  });

  useEffect(() => {
    if (!view && instances.length > 0) setView({ kind: "instance", id: instances[0].id });
  }, [view, instances]);

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

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <aside className="flex w-60 shrink-0 flex-col border-r border-border bg-surface">
        <div className="flex items-center gap-2 px-4 py-4">
          <Boxes size={20} className="text-accent" />
          <span className="text-base font-bold tracking-wide">Aether</span>
          <span className="ml-auto rounded bg-surface-3 px-1.5 py-0.5 text-[10px] text-muted">
            v0.1
          </span>
        </div>

        <div className="px-3 pt-2 pb-1 text-[11px] font-semibold tracking-wider text-muted uppercase">
          Instâncias
        </div>
        <nav className="flex-1 space-y-0.5 overflow-y-auto px-2">
          {instances.map((inst) => (
            <div
              key={inst.id}
              className={`group flex w-full cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors ${
                view?.kind === "instance" && view.id === inst.id
                  ? "bg-surface-3 text-text"
                  : "text-muted hover:bg-surface-2 hover:text-text"
              }`}
              onClick={() => setView({ kind: "instance", id: inst.id })}
            >
              <span className="relative shrink-0">
                <Server size={15} />
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
              <span className="truncate">{inst.name}</span>
              <button
                title="Remover instância (não apaga arquivos)"
                className="ml-auto hidden cursor-pointer text-muted hover:text-danger group-hover:block"
                onClick={(e) => {
                  e.stopPropagation();
                  if (confirm(`Remover a instância "${inst.name}"? Os arquivos não são apagados.`)) {
                    removeInstance.mutate(inst.id);
                    if (view?.kind === "instance" && view.id === inst.id) setView(null);
                  }
                }}
              >
                <Trash2 size={13} />
              </button>
            </div>
          ))}

          <button
            className={`flex w-full cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors ${
              view?.kind === "compare"
                ? "bg-surface-3 text-text"
                : "text-muted hover:bg-surface-2 hover:text-text"
            }`}
            onClick={() => setView({ kind: "compare" })}
          >
            <ArrowLeftRight size={15} />
            Comparar
          </button>
        </nav>

        <div className="border-t border-border p-2">
          <button
            className="flex w-full cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm text-muted transition-colors hover:bg-surface-2 hover:text-text"
            onClick={() => setCreateOpen(true)}
          >
            <Plus size={15} /> Nova instância
          </button>
          <div className="mt-1 flex items-center gap-2 rounded-md px-2 py-1.5 text-sm">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-accent-dim text-xs font-bold text-black">
              {user?.username.charAt(0).toUpperCase()}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-xs">{user?.username}</span>
              <span className="block text-[10px] text-muted">{user?.role}</span>
            </span>
            <button
              title="Sair"
              className="cursor-pointer text-muted hover:text-danger"
              onClick={logout}
            >
              <LogOut size={14} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-border px-4 py-3">
          <h1 className="text-sm font-semibold">
            {view?.kind === "compare" ? "Comparar instâncias" : (active?.name ?? "—")}
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
          {!instancesQuery.isLoading && instances.length === 0 && !instancesQuery.isError && (
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
