import { useQueryClient } from "@tanstack/react-query";
import { Upload } from "lucide-react";
import { useRef, useState } from "react";
import { api } from "../lib/api";
import { Button } from "./ui";

/** Envia arquivos do PC do usuário para uma pasta da instância no servidor. */
export function UploadButton({
  instanceId,
  path,
  label = "Enviar",
  accept,
  onDone,
}: {
  instanceId: string;
  path: string;
  label?: string;
  accept?: string;
  onDone?: () => void;
}) {
  const qc = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");

  async function send(files: FileList, overwrite = false) {
    setBusy(true);
    setStatus(`enviando ${files.length} arquivo(s)…`);
    try {
      const res = await api.uploadFiles(instanceId, path, files, overwrite);
      setStatus(`${res.saved.length} arquivo(s) enviado(s)`);
      qc.invalidateQueries();
      onDone?.();
      setTimeout(() => setStatus(""), 3000);
    } catch (e) {
      const msg = String(e instanceof Error ? e.message : e);
      // Conflito: pergunta antes de sobrescrever.
      if (msg.includes("já existe") && !overwrite) {
        if (confirm(`${msg}\n\nSubstituir o(s) arquivo(s) existente(s)?`)) {
          setBusy(false);
          return send(files, true);
        }
        setStatus("");
      } else {
        setStatus(`erro: ${msg}`);
      }
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <span className="flex items-center gap-2">
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={accept}
        className="hidden"
        onChange={(e) => e.target.files?.length && send(e.target.files)}
      />
      <Button variant="default" disabled={busy} onClick={() => inputRef.current?.click()}>
        <Upload size={14} /> {busy ? "Enviando…" : label}
      </Button>
      {status && <span className="text-[11px] text-muted">{status}</span>}
    </span>
  );
}
