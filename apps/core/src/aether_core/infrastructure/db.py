"""Database models, engine factory and migration runner."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Boolean, Integer, String, Text
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


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    username: Mapped[str] = mapped_column(String(60), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(20))
    email: Mapped[str] = mapped_column(String(200), default="")
    display_name: Mapped[str] = mapped_column(String(100), default="")
    token_epoch: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[str] = mapped_column(String(40))


class SyncProfileRow(Base):
    __tablename__ = "sync_profiles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    instance_id: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(100))
    channel: Mapped[str] = mapped_column(String(20), default="stable")
    rules: Mapped[str] = mapped_column(Text, default="{}")
    manifest: Mapped[str | None] = mapped_column(Text, nullable=True)
    signature: Mapped[str | None] = mapped_column(String(200), nullable=True)
    published_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[str] = mapped_column(String(40))


class BackupRow(Base):
    __tablename__ = "backups"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    instance_id: Mapped[str] = mapped_column(String(32))
    file_name: Mapped[str] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    kind: Mapped[str] = mapped_column(String(20), default="manual")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(String(40))


class BackupPolicyRow(Base):
    __tablename__ = "backup_policies"

    instance_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    schedule: Mapped[str] = mapped_column(String(20), default="off")
    keep: Mapped[int] = mapped_column(Integer, default=7)
    last_run: Mapped[str | None] = mapped_column(String(40), nullable=True)


class ScheduledTaskRow(Base):
    __tablename__ = "scheduled_tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    instance_id: Mapped[str] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(20))
    schedule: Mapped[str] = mapped_column(String(20))
    at_hour: Mapped[int] = mapped_column(Integer, default=4)
    at_minute: Mapped[int] = mapped_column(Integer, default=0)
    weekday: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    command: Mapped[str] = mapped_column(Text, default="")
    warn_minutes: Mapped[int] = mapped_column(Integer, default=0)
    last_run: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[str] = mapped_column(String(40))


class AuditLogRow(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    username: Mapped[str | None] = mapped_column(String(60), nullable=True)
    action: Mapped[str] = mapped_column(String(200))
    ip: Mapped[str | None] = mapped_column(String(60), nullable=True)
    created_at: Mapped[str] = mapped_column(String(40))


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
