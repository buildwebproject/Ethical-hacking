"""Flask dashboard for WiFi Network Device Scanner."""

from __future__ import annotations

import secrets
import json
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
from scanner.report import DEFAULT_REPORT_DIR, export_reports, load_latest_json_report
from scanner.vendor_lookup import lookup_vendor
from scanner.wifi_info import get_connection_details


F = TypeVar("F", bound=Callable[..., object])
MAX_DEVICE_PORT_SCAN_WORKERS = SCAN_MAX_DEVICE_WORKERS


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = WIFI_SCANNER_SECRET_KEY or secrets.token_hex(32)

    @app.before_request
    def require_login_for_dashboard() -> None | object:
        public_endpoints = {"login", "static", "client_error", "favicon"}
        if request.endpoint in public_endpoints:
            return None
        if session.get("username"):
            return None
        return redirect(url_for("login"))

    def login_required(view: F) -> F:
        @wraps(view)
        def wrapped(*args: object, **kwargs: object) -> object:
            if not session.get("username"):
                return redirect(url_for("login"))
            return view(*args, **kwargs)

        return wrapped  # type: ignore[return-value]

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
        except PermissionError:
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
