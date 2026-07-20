import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  ExternalLink,
  Gamepad2,
  Info,
  MemoryStick,
  Network,
  Plus,
  Server,
} from "lucide-react";
import { Badge, Button, Panel, Spinner } from "../../components/ui";
import type { GameCatalogEntry, RequisitosDeHardware } from "../../lib/api";
import { api } from "../../lib/api";

function Requisitos({ titulo, req }: { titulo: string; req: RequisitosDeHardware | null }) {
  if (!req) return null;
  const linhas = [
    ["Processador", req.cpu],
    ["Memória", req.ram],
    ["Disco", req.disco],
    ["Rede", req.rede],
    ["Sistema", req.observacao],
  ].filter(([, v]) => v);
  if (linhas.length === 0) return null;

  return (
    <div className="min-w-0 flex-1">
      <div className="mb-1.5 text-[11px] font-semibold tracking-wide text-muted uppercase">
        {titulo}
      </div>
      <dl className="space-y-1">
        {linhas.map(([rotulo, valor]) => (
          <div key={rotulo} className="flex gap-2 text-[13px]">
            <dt className="w-24 shrink-0 text-muted">{rotulo}</dt>
            <dd className="min-w-0">{valor}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

/**
 * Página do jogo: tudo que ajuda a decidir antes de criar o servidor.
 *
 * Os números de hospedagem (RAM por jogadores, portas, avisos) vêm do provider
 * — é conhecimento de quem roda o servidor. Descrição, gênero e requisitos do
 * cliente vêm da loja, quando o jogo tem página lá.
 */
export function GameView({
  gameId,
  onVoltar,
  onCriar,
}: {
  gameId: string;
  onVoltar: () => void;
  onCriar: (providerId: string) => void;
}) {
  const query = useQuery({
    queryKey: ["catalog", gameId],
    queryFn: () => api.catalogGame(gameId),
  });

  if (query.isLoading) return <Spinner />;
  if (query.isError || !query.data)
    return <div className="p-6 text-sm text-danger">Erro ao carregar o jogo: {String(query.error)}</div>;

  const jogo: GameCatalogEntry = query.data;
  const temReqServidor = jogo.requisitos_servidor_minimo || jogo.requisitos_servidor_recomendado;
  const temReqCliente = jogo.requisitos_cliente_minimo || jogo.requisitos_cliente_recomendado;

  return (
    <div className="h-full overflow-y-auto">
      {/* Banner com o nome por cima: dá identidade à página sem ocupar meia tela. */}
      <div className="relative h-44 w-full overflow-hidden bg-surface-3">
        {jogo.banner_url ? (
          <img src={jogo.banner_url} alt="" className="h-full w-full object-cover opacity-60" />
        ) : (
          <div className="flex h-full items-center justify-center">
            <Gamepad2 size={48} className="text-muted" />
          </div>
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-bg to-transparent" />
        <div className="absolute right-4 bottom-4 left-4 flex flex-wrap items-end gap-3">
          {jogo.logo_url && (
            <img src={jogo.logo_url} alt="" className="h-9 max-w-[180px] object-contain" />
          )}
          <div className="min-w-0 flex-1">
            <h2 className="text-xl font-bold">{jogo.nome}</h2>
            {jogo.tagline && <p className="text-[13px] text-muted">{jogo.tagline}</p>}
          </div>
          <Button variant="primary" onClick={() => onCriar(jogo.provider_id)}>
            <Plus size={15} /> Criar servidor
          </Button>
        </div>
      </div>

      <div className="mx-auto w-full max-w-4xl space-y-4 p-4">
        <button
          onClick={onVoltar}
          className="flex cursor-pointer items-center gap-1.5 text-xs text-muted hover:text-text"
        >
          <ArrowLeft size={13} /> Voltar ao catálogo
        </button>

        {/* Crédito da imagem: a licença de algumas artes (CC BY) exige atribuição
            onde a imagem aparece — omitir é violar a licença, não descuido de UI. */}
        {jogo.atribuicao_da_imagem && (
          <p className="text-[11px] text-muted">{jogo.atribuicao_da_imagem}</p>
        )}

        {(jogo.descricao || jogo.genero.length > 0) && (
          <Panel title="Sobre" icon={<Info size={15} />}>
            {jogo.descricao && <p className="text-[13px] leading-relaxed">{jogo.descricao}</p>}
            <div className="mt-3 flex flex-wrap gap-4 text-[12px] text-muted">
              {jogo.desenvolvedora && <span>Desenvolvedora: {jogo.desenvolvedora}</span>}
              {jogo.publicadora && <span>Publicadora: {jogo.publicadora}</span>}
              {jogo.plataformas_do_cliente.length > 0 && (
                <span>Cliente: {jogo.plataformas_do_cliente.join(", ")}</span>
              )}
              {jogo.so_do_servidor.length > 0 && (
                <span>Servidor: {jogo.so_do_servidor.join(", ")}</span>
              )}
            </div>
            {jogo.genero.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {jogo.genero.map((g) => (
                  <Badge key={g} tone="neutral">
                    {g}
                  </Badge>
                ))}
              </div>
            )}
          </Panel>
        )}

        {jogo.ram_por_jogadores.length > 0 && (
          <Panel
            title="Memória recomendada"
            icon={<MemoryStick size={15} />}
            hint="Ponto de partida; modpacks e mundos grandes pedem mais."
            bodyClassName="px-0 pb-0"
          >
            <div className="divide-y divide-border border-t border-border">
              {jogo.ram_por_jogadores.map((faixa) => (
                <div key={faixa.ate_jogadores} className="flex items-center gap-4 px-4 py-2.5">
                  <span className="w-32 shrink-0 text-[13px]">
                    até {faixa.ate_jogadores} jogadores
                  </span>
                  <span className="w-24 shrink-0 text-sm font-semibold text-accent">
                    {faixa.ram}
                  </span>
                  <span className="min-w-0 flex-1 text-[12px] text-muted">{faixa.observacao}</span>
                </div>
              ))}
            </div>
          </Panel>
        )}

        {jogo.portas.length > 0 && (
          <Panel
            title="Portas"
            icon={<Network size={15} />}
            hint="Precisam estar liberadas para os jogadores conectarem."
            bodyClassName="px-0 pb-0"
          >
            <div className="divide-y divide-border border-t border-border">
              {jogo.portas.map((porta) => (
                <div
                  key={`${porta.numero}-${porta.protocolo}`}
                  className="flex items-center gap-3 px-4 py-2.5"
                >
                  <code className="w-28 shrink-0 text-[13px]">
                    {porta.numero}/{porta.protocolo}
                  </code>
                  <span className="min-w-0 flex-1 text-[12px] text-muted">{porta.descricao}</span>
                  {!porta.obrigatoria && <Badge tone="neutral">opcional</Badge>}
                </div>
              ))}
            </div>
          </Panel>
        )}

        {temReqServidor && (
          <Panel title="Requisitos do servidor" icon={<Server size={15} />}>
            <div className="flex flex-wrap gap-6">
              <Requisitos titulo="Mínimo" req={jogo.requisitos_servidor_minimo} />
              <Requisitos titulo="Recomendado" req={jogo.requisitos_servidor_recomendado} />
            </div>
          </Panel>
        )}

        {temReqCliente && (
          <Panel
            title="Requisitos do cliente"
            icon={<Gamepad2 size={15} />}
            hint="O que os jogadores precisam para entrar."
          >
            <div className="flex flex-wrap gap-6">
              <Requisitos titulo="Mínimo" req={jogo.requisitos_cliente_minimo} />
              <Requisitos titulo="Recomendado" req={jogo.requisitos_cliente_recomendado} />
            </div>
          </Panel>
        )}

        {jogo.observacoes_de_hospedagem.length > 0 && (
          <Panel title="Antes de hospedar" icon={<Info size={15} />}>
            <ul className="space-y-2">
              {jogo.observacoes_de_hospedagem.map((obs) => (
                <li key={obs} className="flex gap-2 text-[13px] leading-relaxed">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-accent" />
                  <span className="min-w-0">{obs}</span>
                </li>
              ))}
            </ul>
          </Panel>
        )}

        {jogo.links.length > 0 && (
          <Panel title="Links úteis" icon={<ExternalLink size={15} />}>
            <div className="flex flex-wrap gap-3">
              {jogo.links.map((link) => (
                <a
                  key={link.url}
                  href={link.url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="flex items-center gap-1.5 rounded-lg border border-border bg-surface-2 px-3 py-1.5 text-[12px] hover:border-accent/60"
                >
                  {link.titulo} <ExternalLink size={11} />
                </a>
              ))}
            </div>
          </Panel>
        )}

        <div className="flex justify-center pb-4">
          <Button variant="primary" onClick={() => onCriar(jogo.provider_id)}>
            <Plus size={15} /> Criar servidor de {jogo.nome}
          </Button>
        </div>
      </div>
    </div>
  );
}
