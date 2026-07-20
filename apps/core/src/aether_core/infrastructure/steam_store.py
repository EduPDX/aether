"""Metadados de jogo pela loja pública da Steam.

Usa o `appdetails` da loja, que é aberto e não pede chave de API — a mesma
resposta que a página da Steam consome. Em troca não há contrato de
estabilidade: a fonte pode mudar de formato ou parar de responder, então tudo
aqui degrada para vazio em vez de levantar. Um catálogo sem descrição ainda é
útil; um catálogo que não abre, não.

Os requisitos vêm em HTML (`<strong>Memória:</strong> 8 GB de RAM<br>`), então
o parser desmonta esses pares em campos.
"""

import html
import logging
import re

from aether_sdk import RequisitosDeHardware

log = logging.getLogger(__name__)

URL = "https://store.steampowered.com/api/appdetails"

_TAG = re.compile(r"<[^>]+>")
_ITEM = re.compile(r"<strong>(.*?)</strong>(.*?)(?=<strong>|$)", re.DOTALL)

# Rótulos como a Steam os escreve, em português e inglês.
_CPU = ("processador", "processor")
_RAM = ("memória", "memoria", "memory")
_DISCO = ("armazenamento", "espaço", "storage", "hard drive")
_SO = ("sistema operativo", "sistema operacional", "os", "so")
_REDE = ("rede", "network", "internet")


def _limpar(texto: str) -> str:
    return html.unescape(_TAG.sub(" ", texto or "")).replace("\xa0", " ").strip(" :\t\n")


def _requisitos(bruto: str) -> RequisitosDeHardware | None:
    """Transforma o HTML de requisitos da Steam em campos."""
    if not bruto:
        return None
    campos: dict[str, str] = {}
    for rotulo, valor in _ITEM.findall(bruto):
        chave = _limpar(rotulo).lower()
        texto = _limpar(valor)
        if not texto:
            continue
        if any(k in chave for k in _CPU):
            campos["cpu"] = texto
        elif any(k in chave for k in _RAM):
            campos["ram"] = texto
        elif any(k in chave for k in _DISCO):
            campos["disco"] = texto
        elif any(k in chave for k in _REDE):
            campos["rede"] = texto
        elif any(k == chave for k in _SO):
            campos["observacao"] = texto
    return RequisitosDeHardware(**campos) if campos else None


class SteamStoreSource:
    """Fonte de metadados baseada na loja pública da Steam."""

    id = "steam"

    def __init__(self, http_get, idioma: str = "portuguese") -> None:
        self._get = http_get
        self._idioma = idioma

    def aplica_para(self, entrada) -> bool:
        return entrada.steam_app_id is not None

    async def buscar(self, entrada) -> dict:
        """Devolve só o que a fonte sabe; o chamador decide o que sobrescrever."""
        try:
            resposta = await self._get(
                URL, params={"appids": entrada.steam_app_id, "l": self._idioma}
            )
        except Exception as exc:  # noqa: BLE001 - fonte externa não derruba o catálogo
            log.info("Steam indisponível para %s: %s", entrada.id, exc)
            return {}

        bloco = (resposta or {}).get(str(entrada.steam_app_id)) or {}
        if not bloco.get("success"):
            return {}
        dados = bloco.get("data") or {}

        plataformas = [
            nome.capitalize() for nome, tem in (dados.get("platforms") or {}).items() if tem
        ]
        # Requisitos de Linux quando existem: é o que interessa para hospedar.
        cliente = dados.get("linux_requirements") or dados.get("pc_requirements") or {}
        if isinstance(cliente, list):  # a Steam manda [] quando não há
            cliente = {}

        return {
            "descricao": _limpar(dados.get("short_description", "")),
            "genero": [g["description"] for g in dados.get("genres", []) if g.get("description")],
            "desenvolvedora": ", ".join(dados.get("developers") or []),
            "publicadora": ", ".join(dados.get("publishers") or []),
            "plataformas_do_cliente": plataformas,
            "banner_url": dados.get("header_image", ""),
            "logo_url": dados.get("capsule_image", ""),
            "requisitos_cliente_minimo": _requisitos(cliente.get("minimum", "")),
            "requisitos_cliente_recomendado": _requisitos(cliente.get("recommended", "")),
        }
