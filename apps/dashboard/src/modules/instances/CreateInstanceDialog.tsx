import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Container, FolderSearch, Gamepad2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Button, Input, Modal, Select } from "../../components/ui";
import type { ProviderInfo } from "../../lib/api";
import { api } from "../../lib/api";
import { useProviders } from "../../lib/providers";
import { useQuery } from "@tanstack/react-query";
import { FieldControl } from "../config/FieldControl";
import { valoresIniciais, visivel } from "../config/fields";
import { FolderBrowser } from "./FolderBrowser";

type Modo = "adopt" | "create";

/**
 * Criação de instância em dois passos: escolher o jogo (provider) e então
 * adotar uma pasta existente ou criar um servidor do zero em container.
 * O formulário de criação é gerado do provision_schema do provider — a
 * interface não conhece nenhum jogo em particular.
 */
export function CreateInstanceDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const providers = useProviders();
  const [providerId, setProviderId] = useState<string | null>(null);
  const [modo, setModo] = useState<Modo>("adopt");
  const [name, setName] = useState("");
  const [rootDir, setRootDir] = useState("");
  const [isContentFolder, setIsContentFolder] = useState(false);
  const [provisionValues, setProvisionValues] = useState<Record<string, string>>({});
  const [version, setVersion] = useState("");
  const [browserOpen, setBrowserOpen] = useState(false);
  const [error, setError] = useState("");

  const provider = providers.find((p) => p.manifest.id === providerId);
  const podeCriar = Boolean(
    provider?.capabilities.container && provider?.capabilities.provision,
  );
  const contentType = provider?.content_types[0];

  const camposProvision = useMemo(
    () => provider?.provision_schema?.fields ?? [],
    [provider],
  );

  // Os padrões precisam existir desde o início: sem eles a dependência de
  // "mundo gerado" nunca bate e os campos de semente/tamanho não aparecem.
  useEffect(() => {
    setProvisionValues(camposProvision.length ? valoresIniciais(camposProvision) : {});
  }, [camposProvision]);

  const versoes = useQuery({
    queryKey: ["versions", providerId],
    queryFn: () => api.providerVersions(providerId!),
    enabled: Boolean(providerId) && Boolean(provider?.capabilities.install) && modo === "create",
    staleTime: 5 * 60 * 1000,
  });
  const opcoesDeVersao = versoes.data ?? [];
  const versaoEscolhida = version || opcoesDeVersao.find((v) => v.stable)?.id || "";

  const reset = () => {
    setProviderId(null);
    setModo("adopt");
    setName("");
    setRootDir("");
    setIsContentFolder(false);
    setProvisionValues({});
    setVersion("");
    setError("");
  };

  const create = useMutation({
    mutationFn: () => {
      if (modo === "create") {
        // Campo escondido pela dependência não vai: mandar semente de mapa
        // pré-gerado gravaria configuração que o jogo ignora.
        const values: Record<string, string> = {};
        for (const f of camposProvision) {
          if (visivel(f, provisionValues)) values[f.key] = provisionValues[f.key] ?? f.default;
        }
        return api.createInstance({
          name,
          provider_id: providerId!,
          runtime: "docker",
          provision_values: values,
          version: version || undefined,
        });
      }
      return api.createInstance({
        name,
        provider_id: providerId!,
        root_dir: rootDir,
        // Provider sem launch roda a pasta adotada em container mesmo assim.
        runtime: provider?.capabilities.launch ? "process" : "docker",
        content_dirs:
          isContentFolder && contentType ? { [contentType.id]: "." } : {},
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["instances"] });
      reset();
      onClose();
    },
    onError: (e) => setError(String(e)),
  });

  const pronto =
    name.trim() &&
    (modo === "create" ? podeCriar : rootDir.trim()) &&
    !create.isPending;

  return (
    <Modal open={open} onClose={onClose} title="Nova instância">
      {!provider ? (
        <div className="space-y-2">
          <p className="text-xs text-muted">Qual jogo esta instância vai rodar?</p>
          {providers.map((p: ProviderInfo) => (
            <button
              key={p.manifest.id}
              className="flex w-full cursor-pointer items-center gap-3 rounded-xl border border-border bg-surface-2 px-4 py-3 text-left hover:border-accent/60"
              onClick={() => setProviderId(p.manifest.id)}
            >
              <Gamepad2 size={18} className="shrink-0 text-accent" />
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-medium">{p.manifest.name}</span>
                <span className="block text-[11px] text-muted">
                  {p.capabilities.container && p.capabilities.launch
                    ? "Container ou processo local"
                    : p.capabilities.container
                      ? "Container (Docker)"
                      : "Processo local"}
                </span>
              </span>
            </button>
          ))}
          {providers.length === 0 && (
            <p className="text-sm text-muted">Nenhum provider instalado no Core.</p>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-xs text-muted">
            <Gamepad2 size={14} className="text-accent" />
            {provider.manifest.name}
            <button
              className="cursor-pointer text-accent hover:underline"
              onClick={() => setProviderId(null)}
            >
              trocar
            </button>
          </div>

          {podeCriar && (
            <div className="flex gap-2">
              {(
                [
                  ["adopt", "Adotar pasta existente"],
                  ["create", "Criar servidor (Docker)"],
                ] as [Modo, string][]
              ).map(([m, label]) => (
                <button
                  key={m}
                  className={`flex-1 cursor-pointer rounded-lg border px-3 py-2 text-xs ${
                    modo === m
                      ? "border-accent/60 bg-surface-3 text-text"
                      : "border-border bg-surface-2 text-muted hover:text-text"
                  }`}
                  onClick={() => setModo(m)}
                >
                  {m === "create" && <Container size={13} className="mr-1 inline" />}
                  {label}
                </button>
              ))}
            </div>
          )}

          <div>
            <label className="mb-1 block text-xs text-muted">Nome</label>
            <Input
              className="w-full"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={`Ex.: Servidor ${provider.manifest.name}`}
            />
          </div>

          {modo === "adopt" ? (
            <>
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
                  É a pasta <b>na máquina onde o Aether roda</b> (o servidor), não do seu PC.
                  Aponte para a raiz do servidor
                  {contentType && (
                    <>
                      {" "}
                      — aquela que contém{" "}
                      <code className="whitespace-nowrap">
                        {contentType.default_directory || contentType.label}/
                      </code>
                    </>
                  )}
                  .
                </p>
              </div>
              {contentType && (
                /* O texto vai num <span> próprio: sem isso o flex quebra cada
                   trecho inline em um item separado e a frase fica picotada. */
                <label className="flex cursor-pointer items-start gap-2 select-none">
                  <input
                    type="checkbox"
                    checked={isContentFolder}
                    onChange={(e) => setIsContentFolder(e.target.checked)}
                    className="mt-0.5 shrink-0 accent-(--color-accent-dim)"
                  />
                  <span className="text-[13px] leading-relaxed text-muted">
                    A pasta escolhida <b>já é</b> a pasta de conteúdo (marque apenas se apontou
                    direto para a pasta de {contentType.label.toLowerCase()}).
                  </span>
                </label>
              )}
            </>
          ) : (
            <div className="space-y-1 rounded-xl border border-border bg-surface-2 p-1">
              {provider.capabilities.install && (
                <div className="flex items-center gap-3 border-b border-border px-3 py-2">
                  <div className="min-w-0 flex-1">
                    <div className="text-[13px]">Versão do servidor</div>
                    <div className="text-[11px] text-muted">
                      {versoes.isLoading
                        ? "consultando as versões disponíveis…"
                        : opcoesDeVersao.length === 0
                          ? "não foi possível listar; a mais recente será instalada"
                          : "os arquivos do jogo são baixados nesta versão."}
                    </div>
                  </div>
                  <Select
                    className="w-56"
                    value={versaoEscolhida}
                    disabled={opcoesDeVersao.length === 0}
                    onChange={(e) => setVersion(e.target.value)}
                  >
                    {opcoesDeVersao.length === 0 && <option value="">Mais recente</option>}
                    {opcoesDeVersao
                      .filter((v) => v.stable)
                      .map((v) => (
                        <option key={v.id} value={v.id}>
                          {v.label}
                        </option>
                      ))}
                    {opcoesDeVersao.some((v) => !v.stable) && (
                      <optgroup label="Instáveis">
                        {opcoesDeVersao
                          .filter((v) => !v.stable)
                          .map((v) => (
                            <option key={v.id} value={v.id}>
                              {v.label}
                            </option>
                          ))}
                      </optgroup>
                    )}
                  </Select>
                </div>
              )}

              {camposProvision
                .filter((f) => visivel(f, provisionValues))
                .map((f) => (
                  <div key={f.key} className="flex items-center gap-3 px-3 py-2">
                    <div className="min-w-0 flex-1">
                      <div className="text-[13px]">{f.label}</div>
                      {f.description && (
                        <div className="text-[11px] text-muted">{f.description}</div>
                      )}
                    </div>
                    <FieldControl
                      field={f}
                      value={provisionValues[f.key] ?? f.default}
                      onChange={(v) => {
                        setProvisionValues((prev) => ({ ...prev, [f.key]: v }));
                        setError("");
                      }}
                    />
                  </div>
                ))}
              <p className="px-3 pt-1 pb-2 text-[11px] leading-relaxed text-muted/80">
                O servidor roda isolado num container Docker; os arquivos ficam numa pasta
                gerenciada pelo Aether. A configuração é criada a partir do arquivo que a
                versão escolhida distribui, então nenhuma opção do jogo se perde.
              </p>
            </div>
          )}

          {error && <p className="text-xs text-danger">{error}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" onClick={onClose}>
              Cancelar
            </Button>
            <Button variant="primary" disabled={!pronto} onClick={() => create.mutate()}>
              Criar
            </Button>
          </div>
        </div>
      )}

      <FolderBrowser open={browserOpen} onClose={() => setBrowserOpen(false)} onPick={setRootDir} />
    </Modal>
  );
}
