import { Boxes } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Button, Input, Spinner } from "../../components/ui";
import type { AuthUser } from "../../lib/api";
import { api, clearTokens, getAccessToken, setTokens } from "../../lib/api";

type Phase = "loading" | "setup" | "login" | "ready";

const AuthContext = createContext<{ user: AuthUser | null; logout: () => void }>({
  user: null,
  logout: () => {},
});

export const useAuth = () => useContext(AuthContext);

export function AuthGate({ children }: { children: ReactNode }) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);

  const bootstrap = useCallback(async () => {
    try {
      const { setup_required } = await api.authStatus();
      if (setup_required) return setPhase("setup");
      if (!getAccessToken()) return setPhase("login");
      try {
        setUser(await api.me());
        setPhase("ready");
      } catch {
        setPhase("login");
      }
    } catch {
      setPhase("login"); // Core fora do ar: a tela de login mostra o erro ao tentar
    }
  }, []);

  useEffect(() => {
    bootstrap();
    const onLogout = () => {
      setUser(null);
      setPhase("login");
    };
    window.addEventListener("aether:logout", onLogout);
    return () => window.removeEventListener("aether:logout", onLogout);
  }, [bootstrap]);

  const logout = useCallback(() => {
    clearTokens();
  }, []);

  if (phase === "loading") return <Spinner />;
  if (phase === "ready" && user)
    return <AuthContext.Provider value={{ user, logout }}>{children}</AuthContext.Provider>;

  return (
    <AuthForm
      mode={phase === "setup" ? "setup" : "login"}
      onDone={(u) => {
        setUser(u);
        setPhase("ready");
      }}
    />
  );
}

function AuthForm({
  mode,
  onDone,
}: {
  mode: "setup" | "login";
  onDone: (user: AuthUser) => void;
}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    setError("");
    if (mode === "setup" && password !== confirm) {
      setError("As senhas não conferem.");
      return;
    }
    setBusy(true);
    try {
      const res =
        mode === "setup"
          ? await api.setup(username, password)
          : await api.login(username, password);
      setTokens(res.access_token, res.refresh_token);
      onDone(res.user);
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full items-center justify-center">
      <div className="w-full max-w-sm rounded-xl border border-border bg-surface p-6 shadow-2xl">
        <div className="mb-5 flex items-center justify-center gap-2">
          <Boxes size={24} className="text-accent" />
          <span className="text-lg font-bold tracking-wide">Aether</span>
        </div>

        {mode === "setup" && (
          <p className="mb-4 text-center text-xs text-muted">
            Primeira execução: crie a conta do administrador (owner).
          </p>
        )}

        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <Input
            className="w-full"
            placeholder="Usuário"
            autoFocus
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
          />
          <Input
            className="w-full"
            type="password"
            placeholder={mode === "setup" ? "Senha (mín. 8 caracteres)" : "Senha"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={mode === "setup" ? "new-password" : "current-password"}
          />
          {mode === "setup" && (
            <Input
              className="w-full"
              type="password"
              placeholder="Confirmar senha"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              autoComplete="new-password"
            />
          )}
          {error && <p className="text-xs text-danger">{error}</p>}
          <Button
            variant="primary"
            className="w-full justify-center"
            disabled={busy || !username || !password}
            type="submit"
          >
            {mode === "setup" ? "Criar conta e entrar" : "Entrar"}
          </Button>
        </form>
      </div>
    </div>
  );
}
