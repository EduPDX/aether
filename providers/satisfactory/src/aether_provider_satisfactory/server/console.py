"""Codec do console de Satisfactory (log da Unreal Engine).

O parsing do formato da UE é comum e mora no SDK; aqui fica só o marcador de
"servidor pronto". O servidor dedicado anuncia a inicialização do subsistema de
jogo quando termina de subir.
"""

from aether_sdk.console_ue import UnrealConsoleCodec

# Capturada do console real: o servidor dedicado anuncia a API escutando na
# porta assim que termina de subir.
READY = r"Server API listening on"


def SatisfactoryConsoleCodec() -> UnrealConsoleCodec:
    return UnrealConsoleCodec(ready_pattern=READY)
