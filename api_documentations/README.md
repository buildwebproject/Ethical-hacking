# NET_SCANNER Mobile API Documentation

Theme/UI guide:

```text
../docs/mobile-theme-report.md
```

Base URL:

```text
http://<server-host>:8000/api/v1
```

The API uses the same Flask session as the web dashboard. Mobile clients should store and resend the session cookie returned by `POST /auth/login`.

All responses use this envelope:

```json
{
  "ok": true
}
```

Errors use:

```json
{
  "ok": false,
  "code": "auth_required",
  "message": "Authentication required."
}
```

## Authentication

### POST `/auth/login`

Login and receive a session cookie.

Request:

```json
{
  "username": "admin",
  "password": "your-password"
}
```

Response:

```json
{
  "ok": true,
  "user": {
    "username": "admin"
  }
}
```

### GET `/auth/me`

Return the currently logged-in user.

### POST `/auth/logout`

Clear the current session.

## System

### GET `/health`

Public health check.

Response:

```json
{
  "ok": true,
  "service": "NET_SCANNER_API",
  "version": "v1",
  "authenticated": false
}
```

### GET `/network`

Return current interface, IP, subnet, gateway, MAC, SSID, and connection type.

### GET `/summary`

Return dashboard summary, connection details, and the latest 10 error logs.

## Devices And Scanning

### GET `/devices`

Return the latest saved scan report.

Response:

```json
{
  "ok": true,
  "summary": {
    "device_count": 4,
    "online_count": 4,
    "open_port_count": 8,
    "has_report": true
  },
  "devices": [
    {
      "ip": "192.168.1.10",
      "mac": "AA:BB:CC:DD:EE:FF",
      "vendor": "Unknown",
      "hostname": "Unknown",
      "status": "Online",
      "open_ports": ["80/HTTP"]
    }
  ]
}
```

### POST `/scan`

Run a safe private LAN scan. For faster mobile refreshes, set `include_ports` to `false`; this discovers devices without TCP port checks.

Request:

```json
{
  "subnet": "192.168.1.0/24",
  "ports": "common",
  "include_ports": true,
  "save_report": true
}
```

Fields:

- `subnet`: optional. If empty, the server auto-detects the local `/24`.
- `ports`: `"common"` or comma-separated ports like `"22,80,443"`.
- `include_ports`: optional boolean. Use `false` for faster discovery-only scans.
- `save_report`: optional boolean. Use `false` for temporary scans that should not overwrite reports.

Response includes `duration_ms`, `summary`, and `devices`.

### GET `/ports/common`

Return the common port set used by scans.

### POST `/export`

Export the latest report to JSON, CSV, and Markdown files on the server.

## Project Discovery

### GET `/project-search-words`

Return the bounded safe folder words used for local HTTP project discovery.

### POST `/projects/find`

Find visible HTTP project folders for a scanned device with port 80 open.

Request:

```json
{
  "ip": "192.168.1.20"
}
```

### POST `/projects/tree`

Inspect nested folders below a local HTTP project URL.

Request:

```json
{
  "url": "http://192.168.1.20/project/"
}
```

Response includes `meta`, `folders`, and raw `events`.

## Logs

### GET `/errors?limit=100`

Return recent server/browser/API error logs. `limit` is clamped between 1 and 200.

## Mobile Integration Notes

- Always call `POST /auth/login` first and preserve the returned cookie.
- Use `POST /scan` with `include_ports: false` for fast pull-to-refresh device discovery.
- Run a full scan with `include_ports: true` before using `/projects/find`, because project discovery requires known port 80 results.
- All scanning remains restricted to private IPv4 local networks and `/24` or smaller subnets.
