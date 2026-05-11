"""Safe ARP discovery for local private networks."""

from __future__ import annotations

import ipaddress
import socket
import subprocess
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed

from scanner.config import DISCOVERY_PING_WORKERS


class DiscoveryError(RuntimeError):
    """Raised when ARP discovery fails."""


@dataclass
class Device:
    ip: str
    mac: str
    hostname: str = "Unknown"
    vendor: str = "Unknown"
    status: str = "Online"
    open_ports: list[str] = field(default_factory=list)


def resolve_hostname(ip: str) -> str:
    try:
        hostname, _, _ = socket.gethostbyaddr(ip)
        return hostname
    except (socket.herror, socket.gaierror, OSError):
        return "Unknown"


def sort_devices(devices: list[Device]) -> list[Device]:
    return sorted(devices, key=lambda device: tuple(int(part) for part in device.ip.split(".")))


def build_devices_from_arp_rows(rows: list[tuple[str, str]]) -> list[Device]:
    devices: list[Device] = []
    seen_ips: set[str] = set()

    for ip, mac in rows:
        if ip in seen_ips or mac == "00:00:00:00:00:00":
            continue
        seen_ips.add(ip)
        devices.append(Device(ip=ip, mac=mac.upper(), hostname=resolve_hostname(ip)))

    return sort_devices(devices)


def ping_host(ip: str, timeout: int = 1) -> None:
    """Touch a host so the OS can populate its ARP cache."""
    try:
        subprocess.run(
            ["ping", "-n", "-c", "1", "-W", str(timeout), ip],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return


def read_linux_arp_cache(subnet: str) -> list[tuple[str, str]]:
    network = ipaddress.ip_network(subnet, strict=False)
    arp_path = "/proc/net/arp"
    rows: list[tuple[str, str]] = []

    try:
        with open(arp_path, "r", encoding="utf-8") as file:
            next(file, None)
            for line in file:
                columns = line.split()
                if len(columns) < 4:
                    continue
                ip = columns[0]
                mac = columns[3]
                try:
                    if ipaddress.ip_address(ip) in network:
                        rows.append((ip, mac))
                except ValueError:
                    continue
    except FileNotFoundError:
        return []
    except OSError as exc:
        raise DiscoveryError(f"Could not read ARP cache: {exc}") from exc

    return rows


def discover_devices_without_root(subnet: str, timeout: float = 1.0, max_workers: int = DISCOVERY_PING_WORKERS) -> list[Device]:
    """Fallback discovery using ping plus the OS ARP cache.

    This is less complete than raw ARP, but it lets the web dashboard run under
    a normal Gunicorn user on common Linux systems.
    """
    network = ipaddress.ip_network(subnet, strict=False)
    hosts = [str(host) for host in network.hosts()]
    worker_count = max(1, min(max_workers, DISCOVERY_PING_WORKERS, len(hosts)))

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [executor.submit(ping_host, host, int(max(1, timeout))) for host in hosts]
        for future in as_completed(futures):
            future.result()

    return build_devices_from_arp_rows(read_linux_arp_cache(subnet))


def discover_devices(subnet: str, timeout: float = 2.0) -> list[Device]:
    """Discover online devices with ARP requests inside one local subnet."""
    try:
        from scapy.all import ARP, Ether, srp
    except PermissionError:
        return discover_devices_without_root(subnet)
    except Exception as exc:
        message = str(exc).lower()
        if "permission" in message or "operation not permitted" in message:
            return discover_devices_without_root(subnet)
        raise DiscoveryError(f"Scapy could not be loaded: {exc}") from exc

    packet = Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=subnet)

    try:
        answered, _ = srp(packet, timeout=timeout, verbose=False)
    except PermissionError:
        return discover_devices_without_root(subnet)
    except OSError as exc:
        message = str(exc).lower()
        if "permission" in message or "operation not permitted" in message:
            return discover_devices_without_root(subnet)
        raise DiscoveryError("Network unavailable or ARP scan could not be completed.") from exc
    except Exception as exc:
        message = str(exc).lower()
        if "permission" in message or "operation not permitted" in message:
            return discover_devices_without_root(subnet)
        raise DiscoveryError(str(exc)) from exc

    rows = [(received.psrc, received.hwsrc) for _, received in answered]
    return build_devices_from_arp_rows(rows)
