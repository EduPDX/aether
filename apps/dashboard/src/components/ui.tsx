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

export function Switch({ checked, onChange, title }: { checked: boolean; onChange: () => void; title?: string }) {
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
      <span
        className={clsx(
          "absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform",
          checked ? "translate-x-4.5" : "translate-x-0.5",
        )}
      />
    </button>
  );
}

export function Modal({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-lg border border-border bg-surface p-5 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="mb-4 text-base font-semibold">{title}</h2>
        {children}
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
