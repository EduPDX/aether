/** Pacotes de ícones do gerenciador de arquivos (preferência visual do usuário). */

export type IconPack =
  | "classico"
  | "neutro"
  | "solido"
  | "contraste"
  | "pastel"
  | "destaque";

export const ICON_PACKS: { id: IconPack; label: string; hint: string }[] = [
  { id: "classico", label: "Clássico", hint: "Contorno colorido por tipo de arquivo" },
  { id: "neutro", label: "Neutro", hint: "Monocromático, sem cor — visual mais sóbrio" },
  { id: "solido", label: "Sólido", hint: "Ícone sobre uma pastilha colorida" },
  { id: "contraste", label: "Contraste", hint: "Pastilha preenchida, ícone vazado" },
  { id: "pastel", label: "Pastel", hint: "Cores suaves, contorno mais fino" },
  { id: "destaque", label: "Destaque", hint: "Tudo na cor de destaque do tema" },
];

const KEY = "aether.iconPack";
const EVENT = "aether:iconpack";

const IDS = new Set<string>(ICON_PACKS.map((p) => p.id));

export function currentIconPack(): IconPack {
  const v = localStorage.getItem(KEY);
  return v && IDS.has(v) ? (v as IconPack) : "classico";
}

export function setIconPack(pack: IconPack): void {
  localStorage.setItem(KEY, pack);
  window.dispatchEvent(new Event(EVENT));
}

/** Assina mudanças do pacote (mesma aba — o evento é disparado por setIconPack). */
export function subscribeIconPack(fn: () => void): () => void {
  window.addEventListener(EVENT, fn);
  return () => window.removeEventListener(EVENT, fn);
}
