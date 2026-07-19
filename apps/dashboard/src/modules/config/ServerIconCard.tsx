import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Image as ImageIcon, Trash2, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { useDialog } from "../../components/Dialog";
import { Button, Panel } from "../../components/ui";
import type { Instance } from "../../lib/api";
import { api, can, getAccessToken } from "../../lib/api";
import { useAuth } from "../auth/AuthGate";

const LADO = 64;

/**
 * Reduz qualquer imagem ao PNG 64x64 que o Minecraft exige.
 *
 * Feito no navegador de propósito: ele já decodifica e reescala imagem, então
 * o servidor não precisa carregar uma biblioteca de processamento gráfico só
 * para isto. Corta no centro para não distorcer imagem retangular.
 */
async function paraIcone(arquivo: File): Promise<Blob> {
  const bitmap = await createImageBitmap(arquivo);
  const canvas = document.createElement("canvas");
  canvas.width = LADO;
  canvas.height = LADO;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("o navegador não permitiu processar a imagem");

  const lado = Math.min(bitmap.width, bitmap.height);
  const sx = (bitmap.width - lado) / 2;
  const sy = (bitmap.height - lado) / 2;
  ctx.drawImage(bitmap, sx, sy, lado, lado, 0, 0, LADO, LADO);
  bitmap.close();

  const blob = await new Promise<Blob | null>((r) => canvas.toBlob(r, "image/png"));
  if (!blob) throw new Error("falha ao gerar o PNG");
  return blob;
}

export function ServerIconCard({ instance }: { instance: Instance }) {
  const qc = useQueryClient();
  const dialog = useDialog();
  const { user } = useAuth();
  const podeEditar = can(user, "config.write");
  const entrada = useRef<HTMLInputElement>(null);
  const [erro, setErro] = useState("");
  // Muda a cada gravação para o navegador não servir o ícone antigo do cache.
  const [versao, setVersao] = useState(0);

  const existe = useQuery({
    queryKey: ["icone", instance.id, versao],
    queryFn: async () => {
      const res = await fetch(api.iconUrl(instance.id), {
        headers: { Authorization: `Bearer ${getAccessToken()}` },
      });
      if (res.status === 404) return null;
      if (!res.ok) throw new Error(`falha ao carregar (${res.status})`);
      return URL.createObjectURL(await res.blob());
    },
  });

  const enviar = useMutation({
    mutationFn: async (arquivo: File) => api.uploadIcon(instance.id, await paraIcone(arquivo)),
    onSuccess: () => {
      setErro("");
      setVersao((v) => v + 1);
      qc.invalidateQueries({ queryKey: ["icone", instance.id] });
    },
    onError: (e) => setErro(String(e instanceof Error ? e.message : e)),
  });

  const remover = useMutation({
    mutationFn: () => api.deleteIcon(instance.id),
    onSuccess: () => setVersao((v) => v + 1),
    onError: (e) => setErro(String(e instanceof Error ? e.message : e)),
  });

  const url = existe.data;

  return (
    <Panel
      title="Ícone do servidor"
      icon={<ImageIcon size={15} />}
      hint="Aparece na lista de servidores do jogo. Envie qualquer imagem — ela é recortada no centro e reduzida para 64×64 automaticamente."
    >
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-2">
          {url ? (
            <img
              src={url}
              alt="Ícone do servidor"
              className="h-16 w-16 rounded [image-rendering:pixelated]"
            />
          ) : (
            <ImageIcon size={24} className="text-muted" />
          )}
        </div>

        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium">
            {url ? "server-icon.png definido" : "Nenhum ícone definido"}
          </div>
          <p className="mt-0.5 text-xs text-muted">
            {url
              ? "O servidor precisa ser reiniciado para os jogadores verem a troca."
              : "Sem ícone, o jogo mostra o bloco padrão na lista de servidores."}
          </p>
          {erro && <p className="mt-1 text-xs text-danger">{erro}</p>}
        </div>

        {podeEditar && (
          <span className="flex gap-2">
            <input
              ref={entrada}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) enviar.mutate(f);
                e.target.value = "";
              }}
            />
            <Button
              variant="primary"
              disabled={enviar.isPending}
              onClick={() => entrada.current?.click()}
            >
              <Upload size={14} /> {enviar.isPending ? "Enviando…" : url ? "Trocar" : "Enviar"}
            </Button>
            {url && (
              <Button
                variant="danger"
                disabled={remover.isPending}
                onClick={async () => {
                  const ok = await dialog.confirm({
                    title: "Remover ícone",
                    message: "O server-icon.png é apagado e o jogo volta ao ícone padrão.",
                    confirmText: "Remover",
                    tone: "danger",
                  });
                  if (ok) remover.mutate();
                }}
              >
                <Trash2 size={14} />
              </Button>
            )}
          </span>
        )}
      </div>
    </Panel>
  );
}
