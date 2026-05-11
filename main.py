"""Command line interface for WiFi Network Device Scanner."""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from rich.console import Console

from scanner.auth import prompt_and_create_user
from scanner.config import SCAN_MAX_DEVICE_WORKERS, SCAN_MAX_PORT_WORKERS, SOCKET_TIMEOUT_SECONDS
from scanner.db import init_db
from scanner.discovery import DiscoveryError, discover_devices
from scanner.network import NetworkError, get_local_network, validate_private_subnet
from scanner.port_scanner import COMMON_PORTS, parse_ports, scan_device_ports
from scanner.report import (
    DEFAULT_REPORT_DIR,
    export_reports,
    load_latest_json_report,
    render_devices_table,
)
from scanner.vendor_lookup import lookup_vendor


console = Console()
MAX_DEVICE_PORT_SCAN_WORKERS = SCAN_MAX_DEVICE_WORKERS


def enrich_device_ports(device: object, ports: list[int], timeout: float, max_workers: int) -> object:
    device.vendor = lookup_vendor(device.mac)
    device.open_ports = scan_device_ports(
        ip=device.ip,
        ports=ports,
        timeout=timeout,
        max_workers=max_workers,
    )
    return device


def scan_ports_for_devices(devices: list[object], ports: list[int], timeout: float, max_workers: int) -> None:
    worker_count = max(1, min(MAX_DEVICE_PORT_SCAN_WORKERS, len(devices)))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [
            executor.submit(enrich_device_ports, device, ports, timeout, max_workers)
            for device in devices
        ]
        for future in as_completed(futures):
            future.result()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="WiFi Network Device Scanner",
        description="Safely discover devices on your own local private Wi-Fi/LAN network.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="Discover devices and scan common ports.")
    scan_parser.add_argument(
        "--subnet",
        help="Private local subnet to scan, for example 192.168.1.0/24.",
    )
    scan_parser.add_argument(
        "--ports",
        default="common",
        help="Use 'common' or a comma-separated list such as 22,80,443,8080.",
    )
    scan_parser.add_argument(
        "--timeout",
        type=float,
        default=SOCKET_TIMEOUT_SECONDS,
        help=f"Socket timeout in seconds for each port check. Default: {SOCKET_TIMEOUT_SECONDS}",
    )
    scan_parser.add_argument(
        "--max-workers",
        type=int,
        default=SCAN_MAX_PORT_WORKERS,
        help=f"Maximum concurrent port checks. Default: {SCAN_MAX_PORT_WORKERS}",
    )

    subparsers.add_parser("export", help="Re-export the latest JSON report to CSV and Markdown.")
    subparsers.add_parser("init-db", help="Create PostgreSQL tables for users and error logs.")

    user_parser = subparsers.add_parser("create-user", help="Create a dashboard login user.")
    user_parser.add_argument("username", help="Username for dashboard login.")
    return parser


def run_scan(args: argparse.Namespace) -> int:
    try:
        if args.subnet:
            subnet = validate_private_subnet(args.subnet)
            local_ip = "manual"
        else:
            local_ip, subnet = get_local_network()

        ports = parse_ports(args.ports)
    except (NetworkError, ValueError) as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        return 2

    console.print(f"[bold]Current IP:[/bold] {local_ip}")
    console.print(f"[bold]Subnet:[/bold] {subnet}")
    console.print("[yellow]Scanning only this private local subnet. Use only on authorized networks.[/yellow]")

    try:
        devices = discover_devices(str(subnet))
    except PermissionError:
        console.print(
            "[bold red]Permission error:[/bold red] ARP scanning may require elevated privileges. "
            "Try: sudo python main.py scan"
        )
        return 1
    except DiscoveryError as exc:
        console.print(f"[bold red]Discovery error:[/bold red] {exc}")
        return 1

    if not devices:
        console.print("[yellow]No online devices were discovered on this subnet.[/yellow]")
        return 0

    console.print(f"Discovered {len(devices)} online device(s). Checking ports...")

    scan_ports_for_devices(devices, ports, args.timeout, args.max_workers)

    console.print(render_devices_table(devices))
    written = export_reports(devices)
    console.print("[green]Reports saved:[/green]")
    for path in written:
        console.print(f"  {path}")
    return 0


def run_export() -> int:
    json_path = Path(DEFAULT_REPORT_DIR) / "network_scan.json"
    try:
        devices = load_latest_json_report(json_path)
    except FileNotFoundError:
        console.print("[bold red]Error:[/bold red] No JSON report found. Run 'python main.py scan' first.")
        return 1
    except ValueError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        return 1

    written = export_reports(devices)
    console.print("[green]Reports exported:[/green]")
    for path in written:
        console.print(f"  {path}")
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "scan":
        return run_scan(args)
    if args.command == "export":
        return run_export()
    if args.command == "init-db":
        try:
            init_db()
        except Exception as exc:
            console.print(f"[bold red]Database error:[/bold red] {exc}")
            return 1
        console.print("[green]Database tables are ready.[/green]")
        return 0
    if args.command == "create-user":
        try:
            prompt_and_create_user(args.username)
        except ValueError as exc:
            console.print(f"[bold red]Error:[/bold red] {exc}")
            return 1
        except Exception as exc:
            console.print(f"[bold red]Database error:[/bold red] {exc}")
            return 1
        console.print(f"[green]User created:[/green] {args.username}")
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
