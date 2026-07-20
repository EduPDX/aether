"""Codec de console: níveis do log Unity e detecção de ready."""

from aether_provider_sevendays.server.console import SevenDaysConsoleCodec


def test_linha_de_log_padrao():
    line = SevenDaysConsoleCodec().parse("2026-07-19T21:30:05 55.196 INF Loading world: Navezgane")
    assert line.level == "INFO"
    assert line.message == "Loading world: Navezgane"
    assert not line.ready


def test_ready_no_init_do_gameserver():
    line = SevenDaysConsoleCodec().parse(
        "2026-07-19T21:31:12 122.004 INF GameServer.Init successful"
    )
    assert line.ready


def test_linha_fora_do_padrao_passa_crua():
    """A instalação via SteamCMD imprime linhas próprias antes do jogo subir;
    elas aparecem no console sem nível, nunca são descartadas."""
    raw = " Update state (0x61) downloading, progress: 42.02"
    line = SevenDaysConsoleCodec().parse(raw)
    assert line.message == raw
    assert line.level == ""
