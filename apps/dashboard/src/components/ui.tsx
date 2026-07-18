/** Small design-system primitives (dark theme, token-based). */

import clsx from "clsx";
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";

export function Button({
  variant = "default",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "default" | "primary" | "danger" | "ghost" }) {
  return (
    <button
      className={clsx(
        "inline-flex cursor-pointer items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        variant === "default" && "bg-surface-3 hover:bg-border text-text",
        variant === "primary" && "bg-accent-dim hover:bg-accent text-black",
        variant === "danger" && "bg-surface-3 hover:bg-danger/20 text-danger",
        variant === "ghost" && "hover:bg-surface-2 text-muted hover:text-text",
        className,
      )}
      {...props}
    />
  );
}

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={clsx(
        "rounded-md border border-border bg-surface-2 px-3 py-1.5 text-sm outline-none placeholder:text-muted focus:border-accent-dim",
        className,
      )}
      {...props}
    />
  );
}

export function Select({ className, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={clsx(
        "cursor-pointer rounded-md border border-border bg-surface-2 px-2 py-1.5 text-sm outline-none focus:border-accent-dim",
        className,
      )}
      {...props}
    />
  );
}

export function Badge({
  tone = "neutral",
  children,
  title,
}: {
  tone?: "neutral" | "green" | "orange" | "blue" | "red";
  children: ReactNode;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={clsx(
        "inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-semibold whitespace-nowrap",
        tone === "neutral" && "bg-surface-3 text-muted",
        tone === "green" && "bg-accent/15 text-accent",
        tone === "orange" && "bg-warn/15 text-warn",
        tone === "blue" && "bg-info/15 text-info",
        tone === "red" && "bg-danger/15 text-danger",
      )}
    >
      {children}
    </span>
  );
}

export function Switch({
  checked,
  onChange,
  title,
}: {
  checked: boolean;
  onChange: () => void;
  title?: string;
}) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      title={title}
      onClick={onChange}
      className={clsx(
        "relative h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors",
        checked ? "bg-accent-dim" : "bg-surface-3",
      )}
    >
      {/* Posição explícita em px: o knob fica sempre 2px dentro da trilha. */}
      <span
        className="absolute top-1/2 h-4 w-4 -translate-y-1/2 rounded-full bg-white shadow-sm transition-[left] duration-150"
        style={{ left: checked ? "calc(100% - 18px)" : "2px" }}
      />
    </button>
  );
}

export function Modal({
  open,
  onClose,
  title,
  children,
  size = "md",
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  size?: "md" | "lg";
}) {
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      {/* max-h + overflow: formulários longos rolam dentro do modal em vez
          de vazar para fora da tela. */}
      <div
        className={clsx(
          "flex max-h-[90vh] w-full flex-col rounded-lg border border-border bg-surface shadow-2xl",
          size === "lg" ? "max-w-2xl" : "max-w-md",
        )}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="border-b border-border px-5 py-3 text-base font-semibold">{title}</h2>
        <div className="min-h-0 flex-1 overflow-y-auto p-5">{children}</div>
      </div>
    </div>
  );
}

export function Spinner() {
  return (
    <div className="flex items-center justify-center py-16 text-muted">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-border border-t-accent" />
    </div>
  );
}
