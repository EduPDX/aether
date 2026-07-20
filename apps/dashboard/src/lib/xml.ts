/** Formatação de XML no navegador, para o editor avançado. */

/**
 * Indenta o XML preservando o conteúdo.
 *
 * Feito à mão em cima do DOMParser porque o navegador não tem *pretty print*
 * nativo: o XMLSerializer devolve tudo numa linha só. Devolve `null` quando o
 * XML está quebrado — formatar algo que não parseia daria um resultado pior
 * que o original.
 */
export function formatarXml(texto: string, indentacao = "\t"): string | null {
  const doc = new DOMParser().parseFromString(texto, "application/xml");
  if (doc.getElementsByTagName("parsererror").length > 0) return null;

  const declaracao = texto.trimStart().startsWith("<?xml")
    ? texto.slice(0, texto.indexOf("?>") + 2)
    : '<?xml version="1.0"?>';

  const linhas: string[] = [declaracao];

  function percorrer(node: Element, nivel: number) {
    const prefixo = indentacao.repeat(nivel);
    const filhos = [...node.childNodes];
    const elementos = filhos.filter((n): n is Element => n.nodeType === Node.ELEMENT_NODE);
    const texto = filhos
      .filter((n) => n.nodeType === Node.TEXT_NODE)
      .map((n) => n.nodeValue?.trim() ?? "")
      .join("");

    const atributos = [...node.attributes]
      .map((a) => `${a.name}="${a.value}"`)
      .join(" ");
    const abertura = atributos ? `<${node.tagName} ${atributos}` : `<${node.tagName}`;

    if (elementos.length === 0 && !texto) {
      linhas.push(`${prefixo}${abertura}/>`);
      return;
    }
    if (elementos.length === 0) {
      linhas.push(`${prefixo}${abertura}>${texto}</${node.tagName}>`);
      return;
    }

    linhas.push(`${prefixo}${abertura}>`);
    for (const filho of filhos) {
      if (filho.nodeType === Node.ELEMENT_NODE) {
        percorrer(filho as Element, nivel + 1);
      } else if (filho.nodeType === Node.COMMENT_NODE) {
        // Os comentários do serverconfig do 7DTD documentam cada propriedade:
        // perdê-los na formatação tiraria a única referência que o usuário tem.
        linhas.push(`${indentacao.repeat(nivel + 1)}<!--${filho.nodeValue}-->`);
      }
    }
    linhas.push(`${prefixo}</${node.tagName}>`);
  }

  if (doc.documentElement) percorrer(doc.documentElement, 0);
  return linhas.join("\n") + "\n";
}
