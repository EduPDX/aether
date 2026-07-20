import type { ConfigFieldDef } from "../../lib/api";

/**
 * O campo é relevante com os valores atuais do formulário?
 *
 * Semente e tamanho de mapa só existem em mundo gerado; mostrá-los com um
 * mapa pré-gerado selecionado só confunde, porque o jogo os ignora.
 */
export function visivel(field: ConfigFieldDef, values: Record<string, string>): boolean {
  const dependencias = Object.entries(field.depends_on ?? {});
  return dependencias.every(([chave, esperado]) => values[chave] === esperado);
}

/** Valores iniciais de um schema: o que está salvo, caindo para o padrão. */
export function valoresIniciais(
  fields: ConfigFieldDef[],
  salvos: Record<string, string> = {},
): Record<string, string> {
  const out: Record<string, string> = {};
  for (const f of fields) out[f.key] = salvos[f.key] ?? f.default;
  return out;
}
