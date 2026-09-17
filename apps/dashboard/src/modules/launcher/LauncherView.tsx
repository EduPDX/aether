import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Input, Select, Spinner } from "../../components/ui";
import { api, can, copyText, type Instance, type LauncherSettings } from "../../lib/api";
import { useAuth } from "../auth/AuthGate";

export function LauncherView({ instance, initialProfileId = "" }: { instance: Instance; initialProfileId?: string }) {
  const { user } = useAuth();
  const writable = can(user, "sync.write");
  const qc = useQueryClient();
  const query = useQuery({ queryKey: ["launcher", instance.id], queryFn: () => api.launcherConfig(instance.id) });
  const profiles = useQuery({ queryKey: ["sync", instance.id], queryFn: () => api.syncProfiles(instance.id) });
  const [form, setForm] = useState<LauncherSettings | null>(null);
  const [selected, setSelected] = useState(initialProfileId);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  useEffect(() => { if (query.data) setForm(query.data.settings); }, [query.data]);
  const published = (profiles.data ?? []).filter(p => p.published_at);
  const profileId = published.some(p => p.id === selected) ? selected : published[0]?.id ?? "";
  const saved = query.data?.settings;
  const dirty = JSON.stringify(form) !== JSON.stringify(saved);
  const invite = saved?.public_url && profileId ? `${saved.public_url}/api/v1/public/launcher/${profileId}` : "";
  async function save() {
    if (!form) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const data = await api.saveLauncherConfig(instance.id, form);
      qc.setQueryData(["launcher", instance.id], data);
      setForm(data.settings); setMessage("Configuração salva. Os convites usam estes endereços.");
    } catch (e) { setError(String(e)); } finally { setBusy(false); }
  }
  if (query.isError) return <p role="alert" className="p-4 text-danger">{String(query.error)}</p>;
  if (!form) return <Spinner />;
  const fields: [keyof LauncherSettings, string, string][] = [
    ["public_url", "Endereço público do Aether", "https://aether.exemplo.com"],
    ["game_address", "Endereço do Minecraft", "mc.exemplo.com:25565"],
    ["map_url", "Endereço do mapa (opcional)", "https://mapa.exemplo.com"],
    ["name", "Nome no launcher (opcional)", instance.name],
    ["cover_url", "URL de capa personalizada (opcional)", "Vazio usa a imagem do provider"],
    ["cover_credit", "Crédito da capa personalizada (opcional)", "Autor e licença"],
  ];
  return <div className="h-full overflow-y-auto p-5"><div className="mx-auto max-w-3xl space-y-5">
    <header><h2 className="text-xl font-semibold">Conecte seus jogadores</h2><p className="mt-2 text-sm text-muted">Configure uma vez. O jogador cola o convite, escolhe seu nome e adiciona o servidor.</p></header>
    {query.data?.presentation.cover_url && <figure className="overflow-hidden rounded-xl border border-border">
      <img className="h-40 w-full object-cover" src={query.data.presentation.cover_url} alt={`Capa de ${query.data.presentation.name}`} />
      {query.data.presentation.cover_credit && <figcaption className="bg-surface p-2 text-xs text-muted">{query.data.presentation.cover_credit}</figcaption>}
    </figure>}
    <section className="space-y-4 rounded-xl border border-border bg-surface p-5">
      <h3 className="font-semibold">Apresentação e endereços</h3>
      <p className="text-xs text-muted">Use endereços acessíveis aos jogadores. Estes campos são públicos; não inclua senhas. Deixe o endereço do jogo vazio para o launcher tentar detectá-lo.</p>
      {fields.map(([key, label, placeholder]) => <label key={key} className="block text-sm">{label}<Input className="mt-1 block w-full" value={form[key]} placeholder={placeholder} disabled={!writable || busy} onChange={e => { setForm({...form, [key]: e.target.value}); setMessage(""); }} /></label>)}
      <Button variant="primary" disabled={!writable || busy || !dirty || !form.public_url.trim()} onClick={save}>{busy ? "Salvando…" : "Salvar configuração"}</Button>
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
      {message && <p role="status" className="text-sm text-accent">{message}</p>}
    </section>
    <section className="space-y-3 rounded-xl border border-border bg-surface p-5">
      <h3 className="font-semibold">Convite para o launcher</h3>
      {profiles.isError ? <p role="alert" className="text-danger">{String(profiles.error)}</p> : published.length === 0 ? <p className="text-sm text-muted">Publique um perfil na aba Sync para disponibilizar o convite.</p> : <>
        <label className="block text-sm">Perfil de sincronização<Select className="mt-1 block w-full" value={profileId} onChange={e => { setSelected(e.target.value); setMessage(""); }}>{published.map(p => <option key={p.id} value={p.id}>{p.name} · {p.channel}</option>)}</Select></label>
        <Input aria-label="Convite" className="w-full" readOnly value={invite} placeholder="Salve o endereço público do Aether primeiro" />
        <Button disabled={!invite || dirty} onClick={async () => { setMessage(await copyText(invite) ? "Convite copiado! Envie ao jogador para colar no Aether Launcher." : "Não foi possível copiar. Selecione o convite e copie manualmente."); }}>Copiar convite</Button>
        {dirty && <p className="text-xs text-warn">Salve as alterações antes de copiar o convite.</p>}
        <p className="text-xs text-muted">O convite acompanha mudanças de mapa, capa e endereço do jogo. Se o domínio do Aether mudar, mantenha o antigo acessível ou envie um novo convite. O convite não concede acesso ao painel.</p>
      </>}
    </section>
  </div></div>;
}
