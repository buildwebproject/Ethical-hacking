"""Environment configuration for the scanner project."""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

load_dotenv(ENV_PATH)


def get_env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


DATABASE_URL = get_env(
    "DATABASE_URL",
    "postgresql://wifi_scanner:wifi_scanner_password@127.0.0.1:5432/wifi_network_scanner",
)
WIFI_SCANNER_SECRET_KEY = get_env("WIFI_SCANNER_SECRET_KEY", secrets.token_hex(32))
APP_HOST = get_env("APP_HOST", "127.0.0.1")
APP_PORT = get_env("APP_PORT", "8000")
GUNICORN_TIMEOUT = get_env("GUNICORN_TIMEOUT", "180")
SCAN_MAX_DEVICE_WORKERS = int(get_env("SCAN_MAX_DEVICE_WORKERS", "8"))
SCAN_MAX_PORT_WORKERS = int(get_env("SCAN_MAX_PORT_WORKERS", "20"))
DISCOVERY_PING_WORKERS = int(get_env("DISCOVERY_PING_WORKERS", "64"))
SOCKET_TIMEOUT_SECONDS = float(get_env("SOCKET_TIMEOUT_SECONDS", "0.5"))
