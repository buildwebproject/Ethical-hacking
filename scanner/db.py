"""PostgreSQL database helpers."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

from scanner.config import DATABASE_URL


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS dashboard_users (
    id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS error_logs (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source TEXT NOT NULL,
    method TEXT,
    route TEXT,
    message TEXT NOT NULL,
    exception TEXT,
    traceback TEXT,
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_error_logs_created_at ON error_logs (created_at DESC);
"""


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        yield connection


def init_db() -> None:
    with get_connection() as connection:
        for statement in SCHEMA_SQL.split(";"):
            statement = statement.strip()
            if statement:
                connection.execute(statement)
