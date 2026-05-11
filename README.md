# WiFi Network Device Scanner

A beginner-friendly Python tool for discovering devices on your own Wi-Fi/LAN network and checking a small list of commonly used TCP ports.

## Legal Usage Warning

Use this tool only on networks you own or have explicit permission to assess. It is designed to scan private local network ranges only. It does not perform login attempts, password guessing, brute force, exploitation, packet injection, or attacks.

## What It Does

- Detects your current local IPv4 address.
- Derives the local private subnet, such as `192.168.1.0/24`.
- Discovers online devices using ARP requests.
- Shows IP address, MAC address, vendor when known, hostname when available, and online status.
- Checks only common TCP ports with timeout and concurrency limits.
- Saves reports as JSON, CSV, and Markdown.
- Provides a Gunicorn-ready web dashboard protected by a command-created login.

## Installation

```bash
cd wifi-network-scanner
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## PostgreSQL Setup

Create a PostgreSQL database and user:

```bash
sudo -u postgres psql
```

```sql
CREATE DATABASE wifi_network_scanner;
CREATE USER wifi_scanner WITH PASSWORD 'wifi_scanner_password';
GRANT ALL PRIVILEGES ON DATABASE wifi_network_scanner TO wifi_scanner;
\q
```

Configure `.env`:

```bash
DATABASE_URL=postgresql://wifi_scanner:wifi_scanner_password@127.0.0.1:5432/wifi_network_scanner
WIFI_SCANNER_SECRET_KEY=change-this-long-random-secret
APP_HOST=127.0.0.1
APP_PORT=8000
GUNICORN_TIMEOUT=180
SCAN_MAX_DEVICE_WORKERS=8
SCAN_MAX_PORT_WORKERS=20
DISCOVERY_PING_WORKERS=64
SOCKET_TIMEOUT_SECONDS=0.5
```

Create the required tables:

```bash
python main.py init-db
```

## Create Dashboard Login

The web dashboard has no public registration page. Create the login from the terminal only:

```bash
python main.py create-user admin
```

Passwords are stored as secure hashes in PostgreSQL, not as plain text.

Set a stable Flask session secret before running Gunicorn:

```bash
export WIFI_SCANNER_SECRET_KEY="change-this-long-random-secret"
```

## Run Web Dashboard With Gunicorn

```bash
gunicorn --bind 127.0.0.1:8000 --timeout 180 wsgi:app
```

Open:

```text
http://127.0.0.1:8000
```

Only the login page is available before authentication. The dashboard and scan actions require login.

## Linux Setup Notes

ARP scanning often requires elevated privileges on Linux:

```bash
sudo python main.py scan
```

For the web dashboard, Gunicorn may also need permission for ARP scanning:

```bash
sudo env WIFI_SCANNER_SECRET_KEY="$WIFI_SCANNER_SECRET_KEY" .venv/bin/gunicorn --bind 127.0.0.1:8000 --timeout 180 wsgi:app
```

If you use a virtual environment with `sudo`, pass the virtual environment Python path:

```bash
sudo .venv/bin/python main.py scan
```

## Usage

Automatically detect your local IP and `/24` subnet:

```bash
python main.py scan
```

Scan a specific private local subnet:

```bash
python main.py scan --subnet 192.168.1.0/24
```

Scan common safe ports:

```bash
python main.py scan --ports common
```

Scan selected ports:

```bash
python main.py scan --ports 22,80,443,8080
```

Re-export the latest JSON report:

```bash
python main.py export
```

Create a web dashboard user:

```bash
python main.py create-user admin
```

Initialize PostgreSQL tables:

```bash
python main.py init-db
```

## Common Ports Checked

| Port | Service |
| --- | --- |
| 21 | FTP |
| 22 | SSH |
| 23 | Telnet |
| 25 | SMTP |
| 53 | DNS |
| 80 | HTTP |
| 110 | POP3 |
| 139 | NetBIOS |
| 143 | IMAP |
| 443 | HTTPS |
| 445 | SMB |
| 3306 | MySQL |
| 5432 | PostgreSQL |
| 6379 | Redis |
| 8000 | HTTP Dev |
| 8080 | HTTP Alt |
| 9000 | Common App |
| 27017 | MongoDB |

## Sample Output

```text
Current IP: 192.168.1.25
Subnet: 192.168.1.0/24

                  WiFi/LAN Network Devices
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
┃ IP           ┃ MAC               ┃ Vendor       ┃ Hostname     ┃ Open Ports       ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩
│ 192.168.1.1  │ AA:BB:CC:DD:EE:FF │ TP-Link      │ router.local │ 53/DNS, 80/HTTP  │
│ 192.168.1.10 │ 11:22:33:44:55:66 │ Unknown      │ laptop.local │ 22/SSH, 443/HTTPS│
└──────────────┴───────────────────┴──────────────┴──────────────┴──────────────────┘
```

Reports are saved to:

- `reports/network_scan.json`
- `reports/network_scan.csv`
- `reports/network_scan.md`

## Troubleshooting

**Permission error**

Run with elevated privileges:

```bash
sudo python main.py scan
```

**Invalid subnet error**

Use CIDR format and a private local range:

```bash
python main.py scan --subnet 192.168.1.0/24
```

**Network unavailable error**

Confirm that the computer is connected to Wi-Fi or LAN and has a private IPv4 address.

**No devices found**

Some devices block ARP replies or are on a different VLAN/guest network. Confirm you are connected to the correct network.

## Safety Boundaries

- Public IP ranges are refused.
- Broad ranges larger than `/24` are refused.
- Only ARP discovery and TCP connect checks are used.
- No credential testing or exploitation code is included.
