import { useMutation } from "@tanstack/react-query";
import { AtSign, Check, KeyRound, UserRound } from "lucide-react";
import { useState } from "react";
import { Badge, Button, Input } from "../../components/ui";
import { api, setTokens } from "../../lib/api";
import { useAuth } from "../auth/AuthGate";

/** Dados de contato do usuário logado. */
export function ProfileFormCard() {
  const { user, refresh } = useAuth();
  const [email, setEmail] = useState(user?.email ?? "");
  const [nome, setNome] = useState(user?.display_name ?? "");
  const [erro, setErro] = useState("");
  const [salvo, setSalvo] = useState(false);

  const salvar = useMutation({
    mutationFn: () => api.updateProfile(email, nome),
    onSuccess: () => {
      setErro("");
      setSalvo(true);
      setTimeout(() => setSalvo(false), 2500);
      refresh();
    },
    onError: (e) => setErro(String(e instanceof Error ? e.message : e)),
  });

  const mudou = email !== (user?.email ?? "") || nome !== (user?.display_name ?? "");

  return (
    <div className="rounded-xl border border-border bg-surface p-5">
      <div className="flex items-center gap-2 text-base font-semibold">
        <UserRound size={16} /> Seus dados
        {salvo && <Badge tone="green">salvo ✓</Badge>}
      </div>

      <div className="mt-3 space-y-3">
        <label className="block">
          <span className="mb-1 block text-xs text-muted">Nome de exibição</span>
          <Input
            className="w-full"
            placeholder={user?.username}
            value={nome}
            onChange={(e) => setNome(e.target.value)}
          />
        </label>
        <label className="block">
          <span className="mb-1 flex items-center gap-1.5 text-xs text-muted">
            <AtSign size={12} /> E-mail
          </span>
          <Input
            className="w-full"
            type="email"
            placeholder="voce@exemplo.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <span className="mt-1 block text-[11px] text-muted">
            Serve só como contato. O Aether não envia e-mail, então não recupera senha por aqui.
          </span>
        </label>

        {erro && <p className="text-xs text-danger">{erro}</p>}
        <Button variant="primary" disabled={!mudou || salvar.isPending} onClick={() => salvar.mutate()}>
          <Check size={14} /> Salvar
        </Button>
      </div>
    </div>
  );
}

/** Troca de senha do próprio usuário. */
export function PasswordCard() {
  const [atual, setAtual] = useState("");
  const [nova, setNova] = useState("");
  const [confirma, setConfirma] = useState("");
  const [erro, setErro] = useState("");
  const [ok, setOk] = useState("");

  const trocar = useMutation({
    mutationFn: () => api.changePassword(atual, nova),
    onSuccess: (r) => {
      // A troca invalida as sessões antigas — inclusive esta. Guardar os
      // tokens novos é o que evita ser deslogado ao trocar a própria senha.
      setTokens(r.access_token, r.refresh_token);
      setAtual("");
      setNova("");
      setConfirma("");
      setErro("");
      setOk("Senha alterada. As outras sessões desta conta foram encerradas.");
      setTimeout(() => setOk(""), 6000);
    },
    onError: (e) => setErro(String(e instanceof Error ? e.message : e)),
  });

  const curta = nova.length > 0 && nova.length < 8;
  const diferem = confirma.length > 0 && nova !== confirma;
  const pronto = atual && nova.length >= 8 && nova === confirma;

  return (
    <div className="rounded-xl border border-border bg-surface p-5">
      <div className="flex items-center gap-2 text-base font-semibold">
        <KeyRound size={16} /> Trocar senha
      </div>

      <form
        className="mt-3 space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (pronto) trocar.mutate();
        }}
      >
        <label className="block">
          <span className="mb-1 block text-xs text-muted">Senha atual</span>
          <Input
            className="w-full"
            type="password"
            autoComplete="current-password"
            value={atual}
            onChange={(e) => setAtual(e.target.value)}
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs text-muted">Nova senha (mín. 8)</span>
          <Input
            className="w-full"
            type="password"
            autoComplete="new-password"
            value={nova}
            onChange={(e) => setNova(e.target.value)}
          />
          {curta && (
            <span className="mt-1 block text-[11px] text-warn">
              Faltam {8 - nova.length} caractere(s).
            </span>
          )}
        </label>
        <label className="block">
          <span className="mb-1 block text-xs text-muted">Confirmar nova senha</span>
          <Input
            className="w-full"
            type="password"
            autoComplete="new-password"
            value={confirma}
            onChange={(e) => setConfirma(e.target.value)}
          />
          {diferem && (
            <span className="mt-1 block text-[11px] text-danger">As senhas não conferem.</span>
          )}
        </label>

        {erro && <p className="text-xs text-danger">{erro}</p>}
        {ok && <p className="text-xs text-accent">{ok}</p>}

        <Button variant="primary" type="submit" disabled={!pronto || trocar.isPending}>
          <KeyRound size={14} /> Trocar senha
        </Button>
        <p className="text-[11px] text-muted">
          Ao trocar, qualquer sessão aberta em outro navegador para de valer.
        </p>
      </form>
    </div>
  );
}
