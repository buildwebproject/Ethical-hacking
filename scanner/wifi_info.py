"""Read local Wi-Fi/LAN connection details from the operating system."""

from __future__ import annotations

import ipaddress
import socket
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class ConnectionDetails:
    interface: str = "Unknown"
    ssid: str = "Unknown"
    connection_type: str = "Unknown"
    local_ip: str = "Unknown"
    subnet: str = "Unknown"
    gateway: str = "Unknown"
    mac_address: str = "Unknown"
    status: str = "Connected"

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def run_command(command: list[str]) -> str:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip()


def detect_default_interface() -> str:
    output = run_command(["ip", "route", "show", "default"])
    for line in output.splitlines():
        parts = line.split()
        if "dev" in parts:
            index = parts.index("dev")
            if index + 1 < len(parts):
                return parts[index + 1]
    return "Unknown"


def detect_gateway() -> str:
    output = run_command(["ip", "route", "show", "default"])
    for line in output.splitlines():
        parts = line.split()
        if "via" in parts:
            index = parts.index("via")
            if index + 1 < len(parts):
                return parts[index + 1]
    return "Unknown"


def detect_ip_and_subnet(interface: str) -> tuple[str, str]:
    if interface == "Unknown":
        return "Unknown", "Unknown"

    output = run_command(["ip", "-o", "-4", "addr", "show", "dev", interface])
    for line in output.splitlines():
        parts = line.split()
        if "inet" in parts:
            value = parts[parts.index("inet") + 1]
            try:
                interface_addr = ipaddress.ip_interface(value)
                return str(interface_addr.ip), str(interface_addr.network)
            except ValueError:
                return value.split("/")[0], value
    return "Unknown", "Unknown"


def detect_mac(interface: str) -> str:
    if interface == "Unknown":
        return "Unknown"
    address_path = Path("/sys/class/net") / interface / "address"
    try:
        mac = address_path.read_text(encoding="utf-8").strip()
    except OSError:
        return "Unknown"
    return mac.upper() if mac else "Unknown"


def detect_ssid(interface: str) -> str:
    if interface == "Unknown":
        return "Unknown"

    output = run_command(["iwgetid", interface, "-r"])
    if output:
        return output

    output = run_command(["nmcli", "-t", "-f", "active,ssid,device", "dev", "wifi"])
    for line in output.splitlines():
        parts = line.split(":")
        if len(parts) >= 3 and parts[0] == "yes" and parts[-1] == interface:
            return parts[1] or "Hidden SSID"

    return "Unknown"


def detect_connection_type(interface: str, ssid: str) -> str:
    if interface == "Unknown":
        return "Unknown"
    if ssid != "Unknown" or interface.startswith(("wl", "wlan", "wifi")):
        return "Wi-Fi"
    if interface.startswith(("en", "eth")):
        return "Ethernet"
    return "LAN"


def get_connection_details() -> dict[str, str]:
    interface = detect_default_interface()
    ssid = detect_ssid(interface)
    local_ip, subnet = detect_ip_and_subnet(interface)
    details = ConnectionDetails(
        interface=interface,
        ssid=ssid,
        connection_type=detect_connection_type(interface, ssid),
        local_ip=local_ip,
        subnet=subnet,
        gateway=detect_gateway(),
        mac_address=detect_mac(interface),
        status="Connected" if interface != "Unknown" else "Unknown",
    )

    if details.local_ip == "Unknown":
        try:
            hostname = socket.gethostname()
            details.local_ip = socket.gethostbyname(hostname)
        except OSError:
            pass

    return details.to_dict()
