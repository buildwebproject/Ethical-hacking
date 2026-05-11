"""Persistent PostgreSQL error log storage for dashboard and AJAX failures."""

from __future__ import annotations

import json
import traceback
from typing import Any

from scanner.db import get_connection, init_db


MAX_LOG_ROWS = 100


def write_error_log(
    source: str,
    message: str,
    *,
    route: str = "",
    method: str = "",
    details: dict[str, Any] | None = None,
    exc: BaseException | None = None,
) -> None:
    try:
        init_db()
        exception = type(exc).__name__ if exc is not None else None
        traceback_text = traceback.format_exception_only(type(exc), exc)[-1].strip() if exc is not None else None
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO error_logs (source, method, route, message, exception, traceback, details)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    source,
                    method,
                    route,
                    message,
                    exception,
                    traceback_text,
                    json.dumps(details or {}),
                ),
            )
    except Exception:
        # Logging must never break the request being logged.
        return


def read_error_logs(limit: int = MAX_LOG_ROWS) -> list[dict[str, Any]]:
    try:
        init_db()
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT created_at, source, method, route, message, exception, traceback, details
                FROM error_logs
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            ).fetchall()
    except Exception:
        return []

    return [
        {
            "time": row["created_at"].isoformat() if row.get("created_at") else "",
            "source": row.get("source") or "",
            "method": row.get("method") or "",
            "route": row.get("route") or "",
            "message": row.get("message") or "",
            "exception": row.get("exception") or "",
            "traceback": row.get("traceback") or "",
            "details": row.get("details") or {},
        }
        for row in rows
    ]
