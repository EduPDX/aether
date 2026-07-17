"""Application settings (environment variables with the ``AETHER_`` prefix)."""

from pathlib import Path

import platformdirs
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_data_dir() -> Path:
    return Path(platformdirs.user_data_dir("Aether", appauthor=False))


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AETHER_")

    data_dir: Path = Field(default_factory=_default_data_dir)
    host: str = "127.0.0.1"
    port: int = 8600

    @property
    def db_path(self) -> Path:
        return self.data_dir / "aether.db"

    @property
    def db_url(self) -> str:
        return f"sqlite+aiosqlite:///{self.db_path.as_posix()}"

    @property
    def icons_dir(self) -> Path:
        return self.data_dir / "icons"

    @property
    def trash_dir(self) -> Path:
        return self.data_dir / "trash"

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.icons_dir, self.trash_dir):
            d.mkdir(parents=True, exist_ok=True)
