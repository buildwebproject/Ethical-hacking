"""Bounded TCP connect port checks for discovered local devices."""

from __future__ import annotations

import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


COMMON_PORTS: dict[int, str] = {
    21: "FTP",
    22: "SSH",
    23: "Telnet",
    25: "SMTP",
    53: "DNS",
    80: "HTTP",
    110: "POP3",
    139: "NetBIOS",
    143: "IMAP",
    443: "HTTPS",
    445: "SMB",
    3306: "MySQL",
    5432: "PostgreSQL",
    6379: "Redis",
    8000: "HTTP Dev",
    8080: "HTTP Alt",
    9000: "Common App",
    27017: "MongoDB",
}


def parse_ports(value: str) -> list[int]:
    if value.strip().lower() == "common":
        return list(COMMON_PORTS)

    ports: list[int] = []
    for raw_port in value.split(","):
        raw_port = raw_port.strip()
        if not raw_port:
            continue
        try:
            port = int(raw_port)
        except ValueError as exc:
            raise ValueError(f"Invalid port '{raw_port}'. Use 'common' or comma-separated numbers.") from exc
        if port < 1 or port > 65535:
            raise ValueError(f"Invalid port '{port}'. Ports must be between 1 and 65535.")
        ports.append(port)

    if not ports:
        raise ValueError("No ports were provided.")

    return sorted(set(ports))


def check_port(ip: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def format_port(port: int) -> str:
    service = COMMON_PORTS.get(port, "Unknown")
    return f"{port}/{service}"


def scan_device_ports(
    ip: str,
    ports: list[int],
    timeout: float = 0.5,
    max_workers: int = 20,
    delay_between_results: float = 0.01,
) -> list[str]:
    """Scan a small allowed list of ports with a strict worker limit."""
    worker_count = max(1, min(max_workers, 20, len(ports)))
    open_ports: list[int] = []

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_to_port = {
            executor.submit(check_port, ip, port, timeout): port
            for port in ports
        }
        for future in as_completed(future_to_port):
            port = future_to_port[future]
            if future.result():
                open_ports.append(port)
            time.sleep(delay_between_results)

    return [format_port(port) for port in sorted(open_ports)]
