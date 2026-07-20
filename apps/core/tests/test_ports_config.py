"""Portas de instância: o que o provider pede, o que o dono ajusta.

A regra que estes casos protegem é a divisão de responsabilidade: a porta
interna é do jogo, a do host é de quem hospeda, e um extra que o usuário criou
não pode sumir quando o provider mudar suas portas padrão.
"""

import pytest
from aether_core.application.ports_config import aplicar_portas, descrever, validar
from aether_core.domain.errors import ValidationFailedError
from aether_sdk import ContainerSpec, PortMapping


def _spec() -> ContainerSpec:
    return ContainerSpec(
        image="jogo",
        ports=[
            PortMapping(container_port=26900, protocol="tcp", host_port=26900),
            PortMapping(container_port=26900, protocol="udp", host_port=26900),
        ],
    )


def test_ajuste_troca_a_porta_do_host_e_preserva_a_do_container():
    dados = {"ports": [{"container_port": 26900, "protocol": "tcp", "host_port": 27100}]}

    portas = aplicar_portas(_spec(), dados).ports

    tcp = next(p for p in portas if p.protocol == "tcp")
    assert (tcp.container_port, tcp.host_port) == (26900, 27100)
    # O UDP não foi tocado: cada protocolo é um mapeamento próprio.
    udp = next(p for p in portas if p.protocol == "udp")
    assert udp.host_port == 26900


def test_porta_extra_do_usuario_e_acrescentada():
    """Mod com mapa web serve numa porta que provider nenhum poderia prever."""
    dados = {
        "ports": [
            {"container_port": 8080, "protocol": "tcp", "host_port": 8080, "description": "mapa"}
        ]
    }

    portas = aplicar_portas(_spec(), dados).ports

    assert len(portas) == 3
    assert any(p.container_port == 8080 for p in portas)


def test_sem_ajuste_o_spec_do_provider_passa_intacto():
    spec = _spec()
    assert aplicar_portas(spec, {}) is spec


def test_descrever_marca_a_origem_de_cada_porta():
    """A interface trava a porta interna do provider e libera as extras — sem
    esta marca não dá para saber qual é qual."""
    dados = {"ports": [{"container_port": 8080, "protocol": "tcp", "host_port": 8080}]}

    linhas = descrever(_spec(), dados)

    origens = {(linha["container_port"], linha["from_provider"]) for linha in linhas}
    assert (26900, True) in origens
    assert (8080, False) in origens


def test_descrever_funciona_sem_servidor_instalado():
    """O spec vem ``None`` antes da instalação; a tela precisa abrir mesmo
    assim, senão não dá para escolher a porta antes de instalar."""
    dados = {"ports": [{"container_port": 8080, "protocol": "tcp", "host_port": 8080}]}

    assert [linha["host_port"] for linha in descrever(None, dados)] == [8080]


def test_porta_repetida_no_host_e_recusada():
    portas = [
        {"container_port": 26900, "protocol": "tcp", "host_port": 27000},
        {"container_port": 8080, "protocol": "tcp", "host_port": 27000},
    ]

    with pytest.raises(ValidationFailedError, match="duas vezes"):
        validar(portas)


def test_porta_de_outra_instancia_e_recusada_com_o_nome_do_dono():
    """O Docker só reclamaria na hora de subir, e aí o servidor fica parado
    sem explicação."""
    portas = [{"container_port": 26900, "protocol": "tcp", "host_port": 26900}]

    with pytest.raises(ValidationFailedError, match="Servidor antigo"):
        validar(portas, ocupadas={(26900, "tcp"): "Servidor antigo"})


def test_porta_fora_de_faixa_e_recusada():
    with pytest.raises(ValidationFailedError, match="inválida"):
        validar([{"container_port": 26900, "protocol": "tcp", "host_port": 70000}])
