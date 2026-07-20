import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Network, Plus, RotateCw, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Button, Input, Panel, Select, Spinner } from "../../components/ui";
import type { Instance, InstancePort } from "../../lib/api";
import { api } from "../../lib/api";

/**
 * Portas publicadas pelo container.
 *
 * A porta **interna** é do jogo e aparece travada: mudá-la só produz um
 * servidor que sobe e não responde. A porta do **host** é sempre do dono do
 * servidor, e mapeamentos extras existem porque nenhum provider consegue prever
 * a porta que o mod que o usuário instalou vai querer.
 */
export function PortsView({ instance }: { instance: Instance }) {
  const qc = useQueryClient();
  const [linhas, setLinhas] = useState<InstancePort[]>([]);
  const [erro, setErro] = useState("");
  const [salvo, setSalvo] = useState(false);

  const portas = useQuery({
    queryKey: ["ports", instance.id],
    queryFn: () => api.instancePorts(instance.id),
  });

  // O servidor é a fonte da verdade: ele mescla o que o provider pede com o
  // que já foi ajustado, e essa mescla não deve ser refeita aqui.
  useEffect(() => {
    if (portas.data) setLinhas(portas.data.ports);
  }, [portas.data]);

  const salvar = useMutation({
    mutationFn: () =>
      api.saveInstancePorts(
        instance.id,
        linhas.map(({ container_port, protocol, host_port, description }) => ({
          container_port,
          protocol,
          host_port,
          description,
        })),
      ),
    onMutate: () => {
      setErro("");
      setSalvo(false);
    },
    onSuccess: (dados) => {
      setLinhas(dados.ports);
      setSalvo(true);
      qc.invalidateQueries({ queryKey: ["ports", instance.id] });
    },
    onError: (e) => setErro(String(e instanceof Error ? e.message : e)),
  });

  if (portas.isLoading) return <Spinner />;
  if (portas.isError)
    return <div className="p-6 text-sm text-muted">Não foi possível ler as portas.</div>;

  const trocar = (i: number, campo: keyof InstancePort, valor: string) =>
    setLinhas((atual) =>
      atual.map((linha, idx) =>
        idx === i
          ? {
              ...linha,
              [campo]:
                campo === "host_port" || campo === "container_port" ? Number(valor) || 0 : valor,
            }
          : linha,
      ),
    );

  return (
    <div className="mx-auto w-full max-w-3xl space-y-4 overflow-y-auto p-4">
      <Panel
        title="Portas do container"
        icon={<Network size={15} />}
        hint="A porta do host é a que os jogadores usam para conectar."
      >
        <div className="space-y-2">
          {linhas.map((linha, i) => (
            <div
              key={`${linha.container_port}-${linha.protocol}-${i}`}
              className="flex flex-wrap items-end gap-2 rounded-lg border border-border bg-surface-2 p-2"
            >
              <div>
                <label className="mb-1 block text-[11px] text-muted">Porta no host</label>
                <Input
                  className="w-28"
                  type="number"
                  value={String(linha.host_port)}
                  onChange={(e) => trocar(i, "host_port", e.target.value)}
                />
              </div>
              <div>
                <label className="mb-1 block text-[11px] text-muted">No container</label>
                <Input
                  className="w-28"
                  type="number"
                  value={String(linha.container_port)}
                  disabled={linha.from_provider}
                  title={
                    linha.from_provider
                      ? "Definida pelo jogo — mudar aqui só faz o servidor subir sem responder."
                      : undefined
                  }
                  onChange={(e) => trocar(i, "container_port", e.target.value)}
                />
              </div>
              <div>
                <label className="mb-1 block text-[11px] text-muted">Protocolo</label>
                <Select
                  className="w-24"
                  value={linha.protocol}
                  disabled={linha.from_provider}
                  onChange={(e) => trocar(i, "protocol", e.target.value)}
                >
                  <option value="tcp">TCP</option>
                  <option value="udp">UDP</option>
                </Select>
              </div>
              <div className="min-w-40 flex-1">
                <label className="mb-1 block text-[11px] text-muted">
                  {linha.from_provider ? "Exigida pelo jogo" : "Para que serve"}
                </label>
                <Input
                  className="w-full"
                  value={linha.description}
                  placeholder={linha.from_provider ? "" : "Ex.: mapa web do mod"}
                  onChange={(e) => trocar(i, "description", e.target.value)}
                />
              </div>
              {/* Porta do provider não some: o jogo depende dela, e removê-la
                  daria um servidor no ar que ninguém consegue acessar. */}
              <Button
                variant="ghost"
                disabled={linha.from_provider}
                title={
                  linha.from_provider ? "O jogo depende desta porta." : "Remover este mapeamento"
                }
                onClick={() => setLinhas((atual) => atual.filter((_, idx) => idx !== i))}
              >
                <Trash2 size={14} />
              </Button>
            </div>
          ))}

          <Button
            onClick={() =>
              setLinhas((atual) => [
                ...atual,
                {
                  container_port: 0,
                  protocol: "tcp",
                  host_port: 0,
                  description: "",
                  from_provider: false,
                },
              ])
            }
          >
            <Plus size={14} /> Adicionar porta
          </Button>
        </div>

        {erro && <p className="mt-3 text-xs text-danger">{erro}</p>}
        <div className="mt-3 flex items-center gap-3">
          <Button variant="primary" disabled={salvar.isPending} onClick={() => salvar.mutate()}>
            Salvar
          </Button>
          {salvo && portas.data?.restart_required && (
            <span className="flex items-center gap-1.5 text-xs text-warn">
              <RotateCw size={13} /> Reinicie o servidor para aplicar — o Docker publica as portas
              na criação do container.
            </span>
          )}
          {salvo && !portas.data?.restart_required && (
            <span className="text-xs text-muted">Salvo. Vale no próximo start.</span>
          )}
        </div>
      </Panel>

      <p className="text-[12px] leading-relaxed text-muted">
        Abrir a porta no painel publica o container na máquina do Aether. Se o servidor fica atrás
        de um roteador ou firewall, a mesma porta ainda precisa ser liberada lá.
      </p>
    </div>
  );
}
