"""Codec do console de HumanitZ (log da Unreal Engine).

O parsing do formato da UE é comum e mora no SDK; aqui fica só o marcador de
"servidor pronto".
"""

from aether_sdk.console_ue import UnrealConsoleCodec

# Capturada do console real: o servidor registra a sessão EOS (fica visível e
# aceita conexões) logo depois de carregar o mundo.
READY = r"Creating (EOS )?Session with"


def HumanitZConsoleCodec() -> UnrealConsoleCodec:
    return UnrealConsoleCodec(ready_pattern=READY)
