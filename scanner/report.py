"""Terminal rendering and report export helpers."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from rich.table import Table

from scanner.discovery import Device


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPORT_DIR = PROJECT_ROOT / "reports"


def device_to_dict(device: Device) -> dict[str, object]:
    return {
        "ip": device.ip,
        "mac": device.mac,
        "vendor": device.vendor,
        "hostname": device.hostname,
        "status": device.status,
        "open_ports": device.open_ports,
    }


def render_devices_table(devices: Iterable[Device]) -> Table:
    table = Table(title="WiFi/LAN Network Devices")
    table.add_column("IP", style="cyan", no_wrap=True)
    table.add_column("MAC", style="magenta", no_wrap=True)
    table.add_column("Vendor")
    table.add_column("Hostname")
    table.add_column("Open Ports")

    for device in devices:
        open_ports = ", ".join(device.open_ports) if device.open_ports else "None"
        table.add_row(device.ip, device.mac, device.vendor, device.hostname, open_ports)

    return table


def export_reports(devices: list[Device], report_dir: str | Path = DEFAULT_REPORT_DIR) -> list[Path]:
    output_dir = Path(report_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "network_scan.json"
    csv_path = output_dir / "network_scan.csv"
    md_path = output_dir / "network_scan.md"

    rows = [device_to_dict(device) for device in devices]

    with json_path.open("w", encoding="utf-8") as file:
        json.dump(rows, file, indent=2)

    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["ip", "mac", "vendor", "hostname", "status", "open_ports"])
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "open_ports": ", ".join(row["open_ports"])})

    with md_path.open("w", encoding="utf-8") as file:
        file.write("# Network Scan Report\n\n")
        file.write("| IP | MAC | Vendor | Hostname | Status | Open Ports |\n")
        file.write("| --- | --- | --- | --- | --- | --- |\n")
        for row in rows:
            open_ports = ", ".join(row["open_ports"]) if row["open_ports"] else "None"
            file.write(
                f"| {row['ip']} | {row['mac']} | {row['vendor']} | "
                f"{row['hostname']} | {row['status']} | {open_ports} |\n"
            )

    return [json_path, csv_path, md_path]


def load_latest_json_report(path: Path) -> list[Device]:
    with path.open("r", encoding="utf-8") as file:
        rows = json.load(file)

    if not isinstance(rows, list):
        raise ValueError("Report JSON is invalid.")

    devices: list[Device] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Report JSON contains an invalid device row.")
        devices.append(
            Device(
                ip=str(row.get("ip", "")),
                mac=str(row.get("mac", "")),
                vendor=str(row.get("vendor", "Unknown")),
                hostname=str(row.get("hostname", "Unknown")),
                status=str(row.get("status", "Online")),
                open_ports=list(row.get("open_ports", [])),
            )
        )
    return devices
