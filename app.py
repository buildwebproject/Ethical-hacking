"""Flask dashboard for WiFi Network Device Scanner."""

from __future__ import annotations

import secrets
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import wraps
from pathlib import Path
from typing import Callable, TypeVar

from flask import Flask, Response, flash, jsonify, redirect, render_template, request, send_from_directory, session, stream_with_context, url_for

from scanner.auth import authenticate, has_users
from scanner.config import SCAN_MAX_DEVICE_WORKERS, WIFI_SCANNER_SECRET_KEY
from scanner.discovery import DiscoveryError, discover_devices
from scanner.http_projects import SAFE_PROJECT_WORDS, find_project_folders, iter_nested_project_folder_probes, iter_project_folder_probes
from scanner.log_store import read_error_logs, write_error_log
from scanner.network import NetworkError, get_local_network, validate_private_subnet
from scanner.port_scanner import parse_ports, scan_device_ports
from scanner.report import DEFAULT_REPORT_DIR, device_to_dict, export_reports, load_latest_json_report
from scanner.vendor_lookup import lookup_vendor
from scanner.wifi_info import get_connection_details


F = TypeVar("F", bound=Callable[..., object])
MAX_DEVICE_PORT_SCAN_WORKERS = SCAN_MAX_DEVICE_WORKERS


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = WIFI_SCANNER_SECRET_KEY or secrets.token_hex(32)

    def api_response(data: dict[str, object] | None = None, status: int = 200) -> object:
        return jsonify({"ok": status < 400, **(data or {})}), status

    def api_error(message: str, status: int = 400, code: str = "api_error") -> object:
        return api_response({"code": code, "message": message}, status)

    def wants_api_response() -> bool:
        return request.path.startswith("/api/")

    @app.before_request
    def require_login_for_dashboard() -> None | object:
        public_endpoints = {"login", "mobile_app", "static", "client_error", "favicon", "api_health", "api_login"}
        if request.endpoint in public_endpoints:
            return None
        if session.get("username"):
            return None
        if wants_api_response():
            return api_error("Authentication required.", 401, "auth_required")
        return redirect(url_for("login"))

    def login_required(view: F) -> F:
        @wraps(view)
        def wrapped(*args: object, **kwargs: object) -> object:
            if not session.get("username"):
                return redirect(url_for("login"))
            return view(*args, **kwargs)

        return wrapped  # type: ignore[return-value]

    def api_login_required(view: F) -> F:
        @wraps(view)
        def wrapped(*args: object, **kwargs: object) -> object:
            if not session.get("username"):
                return api_error("Authentication required.", 401, "auth_required")
            return view(*args, **kwargs)

        return wrapped  # type: ignore[return-value]

    def request_payload() -> dict[str, object]:
        if request.is_json:
            payload = request.get_json(silent=True) or {}
            return payload if isinstance(payload, dict) else {}
        return dict(request.form.items())

    def load_report_devices_or_empty() -> list[object]:
        try:
            return load_dashboard_devices()
        except (FileNotFoundError, ValueError):
            return []

    def serialize_devices(devices: list[object]) -> list[dict[str, object]]:
        return [device_to_dict(device) for device in devices]

    def dashboard_summary(devices: list[object]) -> dict[str, object]:
        return {
            "device_count": len(devices),
            "online_count": sum(1 for device in devices if getattr(device, "status", "") == "Online"),
            "open_port_count": sum(len(getattr(device, "open_ports", [])) for device in devices),
            "has_report": bool(devices),
        }

    def load_dashboard_devices() -> list[object]:
        report_path = Path(DEFAULT_REPORT_DIR) / "network_scan.json"
        if not report_path.exists():
            return []
        return load_latest_json_report(report_path)

    def render_dashboard(current_subnet: str = "", project_results: dict[str, object] | None = None) -> object:
        devices = []
        try:
            devices = load_dashboard_devices()
        except ValueError:
            flash("Saved report could not be loaded.", "error")
        return render_template(
            "dashboard.html",
            devices=devices,
            current_subnet=current_subnet,
            error_logs=read_error_logs(),
            connection_details=get_connection_details(),
            project_results=project_results,
        )

    def enrich_device_ports(device: object, ports: list[int]) -> object:
        device.vendor = lookup_vendor(device.mac)
        device.open_ports = scan_device_ports(device.ip, ports)
        return device

    def scan_ports_for_devices(devices: list[object], ports: list[int]) -> None:
        worker_count = max(1, min(MAX_DEVICE_PORT_SCAN_WORKERS, len(devices)))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [executor.submit(enrich_device_ports, device, ports) for device in devices]
            for future in as_completed(futures):
                future.result()

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc: Exception) -> object:
        write_error_log(
            "server",
            str(exc),
            route=request.path,
            method=request.method,
            exc=exc,
        )
        if wants_api_response():
            return api_error(f"Server error: {type(exc).__name__}: {exc}", 500, "server_error")
        flash(f"Server error: {type(exc).__name__}: {exc}", "error")
        if session.get("username"):
            return render_dashboard(), 500
        return render_template("login.html", has_users=False), 500

    @app.post("/client-error")
    def client_error() -> object:
        payload = request.get_json(silent=True) or {}
        write_error_log(
            "browser",
            str(payload.get("message", "Client-side request failed.")),
            route=str(payload.get("route", "")),
            method=str(payload.get("method", "")),
            details={
                "action": payload.get("action", ""),
                "elapsed_ms": payload.get("elapsed_ms", ""),
                "user_agent": request.headers.get("User-Agent", ""),
            },
        )
        return jsonify({"ok": True})

    @app.get("/favicon.ico")
    def favicon() -> object:
        return send_from_directory(
            app.static_folder or "static",
            "favicon.svg",
            mimetype="image/svg+xml",
        )

    @app.get("/")
    def index() -> object:
        if session.get("username"):
            return redirect(url_for("dashboard"))
        return redirect(url_for("login"))

    

    @app.get("/api/v1/health")
    def api_health() -> object:
        return api_response(
            {
                "service": "NET_SCANNER_API",
                "version": "v1",
                "authenticated": bool(session.get("username")),
            }
        )

    @app.post("/api/v1/auth/login")
    def api_login() -> object:
        payload = request_payload()
        username = str(payload.get("username", ""))
        password = str(payload.get("password", ""))
        try:
            if not authenticate(username, password):
                return api_error("Invalid username or password.", 401, "invalid_credentials")
        except Exception as exc:
            write_error_log("api-auth", str(exc), route=request.path, method=request.method, exc=exc)
            return api_error(f"Authentication backend unavailable: {exc}", 503, "auth_backend_unavailable")

        session.clear()
        session["username"] = username.strip()
        return api_response({"user": {"username": session["username"]}})

    @app.post("/api/v1/auth/logout")
    @api_login_required
    def api_logout() -> object:
        session.clear()
        return api_response({"message": "Logged out."})

    @app.get("/api/v1/auth/me")
    @api_login_required
    def api_me() -> object:
        return api_response({"user": {"username": str(session.get("username", ""))}})

    @app.get("/api/v1/network")
    @api_login_required
    def api_network() -> object:
        return api_response({"connection": get_connection_details()})

    @app.get("/api/v1/ports/common")
    @api_login_required
    def api_common_ports() -> object:
        from scanner.port_scanner import COMMON_PORTS

        return api_response(
            {
                "ports": [
                    {"port": port, "service": service}
                    for port, service in COMMON_PORTS.items()
                ]
            }
        )

    @app.get("/api/v1/devices")
    @api_login_required
    def api_devices() -> object:
        devices = load_report_devices_or_empty()
        return api_response(
            {
                "summary": dashboard_summary(devices),
                "devices": serialize_devices(devices),
            }
        )

    @app.get("/api/v1/summary")
    @api_login_required
    def api_summary() -> object:
        devices = load_report_devices_or_empty()
        return api_response(
            {
                "summary": dashboard_summary(devices),
                "connection": get_connection_details(),
                "errors": read_error_logs(limit=10),
            }
        )

    @app.post("/api/v1/scan")
    @api_login_required
    def api_scan() -> object:
        payload = request_payload()
        subnet_input = str(payload.get("subnet", "")).strip()
        ports_input = str(payload.get("ports", "common")).strip() or "common"
        include_ports = payload.get("include_ports", True)
        include_ports = include_ports if isinstance(include_ports, bool) else str(include_ports).lower() not in {"0", "false", "no"}
        save_report = payload.get("save_report", True)
        save_report = save_report if isinstance(save_report, bool) else str(save_report).lower() not in {"0", "false", "no"}
        started_at = time.perf_counter()

        try:
            if subnet_input:
                subnet = validate_private_subnet(subnet_input)
                local_ip = "manual"
            else:
                local_ip, subnet = get_local_network()
            ports = parse_ports(ports_input) if include_ports else []
            devices = discover_devices(str(subnet))
            if include_ports and devices:
                scan_ports_for_devices(devices, ports)
            if save_report:
                export_reports(devices)
        except (NetworkError, ValueError, DiscoveryError, PermissionError) as exc:
            write_error_log("api-scan", str(exc), route=request.path, method=request.method, exc=exc)
            return api_error(str(exc), 400, "scan_failed")
        except Exception as exc:
            write_error_log("api-scan", str(exc), route=request.path, method=request.method, exc=exc)
            return api_error(f"Scan failed: {exc}", 500, "scan_failed")

        return api_response(
            {
                "message": f"Scan complete for {subnet}.",
                "subnet": str(subnet),
                "local_ip": local_ip,
                "include_ports": include_ports,
                "saved_report": save_report,
                "duration_ms": int((time.perf_counter() - started_at) * 1000),
                "summary": dashboard_summary(devices),
                "devices": serialize_devices(devices),
            }
        )

    @app.post("/api/v1/export")
    @api_login_required
    def api_export() -> object:
        try:
            devices = load_dashboard_devices()
        except FileNotFoundError:
            return api_error("No report found. Run a scan first.", 404, "report_not_found")
        except ValueError as exc:
            return api_error(str(exc), 400, "invalid_report")
        if not devices:
            return api_error("No report data available. Run a scan first.", 404, "report_empty")

        paths = export_reports(devices)
        return api_response(
            {
                "message": "Reports exported.",
                "files": [str(path.relative_to(Path(__file__).resolve().parent)) for path in paths],
            }
        )

    @app.get("/api/v1/errors")
    @api_login_required
    def api_errors() -> object:
        raw_limit = request.args.get("limit", "100")
        try:
            limit = max(1, min(200, int(raw_limit)))
        except ValueError:
            limit = 100
        return api_response({"errors": read_error_logs(limit=limit)})

    @app.get("/api/v1/project-search-words")
    @api_login_required
    def api_project_search_words() -> object:
        return api_response({"words": SAFE_PROJECT_WORDS})

    @app.post("/api/v1/projects/find")
    @api_login_required
    def api_find_projects() -> object:
        payload = request_payload()
        target_ip = str(payload.get("ip", "")).strip()
        try:
            devices = load_dashboard_devices()
            target_device = next((device for device in devices if device.ip == target_ip), None)
            if target_device is None:
                raise ValueError("Target device is not present in the latest scan report.")
            if not any(port.startswith("80/") for port in target_device.open_ports):
                raise ValueError("Port 80 is not open for this device. Run a scan first.")
            return api_response({"results": find_project_folders(target_ip)})
        except Exception as exc:
            write_error_log("api-project-discovery", str(exc), route=request.path, method=request.method, exc=exc)
            return api_error(str(exc), 400, "project_discovery_failed")

    @app.post("/api/v1/projects/tree")
    @api_login_required
    def api_project_tree() -> object:
        payload = request_payload()
        start_url = str(payload.get("url", "")).strip()
        events: list[dict[str, object]] = []
        folders: list[dict[str, object]] = []
        meta: dict[str, object] = {}
        try:
            for event in iter_nested_project_folder_probes(start_url):
                events.append(event)
                if event.get("event") == "meta":
                    meta = event
                if event.get("event") == "folder":
                    folder = event.get("folder")
                    if isinstance(folder, dict):
                        folders.append(folder)
        except Exception as exc:
            write_error_log("api-project-tree", str(exc), route=request.path, method=request.method, exc=exc)
            return api_error(str(exc), 400, "project_tree_failed")

        return api_response({"meta": meta, "folders": folders, "events": events})

    @app.route("/login", methods=["GET", "POST"])
    def login() -> object:
        if session.get("username"):
            return redirect(url_for("dashboard"))

        try:
            user_exists = has_users()
            if request.method == "POST":
                username = request.form.get("username", "")
                password = request.form.get("password", "")
                if authenticate(username, password):
                    session.clear()
                    session["username"] = username.strip()
                    return redirect(url_for("dashboard"))
                flash("Invalid username or password.", "error")
        except Exception as exc:
            write_error_log("database", str(exc), route=request.path, method=request.method, exc=exc)
            flash(f"Database unavailable: {exc}", "error")
            user_exists = False

        return render_template("login.html", has_users=user_exists)

    @app.post("/logout")
    @login_required
    def logout() -> object:
        session.clear()
        return redirect(url_for("login"))

    @app.get("/dashboard")
    @login_required
    def dashboard() -> object:
        return render_dashboard()

    @app.post("/scan")
    @login_required
    def scan() -> object:
        subnet_input = request.form.get("subnet", "").strip()
        ports_input = request.form.get("ports", "common").strip() or "common"

        try:
            if subnet_input:
                subnet = validate_private_subnet(subnet_input)
                local_ip = "manual"
            else:
                local_ip, subnet = get_local_network()
            ports = parse_ports(ports_input)
        except (NetworkError, ValueError) as exc:
            write_error_log("scan", str(exc), route=request.path, method=request.method, exc=exc)
            flash(str(exc), "error")
            return redirect(url_for("dashboard"))

        try:
            devices = discover_devices(str(subnet))
        except PermissionError as exc:
            write_error_log("scan", str(exc), route=request.path, method=request.method, exc=exc)
            flash("ARP scan needs permission. Run Gunicorn with the required network privileges.", "error")
            return redirect(url_for("dashboard"))
        except DiscoveryError as exc:
            write_error_log("scan", str(exc), route=request.path, method=request.method, exc=exc)
            flash(str(exc), "error")
            return redirect(url_for("dashboard"))

        if not devices:
            flash(f"No online devices found on {subnet}.", "warning")
            return render_template(
                "dashboard.html",
                devices=[],
                current_subnet=str(subnet),
                error_logs=read_error_logs(),
                connection_details=get_connection_details(),
                project_results=None,
            )

        scan_ports_for_devices(devices, ports)

        export_reports(devices)
        flash(f"Scan complete for {subnet}. Current IP: {local_ip}", "success")
        return render_template(
            "dashboard.html",
            devices=devices,
            current_subnet=str(subnet),
            error_logs=read_error_logs(),
            connection_details=get_connection_details(),
            project_results=None,
        )

    @app.post("/export")
    @login_required
    def export() -> object:
        try:
            devices = load_dashboard_devices()
        except FileNotFoundError:
            flash("No report found. Run a scan first.", "warning")
            return render_dashboard()
        except ValueError as exc:
            flash(str(exc), "error")
            return render_dashboard()

        if not devices:
            flash("No report data available. Run a scan first.", "warning")
            return render_dashboard()

        export_reports(devices)
        flash("Reports exported to JSON, CSV, and Markdown.", "success")
        return render_template(
            "dashboard.html",
            devices=devices,
            current_subnet="",
            error_logs=read_error_logs(),
            connection_details=get_connection_details(),
            project_results=None,
        )

    @app.post("/find-projects")
    @login_required
    def find_projects() -> object:
        target_ip = request.form.get("ip", "").strip()
        wants_json = request.headers.get("X-Project-Modal") == "1" or request.accept_mimetypes.best == "application/json"
        wants_stream = request.headers.get("X-Project-Stream") == "1"
        try:
            devices = load_dashboard_devices()
            target_device = next((device for device in devices if device.ip == target_ip), None)
            if target_device is None:
                raise ValueError("Target device is not present in the latest scan report.")
            if not any(port.startswith("80/") for port in target_device.open_ports):
                raise ValueError("Port 80 is not open for this device. Run a scan first.")

            if wants_stream:
                def stream_project_events() -> object:
                    try:
                        for event in iter_project_folder_probes(target_ip):
                            yield json.dumps({"ok": True, **event}) + "\n"
                        yield json.dumps({"ok": True, "event": "done"}) + "\n"
                    except Exception as exc:
                        write_error_log("project-discovery", str(exc), route=request.path, method=request.method, exc=exc)
                        yield json.dumps({"ok": False, "event": "error", "message": str(exc)}) + "\n"

                return Response(stream_with_context(stream_project_events()), mimetype="application/x-ndjson")

            project_results = find_project_folders(target_ip)
            if wants_json:
                return jsonify({"ok": True, "results": project_results})
            flash(f"Project folder discovery complete for {target_ip}.", "success")
            return render_template(
                "dashboard.html",
                devices=devices,
                current_subnet="",
                error_logs=read_error_logs(),
                connection_details=get_connection_details(),
                project_results=project_results,
            )
        except Exception as exc:
            write_error_log("project-discovery", str(exc), route=request.path, method=request.method, exc=exc)
            if wants_stream:
                return Response(
                    json.dumps({"ok": False, "event": "error", "message": str(exc)}) + "\n",
                    status=400,
                    mimetype="application/x-ndjson",
                )
            if wants_json:
                return jsonify({"ok": False, "message": str(exc)}), 400
            flash(str(exc), "error")
            return render_dashboard()

    @app.get("/project-search-words")
    @login_required
    def project_search_words() -> object:
        return jsonify({"words": SAFE_PROJECT_WORDS})

    @app.post("/inspect-project-folders")
    @login_required
    def inspect_project_folders() -> object:
        start_url = request.form.get("url", "").strip()

        def stream_folder_events() -> object:
            try:
                for event in iter_nested_project_folder_probes(start_url):
                    yield json.dumps({"ok": True, **event}) + "\n"
                yield json.dumps({"ok": True, "event": "done"}) + "\n"
            except Exception as exc:
                write_error_log("project-tree", str(exc), route=request.path, method=request.method, exc=exc)
                yield json.dumps({"ok": False, "event": "error", "message": str(exc)}) + "\n"

        return Response(stream_with_context(stream_folder_events()), mimetype="application/x-ndjson")

    return app


app = create_app()
