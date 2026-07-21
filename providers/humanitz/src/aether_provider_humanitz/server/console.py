"""Codec do console de HumanitZ (log da Unreal Engine).

O parsing do formato da UE é comum e mora no SDK; aqui fica só o marcador de
"servidor pronto".
"""

from aether_sdk.console_ue import UnrealConsoleCodec

# Linha real do log ao terminar de subir; refinada contra o console real.
READY = r"Server.*started|LogNet: .*listen|is now open for connections|BeginPlay"


def HumanitZConsoleCodec() -> UnrealConsoleCodec:
    return UnrealConsoleCodec(ready_pattern=READY)
