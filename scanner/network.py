"""Local network detection and validation."""

from __future__ import annotations

import ipaddress
import socket


class NetworkError(RuntimeError):
    """Raised when the local network cannot be detected or validated."""


def get_local_ip() -> str:
    """Return the preferred local IPv4 address without sending payload data."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            local_ip = sock.getsockname()[0]
    except OSError as exc:
        raise NetworkError("Network unavailable or local IP address could not be detected.") from exc

    if local_ip.startswith("127."):
        raise NetworkError("Only a loopback address was detected. Connect to Wi-Fi/LAN and try again.")

    return local_ip


def validate_private_subnet(subnet: str) -> ipaddress.IPv4Network:
    """Validate that a subnet is IPv4, private, and not too broad for local scanning."""
    try:
        network = ipaddress.ip_network(subnet, strict=False)
    except ValueError as exc:
        raise ValueError(f"Invalid subnet '{subnet}'. Use CIDR format such as 192.168.1.0/24.") from exc

    if network.version != 4:
        raise ValueError("Only IPv4 private local networks are supported.")

    if not network.is_private:
        raise ValueError("Refusing to scan public or external IP ranges. Use a private local subnet only.")

    if network.prefixlen < 24:
        raise ValueError("Refusing to scan broad ranges. Use a /24 or smaller private local subnet.")

    if network.is_loopback or network.is_link_local or network.is_multicast:
        raise ValueError("Refusing to scan loopback, link-local, or multicast ranges.")

    return network


def get_local_network(prefix_length: int = 24) -> tuple[str, ipaddress.IPv4Network]:
    """Detect local IP and derive the local private subnet."""
    local_ip = get_local_ip()
    subnet = validate_private_subnet(f"{local_ip}/{prefix_length}")
    return local_ip, subnet
