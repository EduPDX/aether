import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Save } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Badge, Button, Input, Select, Spinner, Switch } from "../../components/ui";
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
  return (
    <Input
      className="w-56"
      type={field.type === "integer" ? "number" : "text"}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
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
        <span className="ml-auto">
          <Button variant="primary" disabled={!dirty || save.isPending} onClick={() => save.mutate()}>
            <Save size={13} /> Salvar
          </Button>
        </span>
      </div>

      <div className="mx-auto w-full max-w-3xl space-y-6 p-4">
        {sections.map(([section, fields]) => (
          <section key={section}>
            <h3 className="mb-2 text-[11px] font-semibold tracking-wider text-muted uppercase">
              {section}
            </h3>
            <div className="divide-y divide-border rounded-lg border border-border bg-surface">
              {fields.map((f) => (
                <div key={f.key} className="flex items-center gap-4 px-4 py-2.5">
                  <div className="min-w-0 flex-1">
                    <div className="text-sm">{f.label}</div>
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
          </section>
        ))}
      </div>
    </div>
  );
}
