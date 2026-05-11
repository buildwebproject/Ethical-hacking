"""Safe, bounded HTTP folder discovery for local devices with port 80 open."""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


SAFE_PROJECT_WORDS = [
    "project",
    "projects",
    "app",
    "apps",
    "web",
    "site",
    "public",
    "static",
    "assets",
    "docs",
    "api",
    "dashboard",
    "portal",
    "dev",
    "test",
]
ALLOWED_STATUS_CODES = {200, 301, 302, 303, 307, 308, 401, 403}


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for key, value in attrs:
            if key.lower() == "href" and value:
                self.links.add(value)


def is_private_ip(ip: str) -> bool:
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return address.version == 4 and address.is_private


def request_url(url: str, timeout: float = 0.7) -> tuple[int, str]:
    request = Request(url, headers={"User-Agent": "WiFiNetworkScanner/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(80_000).decode("utf-8", errors="ignore")
            return int(response.status), body
    except HTTPError as exc:
        return int(exc.code), ""
    except (URLError, TimeoutError, OSError):
        return 0, ""


def extract_first_level_folders(base_url: str, html: str) -> list[str]:
    parser = LinkParser()
    parser.feed(html)
    folders: set[str] = set()

    for link in parser.links:
        absolute = urljoin(base_url, link)
        parsed = urlparse(absolute)
        if parsed.netloc != urlparse(base_url).netloc:
            continue
        path = parsed.path.strip("/")
        if not path:
            continue
        first = path.split("/", 1)[0]
        if re.fullmatch(r"[A-Za-z0-9._-]{1,64}", first):
            folders.add(first)

    return sorted(folders)[:25]


def validate_local_project_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "http":
        raise ValueError("Project folder inspection supports local HTTP URLs only.")
    host = parsed.hostname or ""
    if not is_private_ip(host):
        raise ValueError("Project folder inspection is allowed only for private local IP addresses.")
    if parsed.port not in (None, 80):
        raise ValueError("Project folder inspection is limited to port 80.")
    normalized_path = "/" + parsed.path.strip("/")
    if normalized_path != "/":
        normalized_path += "/"
    return f"http://{host}{normalized_path}"


def extract_child_folders(base_url: str, html: str) -> list[str]:
    parser = LinkParser()
    parser.feed(html)
    folders: set[str] = set()
    base_parsed = urlparse(base_url)
    base_path = base_parsed.path.rstrip("/") + "/"

    for link in parser.links:
        if link.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(base_url, link)
        parsed = urlparse(absolute)
        if parsed.netloc != base_parsed.netloc:
            continue
        if not parsed.path.startswith(base_path):
            continue
        rest = parsed.path[len(base_path):].strip("/")
        if not rest:
            continue
        first = rest.split("/", 1)[0]
        if re.fullmatch(r"[A-Za-z0-9._-]{1,64}", first):
            folders.add(first)

    return sorted(folders)[:25]


def check_folder(base_url: str, folder: str) -> dict[str, str] | None:
    url = f"{base_url.rstrip('/')}/{folder}/"
    status, _ = request_url(url)
    if status not in ALLOWED_STATUS_CODES:
        return None
    return {
        "name": folder,
        "url": url,
        "status": str(status),
    }


def probe_folder(base_url: str, folder: str) -> dict[str, object]:
    url = f"{base_url.rstrip('/')}/{folder}/"
    status, _ = request_url(url)
    found = status in ALLOWED_STATUS_CODES
    return {
        "name": folder,
        "url": url,
        "status": str(status) if status else "No response",
        "found": found,
    }


def iter_project_folder_probes(ip: str, max_workers: int = 4) -> Iterator[dict[str, object]]:
    if not is_private_ip(ip):
        raise ValueError("Project discovery is allowed only for private local IP addresses.")

    base_url = f"http://{ip}/"
    status, html = request_url(base_url)
    linked_folders = extract_first_level_folders(base_url, html) if html else []
    candidates = sorted(set(SAFE_PROJECT_WORDS + linked_folders))

    yield {
        "event": "meta",
        "target_ip": ip,
        "base_url": base_url,
        "root_status": str(status) if status else "No response",
        "main_project": urlparse(base_url).netloc,
        "search_words": candidates,
    }

    worker_count = max(1, min(max_workers, len(candidates)))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [executor.submit(probe_folder, base_url, folder) for folder in candidates]
        for future in as_completed(futures):
            yield {"event": "probe", "probe": future.result()}


def find_project_folders(ip: str, max_workers: int = 4) -> dict[str, object]:
    folders: list[dict[str, str]] = []
    checked: list[dict[str, object]] = []
    meta: dict[str, object] = {}

    for event in iter_project_folder_probes(ip, max_workers=max_workers):
        if event["event"] == "meta":
            meta = event
            continue
        result = event["probe"]
        checked.append(result)
        if result["found"]:
            folders.append(
                {
                    "name": str(result["name"]),
                    "url": str(result["url"]),
                    "status": str(result["status"]),
                }
            )

    return {
        "target_ip": str(meta["target_ip"]),
        "base_url": str(meta["base_url"]),
        "root_status": str(meta["root_status"]),
        "main_project": str(meta["main_project"]),
        "folders": sorted(folders, key=lambda row: row["name"]),
        "checked": sorted(checked, key=lambda row: str(row["name"])),
        "search_words": meta["search_words"],
    }


def iter_nested_project_folder_probes(
    start_url: str,
    max_depth: int = 3,
    max_nodes: int = 120,
    max_children_per_folder: int = 30,
) -> Iterator[dict[str, object]]:
    base_url = validate_local_project_url(start_url)
    root_status, root_html = request_url(base_url)
    root_children = extract_child_folders(base_url, root_html) if root_html else []

    yield {
        "event": "meta",
        "base_url": base_url,
        "root_status": str(root_status) if root_status else "No response",
        "max_depth": max_depth,
        "max_nodes": max_nodes,
    }

    queue: list[tuple[str, str, int]] = [
        (folder, f"{base_url.rstrip('/')}/{folder}/", 1)
        for folder in sorted(set(root_children + SAFE_PROJECT_WORDS))[:max_children_per_folder]
    ]
    seen = {base_url}
    emitted = 0

    while queue and emitted < max_nodes:
        name, url, depth = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        status, html = request_url(url)
        found = status in ALLOWED_STATUS_CODES
        children = extract_child_folders(url, html) if found and html and depth < max_depth else []
        child_rows = [
            {
                "name": child,
                "url": f"{url.rstrip('/')}/{child}/",
                "depth": depth + 1,
            }
            for child in children[:max_children_per_folder]
        ]

        emitted += 1
        yield {
            "event": "folder",
            "folder": {
                "name": name,
                "url": url,
                "status": str(status) if status else "No response",
                "found": found,
                "depth": depth,
                "children": child_rows,
            },
        }

        if found and depth < max_depth:
            for child in child_rows:
                if child["url"] not in seen:
                    queue.append((str(child["name"]), str(child["url"]), int(child["depth"])))
