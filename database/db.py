"""SQLite helpers and initialization for ResQMatrix AI."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .seed import seed_demo_data


SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def get_connection(database_path: str | Path) -> sqlite3.Connection:
    """Open a row-producing SQLite connection with foreign keys enabled."""
    connection = sqlite3.connect(str(database_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def connection_scope(database_path: str | Path) -> Iterator[sqlite3.Connection]:
    """Open a connection and commit or roll back one unit of work."""
    connection = get_connection(database_path)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database(database_path: str | Path) -> None:
    """Create the schema and seed a fresh database with demo records."""
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with connection_scope(path) as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        seed_demo_data(connection)


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    """Convert a SQLite row into a JSON-friendly dictionary."""
    return dict(row) if row is not None else None


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    """Convert multiple SQLite rows into dictionaries."""
    return [dict(row) for row in rows]