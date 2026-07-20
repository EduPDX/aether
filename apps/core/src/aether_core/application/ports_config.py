"""Portas de uma instância em container: o que o provider pede e o que o dono ajusta.

O provider declara as portas que o jogo precisa — ele é quem sabe que o 7 Days
to Die fala em 26900 e que o Steam usa mais duas UDP em seguida. Mas o dono do
servidor é quem sabe do resto: que a 26900 já está ocupada pelo servidor antigo,
ou que o mod de mapa web que ele instalou serve numa porta que provider nenhum
poderia prever.

Por isso a divisão de responsabilidade aqui é estrita:

- a **porta interna** (dentro do container) pertence ao provider e não é
  editável — quem a define é o jogo, e mudá-la só produz um servidor que sobe e
  não responde;
- a **porta do host** é do dono do servidor, sempre;
- **mapeamentos extras** são do dono, e o provider nunca os vê.

O formato guardado em ``provider_data["ports"]`` é uma lista de
``{container_port, protocol, host_port, description}``. Casar pelo par
(porta interna, protocolo) é o que permite o provider mudar as portas padrão
numa versão nova sem embaralhar o que o usuário já tinha ajustado.
"""

from aether_sdk import ContainerSpec, PortMapping

from aether_core.domain.errors import ValidationFailedError

CHAVE = "ports"


def _chave(porta: int, protocolo: str) -> tuple[int, str]:
    return int(porta), (protocolo or "tcp").lower()


def normalizar(bruto) -> list[dict]:
    """Lê o que está no provider_data tolerando lixo antigo ou parcial."""
    saida: list[dict] = []
    for item in bruto or []:
        if not isinstance(item, dict):
            continue
        try:
            interna = int(item["container_port"])
            host = int(item["host_port"])
        except (KeyError, TypeError, ValueError):
            continue
        saida.append(
            {
                "container_port": interna,
                "protocol": (item.get("protocol") or "tcp").lower(),
                "host_port": host,
                "description": str(item.get("description") or ""),
            }
        )
    return saida


def aplicar_portas(spec: ContainerSpec, provider_data: dict) -> ContainerSpec:
    """Devolve o spec com as portas do usuário aplicadas sobre as do provider.

    Ajuste com o mesmo par (porta interna, protocolo) troca a porta do host;
    o que não casa com nada é acrescentado.
    """
    ajustes = {
        _chave(p["container_port"], p["protocol"]): p for p in normalizar(provider_data.get(CHAVE))
    }
    if not ajustes:
        return spec

    portas: list[PortMapping] = []
    for porta in spec.ports:
        ajuste = ajustes.pop(_chave(porta.container_port, porta.protocol), None)
        portas.append(
            porta.model_copy(update={"host_port": ajuste["host_port"]}) if ajuste else porta
        )
    for extra in ajustes.values():
        portas.append(
            PortMapping(
                container_port=extra["container_port"],
                protocol=extra["protocol"],
                host_port=extra["host_port"],
            )
        )
    return spec.model_copy(update={"ports": portas})


def descrever(spec: ContainerSpec | None, provider_data: dict) -> list[dict]:
    """Lista para a tela: cada porta com origem e o valor em vigor.

    ``from_provider`` é o que a interface usa para travar a porta interna e
    impedir que o usuário apague uma porta de que o jogo depende.
    """
    ajustes = {
        _chave(p["container_port"], p["protocol"]): p for p in normalizar(provider_data.get(CHAVE))
    }
    saida: list[dict] = []
    for porta in spec.ports if spec else []:
        chave = _chave(porta.container_port, porta.protocol)
        ajuste = ajustes.pop(chave, None)
        saida.append(
            {
                "container_port": porta.container_port,
                "protocol": porta.protocol,
                "host_port": ajuste["host_port"] if ajuste else porta.host_port,
                "description": (ajuste or {}).get("description", ""),
                "from_provider": True,
            }
        )
    for extra in ajustes.values():
        saida.append({**extra, "from_provider": False})
    return saida


def validar(
    portas: list[dict], *, ocupadas: dict[tuple[int, str], str] | None = None
) -> list[dict]:
    """Valida antes de gravar. Porta repetida ou fora de faixa vira erro agora,
    não um container que se recusa a subir depois."""
    limpo = normalizar(portas)
    vistas: set[tuple[int, str]] = set()
    for p in limpo:
        for numero, rotulo in ((p["container_port"], "do container"), (p["host_port"], "do host")):
            if not 1 <= numero <= 65535:
                raise ValidationFailedError(f"porta {rotulo} inválida: {numero}")
        chave = _chave(p["host_port"], p["protocol"])
        if chave in vistas:
            raise ValidationFailedError(
                f"a porta {p['host_port']}/{p['protocol']} do host aparece duas vezes"
            )
        vistas.add(chave)
        dono = (ocupadas or {}).get(chave)
        if dono:
            raise ValidationFailedError(
                f"a porta {p['host_port']}/{p['protocol']} já está reservada pela "
                f"instância '{dono}'"
            )
    return limpo
