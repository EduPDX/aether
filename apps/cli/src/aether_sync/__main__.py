"""CLI: ``aether-sync <servidor> <profile-id> --dir <pasta>``."""

import argparse
import asyncio
import sys
from pathlib import Path

from aether_sync.client import sync
from aether_sync.protocol import ManifestError


def main() -> None:
    # Consoles Windows legados usam cp1252; nunca deixe um acento derrubar o sync.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")

    parser = argparse.ArgumentParser(
        prog="aether-sync",
        description="Sincroniza uma pasta local com um perfil publicado por um servidor Aether.",
    )
    parser.add_argument("server", help="URL do Aether Core (ex.: http://192.168.1.10:8600)")
    parser.add_argument("profile_id", help="Id do perfil de sincronização publicado")
    parser.add_argument(
        "--dir", required=True, type=Path, help="Pasta de destino (ex.: .minecraft)"
    )
    parser.add_argument("--optional", action="store_true", help="Inclui arquivos opcionais")
    parser.add_argument("--check", action="store_true", help="Só mostra o plano, não altera nada")
    args = parser.parse_args()

    args.dir.mkdir(parents=True, exist_ok=True)
    try:
        plan = asyncio.run(
            sync(
                args.server,
                args.profile_id,
                args.dir,
                include_optional=args.optional,
                check_only=args.check,
            )
        )
    except ManifestError as exc:
        print(f"ERRO de segurança: {exc}", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:  # noqa: BLE001 — CLI de usuário final
        print(f"ERRO: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.check and not plan.is_synced:
        sys.exit(3)


if __name__ == "__main__":
    main()
