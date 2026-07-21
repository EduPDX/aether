"""Codec do console de Satisfactory (log da Unreal Engine).

O parsing do formato da UE é comum e mora no SDK; aqui fica só o marcador de
"servidor pronto". O servidor dedicado anuncia a inicialização do subsistema de
jogo quando termina de subir.
"""

from aether_sdk.console_ue import UnrealConsoleCodec

# Linha real do log ao terminar de subir; refinada contra o console real.
READY = r"Game state.*ready|Server.*is ready|InitGame|LogNet: AddClientConnection"


def SatisfactoryConsoleCodec() -> UnrealConsoleCodec:
    return UnrealConsoleCodec(ready_pattern=READY)
