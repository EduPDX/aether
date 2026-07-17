import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FolderSearch } from "lucide-react";
import { useState } from "react";
import { Button, Input, Modal } from "../../components/ui";
import { api } from "../../lib/api";
import { FolderBrowser } from "./FolderBrowser";

export function CreateInstanceDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [rootDir, setRootDir] = useState("");
  const [isModsFolder, setIsModsFolder] = useState(false);
  const [browserOpen, setBrowserOpen] = useState(false);
  const [error, setError] = useState("");

  const create = useMutation({
    mutationFn: () =>
      api.createInstance({
        name,
        provider_id: "minecraft",
        root_dir: rootDir,
        content_dirs: isModsFolder ? { mod: "." } : {},
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["instances"] });
      setName("");
      setRootDir("");
      setError("");
      onClose();
    },
    onError: (e) => setError(String(e)),
  });

  return (
    <Modal open={open} onClose={onClose} title="Nova instância">
      <div className="space-y-3">
        <div>
          <label className="mb-1 block text-xs text-muted">Nome</label>
          <Input
            className="w-full"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Ex.: Servidor Forge"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-muted">Pasta do servidor</label>
          <div className="flex gap-2">
            <Input
              className="flex-1 font-mono text-xs"
              value={rootDir}
              onChange={(e) => setRootDir(e.target.value)}
              placeholder="/caminho/no/servidor"
            />
            <Button variant="default" onClick={() => setBrowserOpen(true)}>
              <FolderSearch size={14} /> Procurar
            </Button>
          </div>
          <p className="mt-1 text-[11px] text-muted/80">
            É a pasta <b>na máquina onde o Aether roda</b> (o servidor), não do seu PC. É a raiz
            do servidor de jogo — a que contém <code>mods/</code>, <code>server.properties</code>{" "}
            etc.
          </p>
        </div>
        <label className="flex cursor-pointer items-center gap-2 text-sm text-muted select-none">
          <input
            type="checkbox"
            checked={isModsFolder}
            onChange={(e) => setIsModsFolder(e.target.checked)}
            className="accent-(--color-accent-dim)"
          />
          A pasta escolhida <b>já é</b> a pasta de mods (marque só se apontou direto para{" "}
          <code>mods/</code>)
        </label>
        {error && <p className="text-xs text-danger">{error}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="ghost" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            variant="primary"
            disabled={!name.trim() || !rootDir.trim() || create.isPending}
            onClick={() => create.mutate()}
          >
            Criar
          </Button>
        </div>
      </div>

      <FolderBrowser
        open={browserOpen}
        onClose={() => setBrowserOpen(false)}
        onPick={setRootDir}
      />
    </Modal>
  );
}
