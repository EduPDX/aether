import { AtSign, Boxes, Eye, EyeOff, KeyRound, ShieldCheck, UserRound } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Button, Input, Spinner } from "../../components/ui";
import type { AuthUser } from "../../lib/api";
import { api, clearTokens, getAccessToken, setTokens } from "../../lib/api";
import { THEMES, currentTheme } from "../../lib/themes";

type Phase = "loading" | "setup" | "login" | "ready";

const AuthContext = createContext<{
  user: AuthUser | null;
  logout: () => void;
  refresh: () => void;
}>({
  user: null,
  logout: () => {},
  refresh: () => {},
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

  /** Recarrega o usuário depois de editar o perfil. */
  const refresh = useCallback(() => {
    api.me().then(setUser).catch(() => {});
  }, []);

  if (phase === "loading") return <Spinner />;
  if (phase === "ready" && user)
    return (
      <AuthContext.Provider value={{ user, logout, refresh }}>{children}</AuthContext.Provider>
    );

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

/** Campo com ícone à esquerda e rótulo — a tela antiga era só placeholders. */
function Campo({
  icone,
  rotulo,
  hint,
  children,
}: {
  icone: ReactNode;
  rotulo: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 flex items-center gap-1.5 text-xs font-medium text-muted">
        {icone}
        {rotulo}
        {hint && <span className="font-normal text-muted/70">· {hint}</span>}
      </span>
      {children}
    </label>
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
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [verSenha, setVerSenha] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const tema = THEMES[currentTheme()];
  const curta = mode === "setup" && password.length > 0 && password.length < 8;
  const diferem = mode === "setup" && confirm.length > 0 && password !== confirm;

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
          ? await api.setup(username, password, email, displayName)
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
    <div className="relative flex h-full items-center justify-center overflow-hidden p-6">
      {/* Fundo com a paleta do tema — a tela era cinza chapado. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-40 blur-3xl"
        style={{
          background:
            `radial-gradient(38rem 30rem at 18% 12%, ${tema.chart[0]}55, transparent 65%), ` +
            `radial-gradient(34rem 28rem at 84% 78%, ${tema.chart[1]}45, transparent 65%)`,
        }}
      />

      <div className="relative w-full max-w-md">
        <div className="mb-6 flex flex-col items-center gap-2 text-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-accent/15">
            <Boxes size={30} className="text-accent" />
          </span>
          <h1 className="text-2xl font-extrabold tracking-wide">Aether</h1>
          <p className="text-sm text-muted">
            {mode === "setup"
              ? "Vamos criar a conta de administrador desta instalação."
              : "Painel de administração dos seus servidores."}
          </p>
        </div>

        <div className="rounded-2xl border border-border bg-surface p-6 shadow-2xl">
          {mode === "setup" && (
            <div className="mb-5 flex items-start gap-2.5 rounded-lg bg-surface-2 p-3">
              <ShieldCheck size={16} className="mt-0.5 shrink-0 text-accent" />
              <p className="text-xs text-muted">
                Esta conta é o <b className="text-text">dono</b> da instalação: só ela cria
                usuários e redefine senhas. Guarde bem — não há recuperação por e-mail.
              </p>
            </div>
          )}

          <form
            className="space-y-3.5"
            onSubmit={(e) => {
              e.preventDefault();
              submit();
            }}
          >
            <Campo icone={<UserRound size={13} />} rotulo="Usuário">
              <Input
                className="w-full"
                placeholder="seu-usuario"
                autoFocus
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
              />
            </Campo>

            {mode === "setup" && (
              <>
                <Campo icone={<UserRound size={13} />} rotulo="Nome" hint="opcional">
                  <Input
                    className="w-full"
                    placeholder="Como quer ser chamado"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    autoComplete="name"
                  />
                </Campo>

                <Campo icone={<AtSign size={13} />} rotulo="E-mail" hint="opcional">
                  <Input
                    className="w-full"
                    type="email"
                    placeholder="voce@exemplo.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    autoComplete="email"
                  />
                </Campo>
              </>
            )}

            <Campo
              icone={<KeyRound size={13} />}
              rotulo="Senha"
              hint={mode === "setup" ? "mínimo 8 caracteres" : undefined}
            >
              <span className="flex items-center gap-1.5">
                <Input
                  className="w-full"
                  type={verSenha ? "text" : "password"}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete={mode === "setup" ? "new-password" : "current-password"}
                />
                <button
                  type="button"
                  title={verSenha ? "Ocultar" : "Mostrar"}
                  className="cursor-pointer text-muted hover:text-text"
                  onClick={() => setVerSenha((v) => !v)}
                >
                  {verSenha ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </span>
              {curta && (
                <span className="mt-1 block text-[11px] text-warn">
                  Faltam {8 - password.length} caractere(s).
                </span>
              )}
            </Campo>

            {mode === "setup" && (
              <Campo icone={<KeyRound size={13} />} rotulo="Confirmar senha">
                <Input
                  className="w-full"
                  type={verSenha ? "text" : "password"}
                  placeholder="••••••••"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  autoComplete="new-password"
                />
                {diferem && (
                  <span className="mt-1 block text-[11px] text-danger">
                    As senhas não conferem.
                  </span>
                )}
              </Campo>
            )}

            {error && (
              <p className="rounded-md bg-danger/10 px-3 py-2 text-xs text-danger">{error}</p>
            )}

            <Button
              variant="primary"
              className="w-full justify-center py-2.5 font-bold"
              disabled={busy || !username || !password || curta || diferem}
              type="submit"
            >
              {busy ? "Aguarde…" : mode === "setup" ? "Criar conta e entrar" : "Entrar"}
            </Button>
          </form>
        </div>

        {mode === "login" && (
          <p className="mt-4 text-center text-xs text-muted">
            Esqueceu a senha? O Aether não envia e-mail — peça ao dono da instalação para
            redefini-la em <b className="text-text">Usuários</b>.
          </p>
        )}
      </div>
    </div>
  );
}
