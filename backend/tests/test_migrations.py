"""Tests for the Alembic migration chain that bootstraps the deployed schema."""

from __future__ import annotations

import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from openpdm.infrastructure.database import dispose_engines

POSTGRES_TEST_URL = os.environ.get("OPENPDM_TEST_POSTGRES_URL", "")


def test_postgresql_migration_chain_upgrades_a_genuinely_empty_database() -> None:
    if not POSTGRES_TEST_URL.startswith("postgresql"):
        if os.environ.get("OPENPDM_REQUIRE_POSTGRES_TRANSFER_TEST") == "1":
            pytest.fail("required PostgreSQL migration test has no PostgreSQL database URL")
        pytest.skip("set OPENPDM_TEST_POSTGRES_URL to an isolated PostgreSQL test database")

    os.environ["OPENPDM_DATABASE_URL"] = POSTGRES_TEST_URL
    dispose_engines()

    # The deployed container only ever runs `alembic upgrade head` against
    # whatever the database already has -- for a fresh contributor checkout
    # that is a genuinely empty database, not one pre-populated by
    # initialize_disposable_database(). Drop everything first so this test
    # exercises that exact bootstrap path.
    engine = create_engine(POSTGRES_TEST_URL)
    with engine.begin() as connection:
        for table_name in inspect(engine).get_table_names():
            connection.exec_driver_sql(f'DROP TABLE IF EXISTS "{table_name}" CASCADE')
    engine.dispose()

    config = Config("alembic.ini")
    command.upgrade(config, "head")

    engine = create_engine(POSTGRES_TEST_URL)
    assert "users" in inspect(engine).get_table_names()
    engine.dispose()

    # The migrated schema must exactly match the current SQLAlchemy models --
    # any drift here means a later migration is missing a column, index or
    # constraint that models.py already declares. Raises on mismatch.
    command.check(config)
