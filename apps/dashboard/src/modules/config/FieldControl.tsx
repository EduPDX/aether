import { Eye, EyeOff } from "lucide-react";
import { useState } from "react";
import { Input, Select, Switch } from "../../components/ui";
import type { ConfigFieldDef } from "../../lib/api";

/** Controle de um campo de schema (config e provision usam o mesmo). */
export function FieldControl({
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
