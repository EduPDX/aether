import Editor from "@monaco-editor/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  FileCode2,
  RotateCcw,
  Save,
  Wand2,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useDialog } from "../../components/Dialog";
import { Badge, Button, Spinner } from "../../components/ui";
import type { Instance, RawConfigValidation } from "../../lib/api";
import { api } from "../../lib/api";
import { formatarXml } from "../../lib/xml";

/**
 * Edição direta do arquivo de configuração.
 *
 * Existe porque o formulário cobre só o que o painel mapeou: a versão
 * instalada do jogo quase sempre tem mais opções, e quem precisa de uma delas
 * não pode ficar esperando uma versão nova do painel.
 *
 * Como daqui dá para impedir o servidor de subir, o editor valida antes de
 * salvar e o servidor guarda a versão anterior a cada gravação.
 */
export function RawConfigEditor({
  instance,
  schemaId,
}: {
  instance: Instance;
  schemaId: string;
}) {
  const qc = useQueryClient();
  const dialog = useDialog();
  const query = useQuery({
    queryKey: ["config-raw", instance.id, schemaId],
    queryFn: () => api.rawConfig(instance.id, schemaId),
  });

  const [content, setContent] = useState("");
  const [dirty, setDirty] = useState(false);
  const [problema, setProblema] = useState<RawConfigValidation | null>(null);
  const [salvo, setSalvo] = useState(false);
  const [erro, setErro] = useState("");
  type EditorInstance = Parameters<NonNullable<Parameters<typeof Editor>[0]["onMount"]>>[0];
  const editorRef = useRef<EditorInstance | null>(null);

  useEffect(() => {
    if (query.data) {
      setContent(query.data.content);
      setDirty(false);
      setProblema(null);
    }
  }, [query.data]);

  const validar = useMutation({
    mutationFn: () => api.validateRawConfig(instance.id, schemaId, content),
    onSuccess: (r) => setProblema(r.valid ? null : r),
  });

  const salvar = useMutation({
    mutationFn: async () => {
      // Valida antes de mandar salvar: o erro aparece no editor, não como
      // uma mensagem solta depois da tentativa.
      const check = await api.validateRawConfig(instance.id, schemaId, content);
      if (!check.valid) {
        setProblema(check);
        throw new Error(
          `XML inválido: ${check.message} (linha ${check.line}, coluna ${check.column})`,
        );
      }
      return api.writeRawConfig(instance.id, schemaId, content);
    },
    onSuccess: () => {
      setDirty(false);
      setProblema(null);
      setErro("");
      setSalvo(true);
      setTimeout(() => setSalvo(false), 2500);
      qc.invalidateQueries({ queryKey: ["config", instance.id] });
      qc.invalidateQueries({ queryKey: ["config-raw", instance.id, schemaId] });
    },
    onError: (e) => setErro(String(e instanceof Error ? e.message : e)),
  });

  const restaurar = useMutation({
    mutationFn: () => api.restoreRawConfig(instance.id, schemaId),
    onSuccess: (r) => {
      setContent(r.content);
      setDirty(false);
      setProblema(null);
      qc.invalidateQueries({ queryKey: ["config", instance.id] });
    },
    onError: (e) => setErro(String(e instanceof Error ? e.message : e)),
  });

  function baixar() {
    const blob = new Blob([content], { type: "application/xml" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = query.data?.file.split("/").pop() ?? "config.xml";
    a.click();
    URL.revokeObjectURL(a.href);
  }

  function formatar() {
    const resultado = formatarXml(content);
    if (resultado === null) {
      setProblema({ valid: false, message: "XML inválido: não dá para formatar", line: 1, column: 1 });
      return;
    }
    setContent(resultado);
    setDirty(true);
  }

  /** Leva o cursor até o erro — achar linha 87 na mão é trabalho à toa. */
  function irParaOErro() {
    const ed = editorRef.current;
    if (!ed || !problema?.line) return;
    ed.revealLineInCenter(problema.line);
    ed.setPosition({ lineNumber: problema.line, column: problema.column ?? 1 });
    ed.focus();
  }

  if (query.isLoading) return <Spinner />;
  if (query.isError)
    return <div className="p-6 text-sm text-danger">Erro ao ler o arquivo: {String(query.error)}</div>;

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-2">
        <FileCode2 size={15} className="text-muted" />
        <code className="text-xs">{query.data?.file}</code>
        {salvo && <Badge tone="green">salvo ✓</Badge>}
        {dirty && !salvo && <Badge tone="orange">não salvo</Badge>}

        <span className="ml-auto flex flex-wrap items-center gap-2">
          <Button onClick={formatar} title="Indentar o XML">
            <Wand2 size={13} /> Formatar
          </Button>
          <Button onClick={() => validar.mutate()} disabled={validar.isPending}>
            <CheckCircle2 size={13} /> Validar
          </Button>
          <Button onClick={baixar} title="Baixar o arquivo">
            <Download size={13} />
          </Button>
          <Button
            disabled={!query.data?.has_previous || restaurar.isPending}
            title={
              query.data?.has_previous
                ? "Voltar para a versão anterior à última gravação"
                : "Nenhuma versão anterior guardada ainda"
            }
            onClick={async () => {
              const ok = await dialog.confirm({
                title: "Restaurar versão anterior",
                message:
                  "O arquivo volta ao conteúdo de antes da última gravação. O conteúdo atual é guardado, então dá para desfazer de novo.",
                confirmText: "Restaurar",
              });
              if (ok) restaurar.mutate();
            }}
          >
            <RotateCcw size={13} /> Restaurar
          </Button>
          <Button variant="primary" disabled={!dirty || salvar.isPending} onClick={() => salvar.mutate()}>
            <Save size={13} /> Salvar
          </Button>
        </span>
      </div>

      {/* O aviso fica sempre à vista: quem edita aqui pode derrubar o servidor. */}
      <div className="flex items-start gap-2 border-b border-border bg-warn/10 px-4 py-2 text-[12px] text-muted">
        <AlertTriangle size={14} className="mt-0.5 shrink-0 text-warn" />
        <span>
          Modo avançado: você edita o arquivo inteiro, inclusive opções que o painel não conhece.
          Um valor inválido pode impedir o servidor de iniciar. O conteúdo anterior é guardado a
          cada gravação — dá para restaurar.
        </span>
      </div>

      {problema && (
        <button
          className="flex cursor-pointer items-center gap-2 border-b border-danger/40 bg-danger/10 px-4 py-2 text-left text-[12px] text-danger"
          onClick={irParaOErro}
        >
          <AlertTriangle size={14} className="shrink-0" />
          <span>
            {problema.message} — linha {problema.line}, coluna {problema.column}. Clique para ir até lá.
          </span>
        </button>
      )}
      {validar.data?.valid && !problema && (
        <div className="border-b border-border px-4 py-2 text-[12px] text-accent">
          XML válido.
        </div>
      )}
      {erro && <div className="border-b border-border px-4 py-2 text-xs text-danger">{erro}</div>}

      <div className="min-h-0 flex-1">
        <Editor
          height="100%"
          language="xml"
          theme="vs-dark"
          value={content}
          onMount={(editor) => {
            editorRef.current = editor;
          }}
          onChange={(v) => {
            setContent(v ?? "");
            setDirty(true);
            setProblema(null);
          }}
          options={{
            minimap: { enabled: false },
            fontSize: 13,
            tabSize: 2,
            wordWrap: "on",
            scrollBeyondLastLine: false,
          }}
        />
      </div>
    </div>
  );
}
