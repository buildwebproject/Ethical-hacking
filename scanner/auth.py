"""Command-created dashboard users stored in PostgreSQL."""

from __future__ import annotations

from dataclasses import dataclass
from getpass import getpass

from psycopg.errors import UniqueViolation
from werkzeug.security import check_password_hash, generate_password_hash

from scanner.db import get_connection, init_db


@dataclass
class User:
    username: str
    password_hash: str


def has_users() -> bool:
    init_db()
    with get_connection() as connection:
        row = connection.execute("SELECT EXISTS (SELECT 1 FROM dashboard_users)").fetchone()
    return bool(row and row["exists"])


def get_user(username: str) -> User | None:
    init_db()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT username, password_hash FROM dashboard_users WHERE username = %s",
            (username.strip(),),
        ).fetchone()

    if row is None:
        return None
    return User(username=str(row["username"]), password_hash=str(row["password_hash"]))


def create_user(username: str, password: str) -> None:
    username = username.strip()
    if not username:
        raise ValueError("Username cannot be empty.")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")

    init_db()
    password_hash = generate_password_hash(password, method="scrypt")
    try:
        with get_connection() as connection:
            connection.execute(
                "INSERT INTO dashboard_users (username, password_hash) VALUES (%s, %s)",
                (username, password_hash),
            )
    except UniqueViolation as exc:
        raise ValueError(f"User '{username}' already exists.") from exc


def authenticate(username: str, password: str) -> bool:
    user = get_user(username)
    if user is None:
        return False
    return check_password_hash(user.password_hash, password)


def prompt_and_create_user(username: str) -> None:
    password = getpass("Password: ")
    confirm = getpass("Confirm password: ")
    if password != confirm:
        raise ValueError("Passwords do not match.")
    create_user(username, password)
