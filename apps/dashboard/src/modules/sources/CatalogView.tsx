import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowUpCircle,
  ChevronLeft,
  ChevronRight,
  Download,
  ExternalLink,
  PackagePlus,
  RefreshCw,
  Search,
} from "lucide-react";
import { useState } from "react";
import { useDialog } from "../../components/Dialog";
import { Badge, Button, Input, Panel, Select, Spinner, StatTile } from "../../components/ui";
import type { CatalogItem, CatalogVersion, Instance } from "../../lib/api";
import { api, can, formatBytes } from "../../lib/api";
import { useAuth } from "../auth/AuthGate";

function milhares(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${Math.round(n / 1000)}k`;
  return String(n);
}

export function CatalogView({ instance }: { instance: Instance }) {
  const qc = useQueryClient();
  const dialog = useDialog();
  const { user } = useAuth();
  const podeInstalar = can(user, "content.write");

  const [busca, setBusca] = useState("");
  const [enviada, setEnviada] = useState("");
  const [destino, setDestino] = useState("mod");
  const [todasVersoes, setTodasVersoes] = useState(false);
  const [erro, setErro] = useState("");
  const [ok, setOk] = useState("");
  const [checarUpdates, setChecarUpdates] = useState(false);
  const [planejando, setPlanejando] = useState("");
  const [pagina, setPagina] = useState(0);
  const [categorias, setCategorias] = useState<string[]>([]);
  const [loaderFiltro, setLoaderFiltro] = useState("");

  const versaoJogo = (instance.provider_data?.game_version as string) || null;
  const loader = (instance.provider_data?.loader as string) || null;

  const POR_PAGINA = 24;
  // Sem termo de busca a consulta continua valendo: o catálogo devolve os mais
  // baixados, que é o que o site do Modrinth mostra ao abrir.
  const resultados = useQuery({
    queryKey: ["catalogo", instance.id, enviada, todasVersoes, pagina, categorias, loaderFiltro],
    queryFn: () =>
      api.searchCatalog(instance.id, enviada, {
        allVersions: todasVersoes,
        offset: pagina * POR_PAGINA,
        limit: POR_PAGINA,
        categories: categorias,
        loader: loaderFiltro || undefined,
      }),
    placeholderData: (anterior) => anterior,
  });

  const filtros = useQuery({
    queryKey: ["catalogo-filtros", instance.id],
    queryFn: () => api.catalogFilters(instance.id),
    staleTime: Infinity,
  });

  function alternarCategoria(id: string) {
    setPagina(0);
    setCategorias((atual) =>
      atual.includes(id) ? atual.filter((c) => c !== id) : [...atual, id],
    );
  }

  const updates = useQuery({
    queryKey: ["catalogo-updates", instance.id, destino],
    queryFn: () => api.catalogUpdates(instance.id, destino),
    enabled: checarUpdates,
    retry: false,
  });

  const instalar = useMutation({
    mutationFn: (v: { version_id: string; overwrite?: boolean; withDeps?: boolean }) =>
      api.installFromCatalog(instance.id, {
        source_id: "modrinth",
        version_id: v.version_id,
        type: destino,
        overwrite: v.overwrite,
        with_dependencies: v.withDeps,
      }),
    onSuccess: (r) => {
      setErro("");
      setOk(
        "installed" in r
          ? `${r.count} arquivo(s) instalado(s): ${r.installed.map((i) => i.file).join(", ")}`
          : `${r.file} instalado (${formatBytes(r.size)}).`,
      );
      qc.invalidateQueries({ queryKey: ["content", instance.id] });
      qc.invalidateQueries({ queryKey: ["catalogo-updates", instance.id] });
    },
    onError: (e) => setErro(String(e instanceof Error ? e.message : e)),
  });

  /**
   * Monta o plano antes de baixar qualquer coisa e mostra o que vai acontecer.
   *
   * O plano existe para o usuário ver "vai instalar 4 arquivos" em vez de
   * descobrir depois, e para uma dependência sem versão compatível bloquear
   * tudo antes de o primeiro arquivo entrar na pasta.
   */
  async function instalarMaisRecente(item: CatalogItem) {
    setErro("");
    setPlanejando(item.project_id);
    try {
      const versoes = await api.catalogVersions(
        instance.id,
        item.project_id,
        "modrinth",
        todasVersoes,
      );
      if (versoes.length === 0) {
        setErro(
          `${item.name} não publica versão para ${loader ?? "este loader"} ${versaoJogo ?? ""}.`,
        );
        return;
      }
      const v: CatalogVersion = versoes[0];
      const plano = await api.planInstall(instance.id, {
        source_id: "modrinth",
        version_id: v.version_id,
        type: destino,
      });

      const deps = plano.items.filter((i) => i.required_by !== null);
      const onde = destino === "mod_client" ? "mods do cliente" : "mods do servidor";

      if (!plano.ok) {
        await dialog.notify({
          title: "Não dá para instalar",
          tone: "danger",
          message: (
            <>
              <b>{item.name}</b> exige dependências que não têm versão para {loader} {versaoJogo}:
              <br />
              <code className="text-xs">{plano.missing.join(", ")}</code>
              <br />
              Instalar assim deixaria o servidor sem subir.
            </>
          ),
          confirmText: "Entendi",
        });
        return;
      }

      const confirmado = await dialog.confirm({
        title: `Instalar ${item.name}`,
        message: (
          <>
            {plano.items.length === 1 ? (
              <>
                <b>{v.file_name}</b> ({formatBytes(v.size)}) em {onde}.
              </>
            ) : (
              <>
                <b>{plano.items.length} arquivos</b> ({formatBytes(plano.total_size)}) em {onde} —
                o mod e {deps.length} dependência(s) obrigatória(s):
                <span className="mt-2 block text-left text-xs text-muted">
                  {plano.items.map((i) => (
                    <span key={i.version_id} className="block truncate">
                      {i.required_by ? "└ " : ""}
                      {i.file_name}
                    </span>
                  ))}
                </span>
              </>
            )}
            {plano.already_installed.length > 0 && (
              <span className="mt-2 block text-xs text-muted">
                {plano.already_installed.length} dependência(s) já estão instaladas.
              </span>
            )}
            {plano.conflicts.length > 0 && (
              <span className="mt-2 block text-xs text-warn">
                Atenção: este mod se declara incompatível com {plano.conflicts.length} mod(s) que
                você já tem instalado.
              </span>
            )}
          </>
        ),
        confirmText: plano.items.length === 1 ? "Instalar" : `Instalar ${plano.items.length}`,
      });
      if (confirmado)
        instalar.mutate({ version_id: v.version_id, withDeps: plano.items.length > 1 });
    } catch (e) {
      setErro(String(e instanceof Error ? e.message : e));
    } finally {
      setPlanejando("");
    }
  }

  const lista = resultados.data ?? [];
  const disponiveis = updates.data ?? [];

  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="mx-auto flex w-full max-w-[1900px] flex-col gap-4">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatTile
            icon={<PackagePlus size={14} />}
            label="Catálogo"
            value="Modrinth"
            sub="aberto, sem credencial"
          />
          <StatTile
            icon={<Search size={14} />}
            label="Resultados"
            value={String(lista.length)}
            sub={enviada ? `para “${enviada}”` : "faça uma busca"}
          />
          <StatTile
            icon={<ArrowUpCircle size={14} />}
            label="Atualizações"
            value={checarUpdates && !updates.isLoading ? String(disponiveis.length) : "—"}
            sub={checarUpdates ? "mods com versão nova" : "não verificado ainda"}
            tone={disponiveis.length > 0 ? "warn" : undefined}
          />
          <StatTile
            icon={<Download size={14} />}
            label="Compatibilidade"
            value={versaoJogo ?? "?"}
            sub={loader ? `filtrando por ${loader}` : "loader não detectado"}
          />
        </div>

        {erro && <p className="text-sm text-danger">{erro}</p>}
        {ok && <p className="text-sm text-accent">{ok}</p>}

        <Panel
          title={
            enviada
              ? `Resultados para “${enviada}”`
              : categorias.length > 0 || loaderFiltro
                ? "Mods filtrados"
                : "Mods populares"
          }
          icon={<Search size={15} />}
          hint={
            versaoJogo
              ? `Filtrando por ${loader ?? "loader"} ${versaoJogo} — só aparece o que roda nesta instância.`
              : "A versão do jogo não foi detectada; os resultados não estão filtrados."
          }
          aside={
            <span className="flex items-center gap-2">
              <Select
                className="py-1 text-xs"
                value={destino}
                onChange={(e) => setDestino(e.target.value)}
                title="Onde instalar"
              >
                <option value="mod">Mods do servidor</option>
                <option value="mod_client">Mods do cliente</option>
              </Select>
              <label className="flex cursor-pointer items-center gap-1.5 text-xs text-muted">
                <input
                  type="checkbox"
                  className="accent-(--color-accent-dim)"
                  checked={todasVersoes}
                  onChange={(e) => setTodasVersoes(e.target.checked)}
                />
                <span>Qualquer versão</span>
              </label>
            </span>
          }
        >
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              setOk("");
              setPagina(0);
              setEnviada(busca);
            }}
          >
            <Input
              className="flex-1"
              placeholder="Nome do mod (ex.: sodium, jei, create)…"
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
            />
            <Button variant="primary" type="submit" disabled={busca.trim().length < 2}>
              <Search size={14} /> Buscar
            </Button>
            {(enviada || categorias.length > 0 || loaderFiltro) && (
              <Button
                variant="ghost"
                type="button"
                onClick={() => {
                  setBusca("");
                  setEnviada("");
                  setCategorias([]);
                  setLoaderFiltro("");
                  setPagina(0);
                }}
              >
                Limpar
              </Button>
            )}
          </form>

          {/* Filtros por categoria e loader — o catálogo declara quais existem,
              então outro jogo traz a lista dele sem mudar esta tela. */}
          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            {(filtros.data?.loaders ?? []).length > 0 && (
              <>
                <span className="mr-1 text-[11px] text-muted">Loader:</span>
                {(filtros.data?.loaders ?? []).map((l) => (
                  <button
                    key={l.id}
                    onClick={() => {
                      setPagina(0);
                      setLoaderFiltro(loaderFiltro === l.id ? "" : l.id);
                    }}
                    className={`cursor-pointer rounded-full border px-2.5 py-1 text-[11px] transition-colors ${
                      loaderFiltro === l.id
                        ? "border-accent bg-accent/15 text-accent"
                        : "border-border text-muted hover:border-muted hover:text-text"
                    }`}
                  >
                    {l.label}
                  </button>
                ))}
                <span className="mx-1 h-4 w-px bg-border" />
              </>
            )}
            {(filtros.data?.categories ?? []).map((c) => (
              <button
                key={c.id}
                onClick={() => alternarCategoria(c.id)}
                className={`cursor-pointer rounded-full border px-2.5 py-1 text-[11px] transition-colors ${
                  categorias.includes(c.id)
                    ? "border-accent bg-accent/15 text-accent"
                    : "border-border text-muted hover:border-muted hover:text-text"
                }`}
              >
                {c.label}
              </button>
            ))}
          </div>

          {resultados.isLoading && <Spinner />}
          {resultados.isError && (
            <p className="mt-3 text-sm text-danger">
              Não consegui falar com o catálogo: {String(resultados.error)}
            </p>
          )}
          {enviada && !resultados.isLoading && lista.length === 0 && (
            <p className="mt-4 text-sm text-muted">
              Nada encontrado. Se o mod existe mas não aparece, marque “Qualquer versão” — pode
              não haver publicação para {loader} {versaoJogo}.
            </p>
          )}

          <div className="mt-3 grid gap-2.5 md:grid-cols-2 2xl:grid-cols-3">
            {lista.map((item) => (
              <div
                key={item.project_id}
                className="flex gap-3 rounded-lg border border-border bg-surface-2 p-3"
              >
                {item.icon_url ? (
                  <img
                    src={item.icon_url}
                    alt=""
                    className="h-12 w-12 shrink-0 rounded-md bg-surface-3 object-contain"
                  />
                ) : (
                  <div className="h-12 w-12 shrink-0 rounded-md bg-surface-3" />
                )}
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-semibold">{item.name}</span>
                    <Badge tone="neutral">{milhares(item.downloads)}</Badge>
                  </div>
                  <p className="mt-0.5 line-clamp-2 text-xs text-muted">{item.summary}</p>
                  <div className="mt-1.5 flex items-center gap-2">
                    {podeInstalar && (
                      <Button
                        variant="primary"
                        disabled={instalar.isPending || planejando === item.project_id}
                        onClick={() => instalarMaisRecente(item)}
                      >
                        <Download size={13} />
                        {planejando === item.project_id ? "Verificando…" : "Instalar"}
                      </Button>
                    )}
                    {item.page_url && (
                      <a
                        href={item.page_url}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="flex items-center gap-1 text-[11px] text-muted hover:text-text"
                      >
                        <ExternalLink size={11} /> ver no site
                      </a>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {(lista.length > 0 || pagina > 0) && (
            <div className="mt-4 flex items-center justify-center gap-3">
              <Button disabled={pagina === 0 || resultados.isFetching} onClick={() => setPagina((p) => p - 1)}>
                <ChevronLeft size={14} /> Anterior
              </Button>
              <span className="text-xs text-muted">página {pagina + 1}</span>
              <Button
                disabled={lista.length < POR_PAGINA || resultados.isFetching}
                onClick={() => setPagina((p) => p + 1)}
              >
                Próxima <ChevronRight size={14} />
              </Button>
            </div>
          )}
        </Panel>

        <Panel
          title="Atualizações disponíveis"
          icon={<ArrowUpCircle size={15} />}
          hint="Cada arquivo instalado é identificado pelo hash, então funciona mesmo com o .jar renomeado. Em instalações grandes leva alguns segundos."
          aside={
            <Button
              disabled={updates.isFetching}
              onClick={() => {
                setChecarUpdates(true);
                updates.refetch();
              }}
            >
              <RefreshCw size={13} className={updates.isFetching ? "animate-spin" : ""} />
              {updates.isFetching ? "Verificando…" : "Verificar"}
            </Button>
          }
        >
          {!checarUpdates && (
            <p className="text-sm text-muted">
              Clique em “Verificar” para comparar os mods instalados com o catálogo.
            </p>
          )}
          {updates.isError && (
            <p className="text-sm text-danger">Falha ao verificar: {String(updates.error)}</p>
          )}
          {checarUpdates && !updates.isFetching && disponiveis.length === 0 && !updates.isError && (
            <p className="text-sm text-muted">
              Tudo em dia — nenhum mod reconhecido pelo catálogo tem versão mais nova.
            </p>
          )}

          <div className="space-y-1.5">
            {disponiveis.map((u) => (
              <div
                key={u.file}
                className="flex flex-wrap items-center gap-3 rounded-md border border-border bg-surface-2 px-3 py-2"
              >
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">{u.file}</div>
                  <div className="text-[11px] text-muted">
                    v{u.current_version} → <b className="text-accent">v{u.latest_version}</b>
                    {u.released_at &&
                      ` · publicada em ${new Date(u.released_at).toLocaleDateString("pt-BR")}`}
                  </div>
                </div>
                {podeInstalar && (
                  <Button
                    variant="primary"
                    disabled={instalar.isPending}
                    onClick={async () => {
                      const confirmado = await dialog.confirm({
                        title: `Atualizar para v${u.latest_version}`,
                        message: `${u.latest_file_name} será baixado. O arquivo antigo (${u.file}) continua na pasta — remova-o depois de confirmar que o servidor sobe.`,
                        confirmText: "Baixar nova versão",
                      });
                      if (confirmado)
                        instalar.mutate({ version_id: u.latest_version_id, overwrite: true });
                    }}
                  >
                    <Download size={13} /> Atualizar
                  </Button>
                )}
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  );
}
