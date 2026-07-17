"""Run the Core in development mode: ``python -m aether_core``."""

import uvicorn

from aether_core.infrastructure.settings import AppSettings


def main() -> None:
    settings = AppSettings()
    uvicorn.run(
        "aether_core.interfaces.http:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        reload=True,
    )


if __name__ == "__main__":
    main()
