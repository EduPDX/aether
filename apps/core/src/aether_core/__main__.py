"""Run the Core in development mode: ``python -m aether_core``."""

import uvicorn


def main() -> None:
    uvicorn.run(
        "aether_core.interfaces.http:create_app",
        factory=True,
        host="127.0.0.1",
        port=8600,
        reload=True,
    )


if __name__ == "__main__":
    main()
