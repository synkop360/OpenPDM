"""Database infrastructure for the OpenPDM Platform Core."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from openpdm.infrastructure.settings import Settings

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Shared declarative base for Platform Core models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


metadata = Base.metadata

_ENGINE_CACHE: dict[str, Engine] = {}
_SESSION_FACTORY_CACHE: dict[str, sessionmaker[Session]] = {}


def _engine_options(database_url: str) -> dict[str, Any]:
    if database_url.startswith("sqlite"):
        options: dict[str, Any] = {"connect_args": {"check_same_thread": False}}
        if ":memory:" in database_url:
            options["poolclass"] = StaticPool
        return options
    return {"pool_pre_ping": True}


def get_engine(settings: Settings | None = None) -> Engine:
    """Return a shared engine for the configured database URL."""
    active_settings = settings or Settings()
    database_url = active_settings.database_url
    engine = _ENGINE_CACHE.get(database_url)
    if engine is None:
        engine = create_engine(database_url, future=True, **_engine_options(database_url))
        _ENGINE_CACHE[database_url] = engine
    return engine


def get_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    """Return a shared session factory."""
    active_settings = settings or Settings()
    database_url = active_settings.database_url
    factory = _SESSION_FACTORY_CACHE.get(database_url)
    if factory is None:
        factory = sessionmaker(
            bind=get_engine(active_settings),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            future=True,
        )
        _SESSION_FACTORY_CACHE[database_url] = factory
    return factory


def initialize_database(settings: Settings | None = None) -> None:
    """Create the current schema for local development and tests."""
    from openpdm.platform_core.modules.models import Base as PlatformBase

    PlatformBase.metadata.create_all(get_engine(settings))


def dispose_engines() -> None:
    """Dispose cached engines. Useful for tests."""
    for engine in _ENGINE_CACHE.values():
        engine.dispose()
    _ENGINE_CACHE.clear()
    _SESSION_FACTORY_CACHE.clear()


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI dependency for a database session."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope(settings: Settings | None = None) -> Generator[Session, None, None]:
    """Context manager that commits or rolls back a session."""
    session = get_session_factory(settings)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
