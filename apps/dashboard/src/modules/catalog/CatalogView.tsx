import { useQuery } from "@tanstack/react-query";
import { Gamepad2, Server } from "lucide-react";
import { Spinner } from "../../components/ui";
import type { GameCatalogEntry } from "../../lib/api";
import { api } from "../../lib/api";

/**
 * Catálogo: a porta de entrada para criar um servidor.
 *
 * Antes o assistente pedia o jogo num select, sem contexto. Escolher um jogo
 * para hospedar é uma decisão informada — quanta RAM vai precisar, que portas
 * abrir —, e é isso que a página de cada jogo responde.
 */
export function CatalogView({ onAbrir }: { onAbrir: (gameId: string) => void }) {
  const query = useQuery({ queryKey: ["catalog"], queryFn: api.catalog, staleTime: 60_000 });

  if (query.isLoading) return <Spinner />;
  if (query.isError)
    return <div className="p-6 text-sm text-danger">Erro ao carregar o catálogo: {String(query.error)}</div>;

  const jogos = query.data ?? [];

  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="mx-auto w-full max-w-6xl">
        <p className="mb-4 text-sm text-muted">
          Escolha o jogo que este servidor vai rodar. Cada um tem requisitos, portas e
          recomendações próprias.
        </p>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {jogos.map((jogo: GameCatalogEntry) => (
            <button
              key={jogo.id}
              onClick={() => onAbrir(jogo.id)}
              className="group flex cursor-pointer flex-col overflow-hidden rounded-xl border border-border bg-surface-2 text-left transition-colors hover:border-accent/60"
            >
              <span className="flex h-32 items-center justify-center overflow-hidden bg-surface-3">
                {jogo.banner_url ? (
                  <img
                    src={jogo.banner_url}
                    alt=""
                    className="h-full w-full object-cover transition-transform group-hover:scale-105"
                  />
                ) : (
                  <Gamepad2 size={40} className="text-muted" />
                )}
              </span>
              <span className="flex min-w-0 flex-1 flex-col gap-1 p-4">
                <span className="text-sm font-semibold">{jogo.nome}</span>
                {jogo.tagline && (
                  <span className="line-clamp-2 text-[12px] leading-relaxed text-muted">
                    {jogo.tagline}
                  </span>
                )}
                <span className="mt-2 flex items-center gap-1.5 text-[11px] text-muted">
                  <Server size={12} />
                  {jogo.so_do_servidor.join(" · ") || "servidor dedicado"}
                </span>
              </span>
            </button>
          ))}
        </div>

        {jogos.length === 0 && (
          <p className="text-sm text-muted">
            Nenhum jogo no catálogo — nenhum provider instalado descreve o jogo que roda.
          </p>
        )}
      </div>
    </div>
  );
}
