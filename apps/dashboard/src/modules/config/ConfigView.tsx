import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, FileCode2, Save, Settings2, SlidersHorizontal } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Badge, Button, Panel, Spinner } from "../../components/ui";
import { FieldControl } from "./FieldControl";
import { RawConfigEditor } from "./RawConfigEditor";
import { ServerIconCard } from "./ServerIconCard";
import { valoresIniciais, visivel } from "./fields";
import type { ConfigFieldDef, Instance } from "../../lib/api";
import { api } from "../../lib/api";
import { useProvider } from "../../lib/providers";

type Modo = "basico" | "avancado";

export function ConfigView({ instance }: { instance: Instance }) {
  const qc = useQueryClient();
  const provider = useProvider(instance.provider_id);
  const query = useQuery({
    queryKey: ["config", instance.id],
    queryFn: () => api.configs(instance.id),
  });

  const config = query.data?.[0];
  const [modo, setModo] = useState<Modo>("basico");
  const [values, setValues] = useState<Record<string, string>>({});
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [mostrarAvancadas, setMostrarAvancadas] = useState(false);

  useEffect(() => {
    if (!config) return;
    setValues(valoresIniciais(config.schema.fields, config.values));
    setDirty(false);
  }, [config]);

  const sections = useMemo(() => {
    if (!config) return [];
    const by = new Map<string, ConfigFieldDef[]>();
    for (const f of config.schema.fields) {
      const key = f.section || "Outros";
      if (!by.has(key)) by.set(key, []);
      by.get(key)!.push(f);
    }
    return [...by.entries()];
  }, [config]);

  const save = useMutation({
    mutationFn: () =>
      // Campo escondido pela dependência não vai junto: mandar a semente de
      // um mundo pré-gerado escreveria configuração que o jogo ignora.
      api.updateConfig(
        instance.id,
        config!.schema.id,
        Object.fromEntries(
          config!.schema.fields
            .filter((f) => visivel(f, values))
            .map((f) => [f.key, values[f.key] ?? f.default]),
        ),
      ),
    onSuccess: () => {
      setDirty(false);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
      qc.invalidateQueries({ queryKey: ["config", instance.id] });
    },
    onError: (e) => setError(String(e)),
  });

  if (query.isLoading) return <Spinner />;
  if (!config)
    return (
      <div className="p-6 text-sm text-muted">
        Este provider não expõe configurações por formulário.
      </div>
    );

  const seletorDeModo = (
    <span className="flex overflow-hidden rounded-lg border border-border">
      {(
        [
          ["basico", "Básico", <Settings2 key="b" size={13} />],
          ["avancado", "Avançado", <FileCode2 key="a" size={13} />],
        ] as [Modo, string, React.ReactNode][]
      ).map(([m, rotulo, icone]) => (
        <button
          key={m}
          onClick={() => setModo(m)}
          title={
            m === "basico"
              ? "Formulário com as opções que o painel conhece"
              : "Editar o arquivo inteiro, inclusive o que o painel não mapeia"
          }
          className={`flex cursor-pointer items-center gap-1.5 px-3 py-1.5 text-xs ${
            modo === m ? "bg-surface-3 text-text" : "text-muted hover:bg-surface-2 hover:text-text"
          }`}
        >
          {icone}
          {rotulo}
        </button>
      ))}
    </span>
  );

  if (modo === "avancado") {
    return (
      <div className="flex h-full flex-col">
        <div className="flex items-center gap-3 border-b border-border px-4 py-2">
          <span className="text-sm font-semibold">{config.schema.label}</span>
          <span className="ml-auto">{seletorDeModo}</span>
        </div>
        <div className="min-h-0 flex-1">
          <RawConfigEditor instance={instance} schemaId={config.schema.id} />
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <div className="sticky top-0 z-10 flex items-center gap-3 border-b border-border bg-bg px-4 py-2">
        <span className="text-sm font-semibold">{config.schema.label}</span>
        {!config.file_exists && (
          <Badge tone="orange" title="O arquivo será criado ao salvar">
            arquivo ainda não existe
          </Badge>
        )}
        {saved && <Badge tone="green">salvo ✓</Badge>}
        {error && <span className="text-xs text-danger">{error}</span>}
        <span className="ml-auto flex items-center gap-2">
          <label className="flex cursor-pointer items-center gap-1.5 text-xs text-muted">
            <input
              type="checkbox"
              className="accent-(--color-accent-dim)"
              checked={mostrarAvancadas}
              onChange={(e) => setMostrarAvancadas(e.target.checked)}
            />
            <SlidersHorizontal size={13} />
            <span>Opções avançadas</span>
          </label>
          {seletorDeModo}
          <Button variant="primary" disabled={!dirty || save.isPending} onClick={() => save.mutate()}>
            <Save size={13} /> Salvar
          </Button>
        </span>
      </div>

      <div className="mx-auto w-full max-w-4xl space-y-4 p-4">
        {/* Avisos do provider: valores válidos no formato mas errados na
            prática — como um mundo apontando para pasta que não existe. */}
        {(config.warnings ?? []).map((a) => (
          <div
            key={a.key}
            className={`flex items-start gap-3 rounded-xl border p-4 ${
              a.level === "error"
                ? "border-danger/50 bg-danger/10"
                : "border-warn/50 bg-warn/10"
            }`}
          >
            <AlertTriangle
              size={18}
              className={`mt-0.5 shrink-0 ${a.level === "error" ? "text-danger" : "text-warn"}`}
            />
            <div className="min-w-0">
              <div className="text-sm font-semibold">
                {a.level === "error" ? "Isto vai dar problema" : "Atenção"}
                <code className="ml-2 text-[11px] font-normal text-muted">{a.key}</code>
              </div>
              <p className="mt-0.5 text-sm text-muted">{a.message}</p>
            </div>
          </div>
        ))}

        {/* Só para jogos que têm a noção de ícone de servidor no disco. */}
        {provider?.manifest.icon_spec && <ServerIconCard instance={instance} />}

        {sections.map(([section, todos]) => {
          // Campo cuja dependência não bate some: com mapa pré-gerado, semente
          // e tamanho não fazem sentido nenhum.
          const fields = todos.filter((f) => visivel(f, values));
          const essenciais = fields.filter((f) => !f.advanced);
          const avancadas = fields.filter((f) => f.advanced);
          const visiveis = mostrarAvancadas ? fields : essenciais;
          if (visiveis.length === 0) return null;
          return (
            <Panel
              key={section}
              title={section}
              icon={<Settings2 size={15} />}
              hint={
                avancadas.length > 0 && !mostrarAvancadas
                  ? `${avancadas.length} opção(ões) avançada(s) oculta(s)`
                  : undefined
              }
              bodyClassName="px-0 pb-0"
            >
              <div className="divide-y divide-border border-t border-border">
                {visiveis.map((f) => (
                  <div key={f.key} className="flex items-center gap-4 px-4 py-2.5">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 text-sm">
                        {f.label}
                        {f.advanced && <Badge tone="neutral">avançado</Badge>}
                      </div>
                      <div className="text-[11px] text-muted">
                        <code>{f.key}</code>
                        {f.description && ` — ${f.description}`}
                      </div>
                    </div>
                    <FieldControl
                      field={f}
                      value={values[f.key] ?? ""}
                      onChange={(v) => {
                        setValues((prev) => ({ ...prev, [f.key]: v }));
                        setDirty(true);
                        setError("");
                      }}
                    />
                  </div>
                ))}
              </div>
            </Panel>
          );
        })}
      </div>
    </div>
  );
}
