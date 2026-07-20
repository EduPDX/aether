import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Container, FolderSearch, Gamepad2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Button, Input, Modal, Select } from "../../components/ui";
import type { ProviderInfo } from "../../lib/api";
import { api } from "../../lib/api";
import { useProviders } from "../../lib/providers";
import { FieldControl } from "../config/FieldControl";
import { valoresIniciais, visivel } from "../config/fields";
import { FolderBrowser } from "./FolderBrowser";

type Modo = "adopt" | "create";

/** Uma etapa por decisão. O schema de provisionamento de um jogo pode ter
 *  quinze campos — despejados de uma vez, o modal vira uma página de rolagem
 *  e a primeira pergunta (o nome) fica escondida no topo. */
type Etapa = "modo" | "identidade" | "config" | "revisao";

const PASSOS: Record<Modo, Etapa[]> = {
  create: ["modo", "identidade", "config", "revisao"],
  // Adotar pasta não tem o que configurar: os arquivos já existem.
  adopt: ["modo", "identidade", "revisao"],
};

const TITULO: Record<Etapa, string> = {
  modo: "Como criar",
  identidade: "Identificação",
  config: "Configuração do servidor",
  revisao: "Revisão",
};

/**
 * Criação de instância como assistente: escolher o jogo, então avançar por
 * etapas curtas até a revisão. O formulário de criação é gerado do
 * provision_schema do provider — a interface não conhece nenhum jogo em
 * particular.
 */
export function CreateInstanceDialog({
  open,
  onClose,
  providerId: providerFixo,
}: {
  open: boolean;
  onClose: () => void;
  /** Vindo da página do jogo: o jogo já foi escolhido no catálogo. */
  providerId?: string | null;
}) {
  const qc = useQueryClient();
  const providers = useProviders();
  const [providerId, setProviderId] = useState<string | null>(providerFixo ?? null);
  const [modo, setModo] = useState<Modo>("adopt");
  const [etapa, setEtapa] = useState<Etapa>("modo");
  const [name, setName] = useState("");
  const [rootDir, setRootDir] = useState("");
  const [isContentFolder, setIsContentFolder] = useState(false);
  const [provisionValues, setProvisionValues] = useState<Record<string, string>>({});
  const [version, setVersion] = useState("");
  const [browserOpen, setBrowserOpen] = useState(false);
  const [error, setError] = useState("");

  const provider = providers.find((p) => p.manifest.id === providerId);
  const podeCriar = Boolean(provider?.capabilities.container && provider?.capabilities.provision);
  const contentType = provider?.content_types[0];

  const camposProvision = useMemo(() => provider?.provision_schema?.fields ?? [], [provider]);

  // Os padrões precisam existir desde o início: sem eles a dependência de
  // "mundo gerado" nunca bate e os campos de semente/tamanho não aparecem.
  useEffect(() => {
    setProvisionValues(camposProvision.length ? valoresIniciais(camposProvision) : {});
  }, [camposProvision]);

  const versoes = useQuery({
    queryKey: ["versions", providerId],
    queryFn: () => api.providerVersions(providerId!),
    enabled: Boolean(providerId) && Boolean(provider?.capabilities.install) && modo === "create",
    // O Core guarda a lista por 10 minutos; repetir a consulta aqui só
    // adiciona espera à tela.
    staleTime: 10 * 60 * 1000,
  });
  const opcoesDeVersao = versoes.data ?? [];
  const versaoEscolhida = version || opcoesDeVersao.find((v) => v.stable)?.id || "";

  // Reabrir o diálogo a partir de outra página do jogo precisa trocar o jogo.
  useEffect(() => {
    if (providerFixo) setProviderId(providerFixo);
  }, [providerFixo]);

  const reset = () => {
    setProviderId(providerFixo ?? null);
    setModo("adopt");
    setEtapa("modo");
    setName("");
    setRootDir("");
    setIsContentFolder(false);
    setProvisionValues({});
    setVersion("");
    setError("");
  };

  const visiveis = camposProvision.filter((f) => visivel(f, provisionValues));

  const create = useMutation({
    mutationFn: () => {
      if (modo === "create") {
        // Campo escondido pela dependência não vai: mandar semente de mapa
        // pré-gerado gravaria configuração que o jogo ignora.
        const values: Record<string, string> = {};
        for (const f of visiveis) values[f.key] = provisionValues[f.key] ?? f.default;
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
        content_dirs: isContentFolder && contentType ? { [contentType.id]: "." } : {},
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["instances"] });
      reset();
      onClose();
    },
    onError: (e) => setError(String(e)),
  });

  const passos = PASSOS[podeCriar ? modo : "adopt"];
  const indice = Math.max(0, passos.indexOf(etapa));
  const ultima = indice === passos.length - 1;
  // Só o que impede de seguir; o resto é conferido na revisão.
  const podeAvancar =
    etapa === "identidade" ? Boolean(name.trim() && (modo === "create" || rootDir.trim())) : true;

  const avancar = () => setEtapa(passos[Math.min(indice + 1, passos.length - 1)]);
  const voltar = () => setEtapa(passos[Math.max(indice - 1, 0)]);

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
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-2 text-xs text-muted">
            <Gamepad2 size={14} className="text-accent" />
            {provider.manifest.name}
            {!providerFixo && (
              <button
                className="cursor-pointer text-accent hover:underline"
                onClick={() => setProviderId(null)}
              >
                trocar
              </button>
            )}
          </div>

          {/* Trilha das etapas: mostra onde se está e quanto falta. */}
          <ol className="flex items-center gap-1.5 text-[11px]">
            {passos.map((p, i) => (
              <li key={p} className="flex items-center gap-1.5">
                <span
                  className={`flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 ${
                    i < indice
                      ? "bg-accent/20 text-accent"
                      : i === indice
                        ? "bg-accent text-bg"
                        : "bg-surface-3 text-muted"
                  }`}
                >
                  {i < indice ? <Check size={11} /> : i + 1}
                </span>
                <span className={i === indice ? "text-text" : "text-muted"}>{TITULO[p]}</span>
                {i < passos.length - 1 && <span className="text-muted/40">›</span>}
              </li>
            ))}
          </ol>

          {/* Altura fixa com rolagem interna: é o que impede o modal de crescer
              a cada campo que o jogo declara. */}
          <div className="h-72 space-y-3 overflow-y-auto pr-1">
            {etapa === "modo" && (
              <>
                {podeCriar ? (
                  (
                    [
                      [
                        "create",
                        "Criar servidor (Docker)",
                        "O Aether baixa o jogo e roda isolado num container. É o caminho para quem não tem servidor ainda.",
                      ],
                      [
                        "adopt",
                        "Adotar pasta existente",
                        "Aponte uma pasta que já tem um servidor instalado na máquina do Aether.",
                      ],
                    ] as [Modo, string, string][]
                  ).map(([m, label, ajuda]) => (
                    <button
                      key={m}
                      onClick={() => {
                        setModo(m);
                        setEtapa("identidade");
                      }}
                      className={`flex w-full cursor-pointer items-start gap-3 rounded-xl border px-4 py-3 text-left ${
                        modo === m
                          ? "border-accent/60 bg-surface-3"
                          : "border-border bg-surface-2 hover:border-accent/40"
                      }`}
                    >
                      {m === "create" ? (
                        <Container size={16} className="mt-0.5 shrink-0 text-accent" />
                      ) : (
                        <FolderSearch size={16} className="mt-0.5 shrink-0 text-accent" />
                      )}
                      <span>
                        <span className="block text-[13px] font-medium">{label}</span>
                        <span className="block text-[11px] leading-relaxed text-muted">
                          {ajuda}
                        </span>
                      </span>
                    </button>
                  ))
                ) : (
                  <p className="text-[13px] text-muted">
                    Este jogo é gerenciado apontando uma pasta que já existe na máquina do Aether.
                  </p>
                )}
              </>
            )}

            {etapa === "identidade" && (
              <>
                <div>
                  <label className="mb-1 block text-xs text-muted">Nome</label>
                  <Input
                    className="w-full"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder={`Ex.: Servidor ${provider.manifest.name}`}
                  />
                </div>

                {modo === "create" ? (
                  provider.capabilities.install && (
                    <div>
                      <label className="mb-1 block text-xs text-muted">Versão do servidor</label>
                      <Select
                        className="w-full"
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
                      <p className="mt-1 text-[11px] text-muted">
                        {versoes.isLoading
                          ? "consultando as versões disponíveis…"
                          : opcoesDeVersao.length === 0
                            ? "não foi possível listar; a mais recente será instalada"
                            : "os arquivos do jogo são baixados nesta versão."}
                      </p>
                    </div>
                  )
                ) : (
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
                      /* O texto vai num <span> próprio: sem isso o flex quebra
                         cada trecho inline em um item e a frase fica picotada. */
                      <label className="flex cursor-pointer items-start gap-2 select-none">
                        <input
                          type="checkbox"
                          checked={isContentFolder}
                          onChange={(e) => setIsContentFolder(e.target.checked)}
                          className="mt-0.5 shrink-0 accent-(--color-accent-dim)"
                        />
                        <span className="text-[13px] leading-relaxed text-muted">
                          A pasta escolhida <b>já é</b> a pasta de conteúdo (marque apenas se
                          apontou direto para a pasta de {contentType.label.toLowerCase()}).
                        </span>
                      </label>
                    )}
                  </>
                )}
              </>
            )}

            {etapa === "config" && (
              <div className="space-y-1 rounded-xl border border-border bg-surface-2 p-1">
                {visiveis.map((f) => (
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
                {visiveis.length === 0 && (
                  <p className="px-3 py-2 text-[13px] text-muted">
                    Este jogo não pede nada na criação; tudo pode ser ajustado depois.
                  </p>
                )}
              </div>
            )}

            {etapa === "revisao" && (
              <div className="space-y-1 rounded-xl border border-border bg-surface-2 p-3 text-[13px]">
                <Linha rotulo="Jogo" valor={provider.manifest.name} />
                <Linha rotulo="Nome" valor={name || "—"} />
                {modo === "create" ? (
                  <>
                    <Linha
                      rotulo="Onde roda"
                      valor="Container Docker (pasta gerenciada pelo Aether)"
                    />
                    {provider.capabilities.install && (
                      <Linha rotulo="Versão" valor={versaoEscolhida || "mais recente"} />
                    )}
                    {visiveis.map((f) => (
                      <Linha
                        key={f.key}
                        rotulo={f.label}
                        valor={provisionValues[f.key] || f.default || "—"}
                      />
                    ))}
                  </>
                ) : (
                  <Linha rotulo="Pasta" valor={rootDir || "—"} />
                )}
                {modo === "create" && (
                  <p className="pt-2 text-[11px] leading-relaxed text-muted/80">
                    A configuração é criada a partir do arquivo que a versão escolhida distribui,
                    então nenhuma opção do jogo se perde. O download começa assim que a instância
                    for criada e o progresso aparece no console.
                  </p>
                )}
              </div>
            )}
          </div>

          {error && <p className="text-xs text-danger">{error}</p>}
          <div className="flex items-center justify-between gap-2 border-t border-border pt-3">
            <Button variant="ghost" onClick={indice === 0 ? onClose : voltar}>
              {indice === 0 ? "Cancelar" : "Voltar"}
            </Button>
            {ultima ? (
              <Button
                variant="primary"
                disabled={!podeAvancar || create.isPending}
                onClick={() => create.mutate()}
              >
                {create.isPending ? "Criando…" : "Criar"}
              </Button>
            ) : (
              <Button variant="primary" disabled={!podeAvancar} onClick={avancar}>
                Avançar
              </Button>
            )}
          </div>
        </div>
      )}

      <FolderBrowser open={browserOpen} onClose={() => setBrowserOpen(false)} onPick={setRootDir} />
    </Modal>
  );
}

function Linha({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-border/60 py-1 last:border-0">
      <span className="text-muted">{rotulo}</span>
      <span className="min-w-0 truncate text-right">{valor}</span>
    </div>
  );
}
