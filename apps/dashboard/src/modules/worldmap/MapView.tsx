import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, ExternalLink, Map as MapIcon } from "lucide-react";
import { useState } from "react";
import { useDialog } from "../../components/Dialog";
import { Button, Panel, Spinner } from "../../components/ui";
import type { Instance, MapStatus } from "../../lib/api";
import { api, copyText } from "../../lib/api";

/** Monta a URL do mapa a partir do host que o navegador já usa + a porta que o
 *  Core devolve. O Core não presume o próprio endereço público, então quem sabe
 *  por onde falar com o servidor é o cliente. */
function mapUrl(status: MapStatus): string {
  const { protocol, hostname } = window.location;
  return `${protocol}//${hostname}:${status.port}${status.path ?? "/"}`;
}

export function MapView({ instance }: { instance: Instance }) {
  const qc = useQueryClient();
  const dialog = useDialog();
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");

  const statusQuery = useQuery({
    queryKey: ["map", instance.id],
    queryFn: () => api.mapStatus(instance.id),
  });

  const enable = useMutation({
    mutationFn: () => api.enableMap(instance.id),
    onMutate: () => setError(""),
    onError: (e) => setError(String(e)),
    onSuccess: (s) => qc.setQueryData(["map", instance.id], s),
  });

  const disable = useMutation({
    mutationFn: () => api.disableMap(instance.id),
    onMutate: () => setError(""),
    onError: (e) => setError(String(e)),
    onSuccess: (s) => qc.setQueryData(["map", instance.id], s),
  });

  if (statusQuery.isLoading) return <Spinner />;
  const status = statusQuery.data;
  const busy = enable.isPending || disable.isPending;

  return (
    <div className="h-full overflow-y-auto p-4">
      <Panel
        title="Mapa-múndi"
        icon={<MapIcon size={16} />}
        hint="Um mapa web do teu mundo, renderizado por um container à parte (BlueMap) que lê o save sem pesar no jogo."
        className="max-w-2xl"
      >
        {status?.enabled ? (
          <div className="flex flex-col gap-4">
            <p className="text-sm text-muted">
              O mapa está <span className="font-semibold text-accent">no ar</span>. O primeiro
              render de um mundo grande leva um tempo — os tiles perto do spawn aparecem primeiro
              e o resto vai preenchendo sozinho.
            </p>

            <div className="flex flex-wrap items-center gap-2">
              <code className="rounded-md border border-border bg-surface-2 px-3 py-1.5 text-sm">
                {status.port ? mapUrl(status) : "—"}
              </code>
              {status.port && (
                <>
                  <Button
                    variant="ghost"
                    onClick={async () => {
                      if (await copyText(mapUrl(status))) {
                        setCopied(true);
                        setTimeout(() => setCopied(false), 1500);
                      }
                    }}
                  >
                    {copied ? <Check size={14} /> : <Copy size={14} />}
                    {copied ? "Copiado" : "Copiar"}
                  </Button>
                  <a href={mapUrl(status)} target="_blank" rel="noreferrer">
                    <Button variant="primary">
                      <ExternalLink size={14} /> Abrir mapa
                    </Button>
                  </a>
                </>
              )}
            </div>

            <div className="border-t border-border pt-3">
              <Button
                variant="danger"
                disabled={busy}
                onClick={async () => {
                  const ok = await dialog.confirm({
                    title: "Desativar o mapa",
                    message:
                      "O container do mapa é derrubado. Os tiles já renderizados ficam salvos — reativar depois retoma de onde parou.",
                    confirmText: "Desativar",
                    tone: "danger",
                  });
                  if (ok) disable.mutate();
                }}
              >
                {disable.isPending ? "Desativando…" : "Desativar mapa"}
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <p className="text-sm text-muted">
              Ao ativar, o Aether sobe um container do BlueMap ao lado do servidor. Ele lê o mundo
              em <span className="font-medium text-text">só-leitura</span> e renderiza com um teto
              de CPU/RAM próprio — o render <span className="font-medium text-text">nunca</span>{" "}
              disputa recursos com o jogo. É opt-in e pode desligar quando quiser.
            </p>
            <div>
              <Button variant="primary" disabled={busy} onClick={() => enable.mutate()}>
                <MapIcon size={14} /> {enable.isPending ? "Ativando…" : "Ativar mapa"}
              </Button>
            </div>
          </div>
        )}

        {error && <p className="mt-3 text-xs text-danger">{error}</p>}
      </Panel>
    </div>
  );
}
