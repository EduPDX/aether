import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button, Input, Modal } from "../../components/ui";
import { api } from "../../lib/api";

export function CreateInstanceDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [rootDir, setRootDir] = useState("");
  const [isModsFolder, setIsModsFolder] = useState(true);
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
            placeholder="Ex.: Servidor"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-muted">Pasta</label>
          <Input
            className="w-full"
            value={rootDir}
            onChange={(e) => setRootDir(e.target.value)}
            placeholder="C:\caminho\para\a\pasta"
          />
        </div>
        <label className="flex cursor-pointer items-center gap-2 text-sm text-muted select-none">
          <input
            type="checkbox"
            checked={isModsFolder}
            onChange={(e) => setIsModsFolder(e.target.checked)}
            className="accent-(--color-accent-dim)"
          />
          A pasta já é a pasta de mods (senão, usa a subpasta <code>mods/</code>)
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
    </Modal>
  );
}
