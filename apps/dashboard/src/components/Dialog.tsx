/**
 * Diálogos do app — substituem `confirm`, `alert` e `prompt` do navegador.
 *
 * Desenho portado do CustomAlert do finance-frontend: cartão centralizado,
 * ícone num círculo tingido com a cor do tipo, título, mensagem e dois botões
 * de largura igual.
 *
 * A API é uma promessa (`await confirm({...})`) porque o código que existia
 * usava `if (confirm(...))`. Manter o mesmo formato deixou a troca mecânica,
 * sem transformar cada chamada num par de estados e callbacks.
 */

import { AlertTriangle, CheckCircle2, Info } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Button, Input } from "./ui";

type Tone = "default" | "danger" | "success";

interface AskOptions {
  title: string;
  message?: ReactNode;
  confirmText?: string;
  cancelText?: string;
  tone?: Tone;
  /** Presente = diálogo com campo de texto (substitui `prompt`). */
  input?: { label?: string; placeholder?: string; initialValue?: string };
  /** Some o botão de cancelar — vira um aviso (substitui `alert`). */
  acknowledge?: boolean;
}

interface Pedido extends AskOptions {
  resolve: (valor: string | boolean | null) => void;
}

const TONE = {
  default: { Icon: Info, cor: "text-info" },
  danger: { Icon: AlertTriangle, cor: "text-danger" },
  success: { Icon: CheckCircle2, cor: "text-accent" },
} as const;

interface DialogApi {
  confirm: (opts: AskOptions) => Promise<boolean>;
  notify: (opts: AskOptions) => Promise<boolean>;
  promptText: (opts: AskOptions) => Promise<string | null>;
}

const Ctx = createContext<DialogApi | null>(null);

export function useDialog(): DialogApi {
  const api = useContext(Ctx);
  if (!api) throw new Error("useDialog precisa estar dentro de <DialogProvider>");
  return api;
}

export function DialogProvider({ children }: { children: ReactNode }) {
  const [pedido, setPedido] = useState<Pedido | null>(null);
  const [valor, setValor] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const abrir = useCallback(
    (opts: AskOptions) =>
      new Promise<string | boolean | null>((resolve) => {
        setValor(opts.input?.initialValue ?? "");
        setPedido({ ...opts, resolve });
      }),
    [],
  );

  const api: DialogApi = {
    confirm: (opts) => abrir(opts).then((v) => v === true),
    notify: (opts) => abrir({ ...opts, acknowledge: true }).then((v) => v === true),
    promptText: (opts) =>
      abrir({ ...opts, input: opts.input ?? {} }).then((v) =>
        typeof v === "string" ? v : null,
      ),
  };

  function fechar(resultado: string | boolean | null) {
    pedido?.resolve(resultado);
    setPedido(null);
  }

  // Foca o campo ao abrir, para o diálogo com input funcionar como o prompt
  // nativo: abre e já dá para digitar.
  useEffect(() => {
    if (pedido?.input) inputRef.current?.focus();
  }, [pedido]);

  useEffect(() => {
    if (!pedido) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        fechar(pedido.input ? null : false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pedido]);

  const { Icon, cor } = TONE[pedido?.tone ?? "default"];
  const confirmar = () => fechar(pedido?.input ? valor : true);
  const podeConfirmar = !pedido?.input || valor.trim().length > 0;

  return (
    <Ctx.Provider value={api}>
      {children}
      {pedido && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/55 p-6"
          onClick={() => fechar(pedido.input ? null : false)}
          role="presentation"
        >
          <div
            role="alertdialog"
            aria-modal="true"
            aria-label={pedido.title}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-sm rounded-3xl border border-border bg-surface p-7 text-center shadow-2xl"
          >
            <span
              className={`mx-auto mb-4 flex h-15 w-15 items-center justify-center rounded-full ${cor} bg-current/15`}
              style={{ width: 60, height: 60 }}
            >
              <Icon size={28} className={cor} />
            </span>

            <h2 className="text-lg font-extrabold">{pedido.title}</h2>
            {pedido.message && (
              <div className="mt-2 text-sm leading-relaxed text-muted">{pedido.message}</div>
            )}

            {pedido.input && (
              <div className="mt-4 text-left">
                {pedido.input.label && (
                  <label className="mb-1 block text-xs text-muted">{pedido.input.label}</label>
                )}
                <Input
                  ref={inputRef}
                  className="w-full"
                  placeholder={pedido.input.placeholder}
                  value={valor}
                  onChange={(e) => setValor(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && podeConfirmar) confirmar();
                  }}
                />
              </div>
            )}

            <div className="mt-7 flex gap-2.5">
              {!pedido.acknowledge && (
                <Button
                  className="flex-1 justify-center py-3"
                  onClick={() => fechar(pedido.input ? null : false)}
                >
                  {pedido.cancelText ?? "Cancelar"}
                </Button>
              )}
              <Button
                variant={pedido.tone === "danger" ? "danger" : "primary"}
                className="flex-1 justify-center py-3 font-extrabold"
                disabled={!podeConfirmar}
                onClick={confirmar}
              >
                {pedido.confirmText ?? "Confirmar"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </Ctx.Provider>
  );
}
