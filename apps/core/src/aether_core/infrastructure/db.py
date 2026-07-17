"""Database models, engine factory and migration runner."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import String, Text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class Base(DeclarativeBase):
    pass


class InstanceRow(Base):
    __tablename__ = "instances"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    provider_id: Mapped[str] = mapped_column(String(64))
    root_dir: Mapped[str] = mapped_column(Text)
    content_dirs: Mapped[str] = mapped_column(Text, default="{}")
    provider_data: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[str] = mapped_column(String(40))


class ContentCacheRow(Base):
    __tablename__ = "content_cache"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    metadata_json: Mapped[str] = mapped_column(Text)
    icon_file: Mapped[str | None] = mapped_column(String(80), nullable=True)
    updated_at: Mapped[str] = mapped_column(String(40))


def run_migrations(db_path: Path) -> None:
    """Bring the SQLite database to the latest schema (runs at startup)."""
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path.as_posix()}")
    command.upgrade(cfg, "head")


def make_engine(db_url: str) -> AsyncEngine:
    return create_async_engine(db_url)


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False)
