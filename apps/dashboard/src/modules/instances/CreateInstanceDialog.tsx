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
          <p className="mt-1.5 text-[11px] leading-relaxed text-muted/80">
            É a pasta <b>na máquina onde o Aether roda</b> (o servidor), não do seu PC. Aponte
            para a raiz do servidor — aquela que contém{" "}
            <code className="whitespace-nowrap">mods/</code> e{" "}
            <code className="whitespace-nowrap">server.properties</code>.
          </p>
        </div>
        {/* O texto vai num <span> próprio: sem isso o flex quebra cada
            trecho inline em um item separado e a frase fica picotada. */}
        <label className="flex cursor-pointer items-start gap-2 select-none">
          <input
            type="checkbox"
            checked={isModsFolder}
            onChange={(e) => setIsModsFolder(e.target.checked)}
            className="mt-0.5 shrink-0 accent-(--color-accent-dim)"
          />
          <span className="text-[13px] leading-relaxed text-muted">
            A pasta escolhida <b>já é</b> a pasta de mods (marque apenas se apontou direto para{" "}
            <code className="whitespace-nowrap">mods/</code>).
          </span>
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
