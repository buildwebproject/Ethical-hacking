"""MAC vendor lookup helper.

The scanner works offline with a small built-in OUI map. Expand this dictionary
if you need more vendor coverage for your own inventory.
"""

from __future__ import annotations


VENDOR_PREFIXES = {
    "00:1A:11": "Google",
    "00:1B:63": "Apple",
    "00:1C:B3": "Apple",
    "00:50:56": "VMware",
    "00:0C:29": "VMware",
    "08:00:27": "VirtualBox",
    "18:65:90": "Apple",
    "1C:1B:0D": "Cisco",
    "28:CF:E9": "Apple",
    "3C:5A:B4": "Google",
    "44:65:0D": "Amazon",
    "50:C7:BF": "TP-Link",
    "60:45:CB": "ASUSTek",
    "6C:72:20": "Apple",
    "70:4F:57": "TP-Link",
    "74:DA:38": "Edimax",
    "80:2A:A8": "Ubiquiti",
    "84:16:F9": "TP-Link",
    "A4:83:E7": "Apple",
    "B8:27:EB": "Raspberry Pi",
    "BC:5F:F4": "ASRock",
    "C8:2A:14": "Apple",
    "D8:3A:DD": "Raspberry Pi",
    "DC:A6:32": "Raspberry Pi",
    "E4:5F:01": "Raspberry Pi",
    "F4:F5:D8": "Google",
    "FC:FB:FB": "Cisco",
}


def normalize_mac(mac: str) -> str:
    parts = mac.replace("-", ":").upper().split(":")
    if len(parts) < 3:
        return ""
    return ":".join(part.zfill(2) for part in parts[:3])


def lookup_vendor(mac: str) -> str:
    prefix = normalize_mac(mac)
    return VENDOR_PREFIXES.get(prefix, "Unknown")
