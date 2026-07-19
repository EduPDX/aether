import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, EyeOff, Save, Settings2, SlidersHorizontal } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Badge, Button, Input, Panel, Select, Spinner, Switch } from "../../components/ui";
import { ServerIconCard } from "./ServerIconCard";
import type { ConfigFieldDef, Instance } from "../../lib/api";
import { api } from "../../lib/api";

function FieldControl({
  field,
  value,
  onChange,
}: {
  field: ConfigFieldDef;
  value: string;
  onChange: (v: string) => void;
}) {
  if (field.type === "boolean") {
    return (
      <Switch
        checked={value === "true"}
        onChange={() => onChange(value === "true" ? "false" : "true")}
      />
    );
  }
  if (field.type === "enum") {
    return (
      <Select value={value} onChange={(e) => onChange(e.target.value)}>
        {field.options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </Select>
    );
  }
  if (field.type === "password") return <PasswordControl value={value} onChange={onChange} />;
  return (
    <Input
      className="w-56"
      type={field.type === "integer" ? "number" : "text"}
      min={field.minimum ?? undefined}
      max={field.maximum ?? undefined}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}

/** Senha começa oculta; sem isso a do RCON ficaria à mostra na tela. */
function PasswordControl({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [visivel, setVisivel] = useState(false);
  return (
    <span className="flex items-center gap-1.5">
      <Input
        className="w-56"
        type={visivel ? "text" : "password"}
        value={value}
        placeholder="sem senha definida"
        onChange={(e) => onChange(e.target.value)}
      />
      <button
        type="button"
        title={visivel ? "Ocultar" : "Mostrar"}
        className="cursor-pointer text-muted hover:text-text"
        onClick={() => setVisivel((v) => !v)}
      >
        {visivel ? <EyeOff size={15} /> : <Eye size={15} />}
      </button>
    </span>
  );
}

export function ConfigView({ instance }: { instance: Instance }) {
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: ["config", instance.id],
    queryFn: () => api.configs(instance.id),
  });

  const config = query.data?.[0];
  const [values, setValues] = useState<Record<string, string>>({});
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [mostrarAvancadas, setMostrarAvancadas] = useState(false);

  useEffect(() => {
    if (!config) return;
    const initial: Record<string, string> = {};
    for (const f of config.schema.fields) {
      initial[f.key] = config.values[f.key] ?? f.default;
    }
    setValues(initial);
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
    mutationFn: () => api.updateConfig(instance.id, config!.schema.id, values),
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
          <Button variant="primary" disabled={!dirty || save.isPending} onClick={() => save.mutate()}>
            <Save size={13} /> Salvar
          </Button>
        </span>
      </div>

      <div className="mx-auto w-full max-w-4xl space-y-4 p-4">
        <ServerIconCard instance={instance} />

        {sections.map(([section, fields]) => {
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
