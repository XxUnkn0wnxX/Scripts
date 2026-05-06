#!/usr/bin/env python3
"""
nord_ovpn_picker.py

Interactive NordVPN OpenVPN config picker that prefers the recommendation API
first, falls back to the V2 dataset when needed, and downloads chosen .ovpn
files into the current directory by default, or a local NordOVPNs folder when
run from the script directory itself.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import logging
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
REPO_VENV_DIR = SCRIPT_DIR / ".venv"
DOCS_PATH = SCRIPT_DIR / "docs" / "nord-ovpn-picker.md"


def is_windows_platform(platform: Optional[str] = None) -> bool:
    active_platform = platform or sys.platform
    return active_platform.startswith("win")


def get_repo_venv_python_candidates(venv_dir: Path, platform: Optional[str] = None) -> list[Path]:
    if is_windows_platform(platform):
        return [
            venv_dir / "Scripts" / "python.exe",
            venv_dir / "Scripts" / "python",
        ]
    return [
        venv_dir / "bin" / "python",
        venv_dir / "bin" / "python3",
    ]


def normalize_platform_path(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def get_cache_dir(home: Optional[Path] = None, platform: Optional[str] = None, environ: Optional[dict[str, str]] = None) -> Path:
    active_home = home or Path.home()
    active_platform = platform or sys.platform
    active_environ = environ or os.environ

    if active_platform == "darwin":
        return active_home / "Library" / "Caches" / APP_NAME
    if active_platform.startswith("win"):
        local_appdata = active_environ.get("LOCALAPPDATA")
        if local_appdata:
            return Path(local_appdata) / APP_NAME
        return active_home / "AppData" / "Local" / APP_NAME

    xdg_cache_home = active_environ.get("XDG_CACHE_HOME")
    if xdg_cache_home:
        return Path(xdg_cache_home) / APP_NAME
    return active_home / ".cache" / APP_NAME


def resolve_repo_venv_python(venv_dir: Path) -> Optional[Path]:
    candidates = get_repo_venv_python_candidates(venv_dir)
    return next((candidate for candidate in candidates if candidate.exists()), None)


def ensure_repo_venv_or_reexec(argv: Optional[Sequence[str]] = None) -> None:
    active_argv = list(argv if argv is not None else sys.argv[1:])
    repo_venv_python = resolve_repo_venv_python(REPO_VENV_DIR)
    if not REPO_VENV_DIR.exists() or repo_venv_python is None:
        docs_hint = DOCS_PATH if DOCS_PATH.exists() else "docs/nord-ovpn-picker.md"
        raise SystemExit(
            "No local .venv was found for nord_ovpn_picker.py.\n"
            f"Create one in {SCRIPT_DIR} and install the repo requirements before running the script.\n"
            f"See {docs_hint} for setup instructions."
        )

    current_prefix = Path(sys.prefix)
    target_prefix = REPO_VENV_DIR
    if normalize_platform_path(current_prefix) != normalize_platform_path(target_prefix) and os.environ.get(
        "NORD_OVPN_PICKER_REEXEC"
    ) != "1":
        os.environ["NORD_OVPN_PICKER_REEXEC"] = "1"
        os.execv(str(repo_venv_python), [str(repo_venv_python), str(SCRIPT_PATH), *active_argv])


ensure_repo_venv_or_reexec()


from prompt_toolkit.completion import Completer
from prompt_toolkit.completion import Completion
from prompt_toolkit.document import Document
from prompt_toolkit.shortcuts.prompt import CompleteStyle
from prompt_toolkit.styles import Style

import questionary
import requests
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

APP_NAME = "nord-ovpn-picker"
DEFAULT_CACHE_TTL = 6 * 60 * 60
DEFAULT_LIMIT = 5
DEFAULT_PING_COUNT = 3
DEFAULT_PING_TOP = 10
DEFAULT_FETCH_LIMIT = 50
DEFAULT_OUTPUT_SUBDIR = "NordOVPNs"
CACHE_DIR = get_cache_dir()

API_V1_RECOMMENDATIONS = "https://api.nordvpn.com/v1/servers/recommendations"
API_V2_SERVERS = "https://api.nordvpn.com/v2/servers"
DOWNLOAD_BASE = "https://downloads.nordcdn.com/configs/files"
HTTP_TIMEOUT = 10

console = Console()
logger = logging.getLogger(APP_NAME)


class CancelledError(KeyboardInterrupt):
    def __init__(self, message: str = "Cancelled.") -> None:
        super().__init__(message)
        self.message = message

PROMPT_STYLE = Style(
    [
        ("qmark", "fg:#ffd75f bold"),
        ("question", "bold"),
        ("answer", "fg:#ffd75f bold"),
        ("completion-menu", "fg:#ffd75f bg:default"),
        ("completion-menu.completion", "fg:#ffd75f bg:default"),
        ("completion-menu.completion.current", "fg:#000000 bg:#ffd75f"),
        ("completion-menu.meta.completion", "fg:#ffd75f bg:default"),
        ("completion-menu.meta.completion.current", "fg:#000000 bg:#ffd75f"),
        ("readline-like-completions", "fg:#ffd75f"),
        ("readline-like-completions.completion", "fg:#ffd75f"),
        ("readline-like-completions.completion.current", "fg:#000000 bg:#ffd75f"),
        ("scrollbar.background", "bg:default"),
        ("scrollbar.button", "bg:#ffd75f"),
    ]
)


class CliError(RuntimeError):
    """Raised for user-visible CLI failures."""


@dataclass(frozen=True)
class Country:
    id: int
    name: str
    code: Optional[str] = None


@dataclass(frozen=True)
class City:
    id: int
    name: str
    country_id: int


@dataclass(frozen=True)
class ProtocolSpec:
    key: str
    label: str
    technology: str
    cdn_dir: str
    file_suffix: str
    advanced: bool = False


@dataclass(frozen=True)
class GroupSpec:
    key: str
    label: str
    identifier: str


@dataclass
class NordServer:
    hostname: str
    name: Optional[str]
    load: Optional[int]
    station: Optional[str]
    country_name: str
    country_code: Optional[str]
    country_id: int
    city_name: Optional[str]
    city_id: Optional[int]
    group_identifiers: list[str]
    technology_identifiers: list[str]
    status: Optional[str] = None


@dataclass
class CandidateScore:
    server: NordServer
    protocol: str
    group: str
    average_ping_ms: Optional[float]
    score: Optional[float]
    recommended: bool = False


@dataclass(frozen=True)
class AutocompleteOption:
    label: str
    value: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class AuthCredentials:
    username: str
    password: str
    source: str


PROTOCOLS: dict[str, ProtocolSpec] = {
    "udp": ProtocolSpec("udp", "UDP", "openvpn_udp", "ovpn_udp", "udp"),
    "tcp": ProtocolSpec("tcp", "TCP", "openvpn_tcp", "ovpn_tcp", "tcp"),
    "xor_udp": ProtocolSpec(
        "xor_udp", "XOR UDP", "openvpn_xor_udp", "ovpn_xor_udp", "udp", advanced=True
    ),
    "xor_tcp": ProtocolSpec(
        "xor_tcp", "XOR TCP", "openvpn_xor_tcp", "ovpn_xor_tcp", "tcp", advanced=True
    ),
}

GROUPS: dict[str, GroupSpec] = {
    "standard": GroupSpec("standard", "Standard", "legacy_standard"),
    "p2p": GroupSpec("p2p", "P2P", "legacy_p2p"),
    "obfuscated": GroupSpec("obfuscated", "Obfuscated", "legacy_obfuscated_servers"),
    "double": GroupSpec("double", "Double VPN", "legacy_double_vpn"),
    "onion": GroupSpec("onion", "Onion over VPN", "legacy_onion_over_vpn"),
    "dedicated": GroupSpec("dedicated", "Dedicated IP", "legacy_dedicated_ip"),
}

COUNTRY_SYNONYMS: dict[str, set[str]] = {
    "unitedstates": {"usa", "america", "unitedstatesofamerica"},
    "unitedkingdom": {"uk", "britain", "greatbritain"},
    "unitedarabemirates": {"uae"},
}

DEFAULT_AUTH_CONFIG_NAMES = ("nord_ovpn_auth.yaml", "nord_ovpn_auth.yml")


def configure_logging(verbose: bool) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format="%(message)s")


def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def safe_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_") or "default"


def get_default_output_dir(cwd: Optional[Path] = None, script_dir: Optional[Path] = None) -> Path:
    active_cwd = (cwd or Path.cwd()).resolve()
    active_script_dir = (script_dir or SCRIPT_DIR).resolve()
    if normalize_platform_path(active_cwd) == normalize_platform_path(active_script_dir):
        return active_cwd / DEFAULT_OUTPUT_SUBDIR
    return active_cwd


def resolve_default_auth_config_path() -> Optional[Path]:
    for name in DEFAULT_AUTH_CONFIG_NAMES:
        candidate = SCRIPT_DIR / name
        if candidate.exists():
            return candidate
    return None


def load_auth_config(path: Path) -> AuthCredentials:
    try:
        import yaml
    except ImportError as exc:
        raise CliError("PyYAML is required to read the Nord auth config. Install the repo requirements first.") from exc

    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except OSError as exc:
        raise CliError(f"Could not read auth config {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise CliError(f"Invalid YAML in auth config {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise CliError(f"Auth config {path} must be a YAML mapping with 'user' and 'pass' keys.")

    username = str(payload.get("user", "")).strip()
    password = str(payload.get("pass", "")).strip()
    if not username or not password:
        raise CliError(f"Auth config {path} must define non-empty 'user' and 'pass' values.")
    return AuthCredentials(username=username, password=password, source=str(path))


def resolve_auth_credentials(args: argparse.Namespace) -> Optional[AuthCredentials]:
    username = (args.auth_username or "").strip()
    password = (args.auth_password or "").strip()
    if bool(username) != bool(password):
        raise CliError("--auth-username and --auth-password must be provided together.")
    if username and password:
        return AuthCredentials(username=username, password=password, source="cli")

    auth_config_path = resolve_default_auth_config_path()
    if auth_config_path is None:
        return None
    return load_auth_config(auth_config_path)


def ensure_cache_dir() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def load_json_cache(cache_name: str, ttl_seconds: int, refresh: bool) -> Optional[Any]:
    ensure_cache_dir()
    cache_path = CACHE_DIR / cache_name
    if refresh or not cache_path.exists():
        return None
    if time.time() - cache_path.stat().st_mtime > ttl_seconds:
        return None
    with cache_path.open("r", encoding="utf-8") as handle:
        logger.debug("Using cached payload: %s", cache_path)
        return json.load(handle)


def save_json_cache(cache_name: str, payload: Any) -> None:
    ensure_cache_dir()
    cache_path = CACHE_DIR / cache_name
    with cache_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def sanitize_filename(value: str) -> str:
    text = re.sub(r'[\\/:*?"<>|]+', "-", value)
    text = re.sub(r"\s+", " ", text).strip()
    return text.rstrip(".") or "nordvpn"


def parse_positive_int(value: str, field_name: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise CliError(f"{field_name} must be a positive integer.") from exc
    if number <= 0:
        raise CliError(f"{field_name} must be a positive integer.")
    return number


def argparse_positive_int(value: str) -> int:
    try:
        return parse_positive_int(value, "Value")
    except CliError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def average_score(load: Optional[int], average_ping_ms: Optional[float]) -> Optional[float]:
    if average_ping_ms is None and load is None:
        return None
    ping_component = average_ping_ms if average_ping_ms is not None else 9999.0
    load_component = float(load * 2) if load is not None else 500.0
    return ping_component + load_component


def signal_display_name(signum: int) -> str:
    try:
        return signal.Signals(signum).name
    except ValueError:
        return f"signal {signum}"


def handle_termination_signal(signum: int, _frame: Any) -> None:
    raise CancelledError(f"Cancelled by {signal_display_name(signum)}.")


def signal_handler_targets() -> list[int]:
    targets = [signal.SIGINT, signal.SIGTERM]
    sighup = getattr(signal, "SIGHUP", None)
    if sighup is not None:
        targets.append(sighup)
    return targets


def install_signal_handlers() -> dict[int, Any]:
    previous: dict[int, Any] = {}
    for signum in signal_handler_targets():
        previous[signum] = signal.getsignal(signum)
        signal.signal(signum, handle_termination_signal)
    return previous


def restore_signal_handlers(previous: dict[int, Any]) -> None:
    for signum, handler in previous.items():
        signal.signal(signum, handler)


def build_cdn_url(hostname: str, protocol_key: str) -> str:
    protocol = PROTOCOLS[protocol_key]
    return (
        f"{DOWNLOAD_BASE}/{protocol.cdn_dir}/servers/"
        f"{hostname}.{protocol.file_suffix}.ovpn"
    )


def format_hostname_label(hostname: str) -> str:
    return hostname.split(".", 1)[0]


def format_output_filename(server: NordServer, protocol_key: str, group_key: str) -> str:
    protocol = PROTOCOLS[protocol_key]
    group = GROUPS[group_key]
    country = server.country_name
    if server.country_code:
        country = f"{country} ({server.country_code})"
    city = server.city_name or "Country Wide"
    hostname_label = format_hostname_label(server.hostname)
    name = f"{country} - {city} [{protocol.label}] [{group.label}] - {hostname_label}.ovpn"
    return sanitize_filename(name)


def format_auth_output_filename(config_path: Path) -> str:
    return f"{safe_slug(config_path.stem)}.auth.txt"


def build_auth_file_contents(credentials: AuthCredentials) -> str:
    return f"{credentials.username}\n{credentials.password}\n"


def patch_ovpn_auth_user_pass(text: str, auth_filename: str) -> str:
    directive = f"auth-user-pass {auth_filename}"
    pattern = re.compile(r"(?m)^auth-user-pass(?:\s+\S+)?\s*$")
    if pattern.search(text):
        return pattern.sub(directive, text, count=1)

    suffix = "" if text.endswith("\n") else "\n"
    return f"{text}{suffix}{directive}\n"


def atomic_temp_glob(destination_name: str) -> str:
    return f".{destination_name}.*.tmp"


def cleanup_atomic_temp_files(output_dir: Path, destination_name: str) -> int:
    removed = 0
    for path in output_dir.glob(atomic_temp_glob(destination_name)):
        try:
            path.unlink()
            removed += 1
        except FileNotFoundError:
            continue
    return removed


def write_text_atomic(destination: Path, text: str, encoding: str = "utf-8") -> None:
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=str(destination.parent),
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, destination)
    except BaseException:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass
        raise


def validate_ovpn_payload(text: str) -> bool:
    lowered = text.casefold()
    return "client" in lowered and "remote " in lowered and ("<ca>" in lowered or "\nca " in lowered)


def dedupe_servers(servers: Iterable[NordServer]) -> list[NordServer]:
    seen: dict[str, NordServer] = {}
    for server in servers:
        current = seen.get(server.hostname)
        if current is None:
            seen[server.hostname] = server
            continue
        current_load = current.load if current.load is not None else 9999
        new_load = server.load if server.load is not None else 9999
        if new_load < current_load:
            seen[server.hostname] = server
    return list(seen.values())


class NordApiClient:
    def __init__(self, timeout: int = HTTP_TIMEOUT) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": f"{APP_NAME}/1.0",
                "Accept": "application/json, text/plain, */*",
            }
        )

    def get_json(self, url: str, params: Optional[dict[str, Any]] = None) -> Any:
        logger.debug("HTTP GET %s params=%s", url, params)
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise CliError(f"Request failed for {url}: {exc}") from exc
        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise CliError(f"Unexpected JSON payload from {url}") from exc

    def get_text(self, url: str) -> str:
        logger.debug("HTTP GET %s", url)
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise CliError(f"Request failed for {url}: {exc}") from exc
        return response.text

    def get_recommendations(
        self,
        country_id: int,
        group_identifier: str,
        technology_identifier: str,
        limit: int,
        refresh: bool = False,
    ) -> list[dict[str, Any]]:
        params = {
            "limit": limit,
            "filters[country_id]": country_id,
            "filters[servers_groups][identifier]": group_identifier,
            "filters[servers_technologies][identifier]": technology_identifier,
        }
        if not country_id:
            params.pop("filters[country_id]")
        digest = hashlib.sha1(json.dumps(params, sort_keys=True).encode("utf-8")).hexdigest()[:12]
        cache_name = f"recommendations_{digest}.json"
        cached = load_json_cache(cache_name, DEFAULT_CACHE_TTL, refresh)
        if cached is not None:
            return cached
        payload = self.get_json(API_V1_RECOMMENDATIONS, params=params)
        save_json_cache(cache_name, payload)
        return payload

    def get_v2_dataset(self, refresh: bool = False) -> dict[str, Any]:
        cached = load_json_cache("v2_servers.json", DEFAULT_CACHE_TTL, refresh)
        if cached is not None:
            return cached
        payload = self.get_json(API_V2_SERVERS, params={"limit": 16384})
        save_json_cache("v2_servers.json", payload)
        return payload


def parse_countries(raw_countries: Any) -> tuple[list[Country], dict[int, list[City]]]:
    if isinstance(raw_countries, dict):
        return parse_countries_from_v2(raw_countries)

    countries: list[Country] = []
    city_map: dict[int, list[City]] = {}
    for item in raw_countries:
        country = Country(id=int(item["id"]), name=item["name"], code=item.get("code"))
        countries.append(country)
        city_entries: list[City] = []
        for city in item.get("cities", []) or []:
            city_entries.append(City(id=int(city["id"]), name=city["name"], country_id=country.id))
        city_map[country.id] = sorted(city_entries, key=lambda entry: entry.name.casefold())
    return sorted(countries, key=lambda entry: entry.name.casefold()), city_map


def parse_countries_from_v2(payload: dict[str, Any]) -> tuple[list[Country], dict[int, list[City]]]:
    countries_by_id: dict[int, Country] = {}
    city_map: dict[int, dict[int, City]] = {}

    for location in payload.get("locations", []):
        country_data = location.get("country") or {}
        country_id = country_data.get("id")
        country_name = country_data.get("name")
        if country_id is None or not country_name:
            continue

        parsed_country_id = int(country_id)
        countries_by_id[parsed_country_id] = Country(
            id=parsed_country_id,
            name=country_name,
            code=country_data.get("code"),
        )

        city_data = country_data.get("city") or {}
        city_id = city_data.get("id")
        city_name = city_data.get("name")
        if city_id is None or not city_name:
            continue

        city_map.setdefault(parsed_country_id, {})[int(city_id)] = City(
            id=int(city_id),
            name=city_name,
            country_id=parsed_country_id,
        )

    countries = sorted(countries_by_id.values(), key=lambda entry: entry.name.casefold())
    sorted_city_map = {
        country_id: sorted(cities.values(), key=lambda entry: entry.name.casefold())
        for country_id, cities in city_map.items()
    }
    for country in countries:
        sorted_city_map.setdefault(country.id, [])
    return countries, sorted_city_map


def recommendation_to_server(item: dict[str, Any]) -> NordServer:
    location = ((item.get("locations") or [{}])[0]).get("country") or {}
    city = location.get("city") or {}
    return NordServer(
        hostname=item["hostname"],
        name=item.get("name"),
        load=item.get("load"),
        station=item.get("station"),
        country_name=location.get("name", "Unknown"),
        country_code=location.get("code"),
        country_id=int(location.get("id", 0)),
        city_name=city.get("name"),
        city_id=int(city["id"]) if city.get("id") is not None else None,
        group_identifiers=[group.get("identifier") for group in item.get("groups", []) if group.get("identifier")],
        technology_identifiers=[
            tech.get("identifier") for tech in item.get("technologies", []) if tech.get("identifier")
        ],
        status=item.get("status"),
    )


def normalize_v2_servers(payload: dict[str, Any]) -> list[NordServer]:
    groups_by_id = {int(group["id"]): group for group in payload.get("groups", [])}
    technologies_by_id = {int(tech["id"]): tech for tech in payload.get("technologies", [])}
    locations_by_id = {int(location["id"]): location for location in payload.get("locations", [])}
    normalized: list[NordServer] = []

    for item in payload.get("servers", []):
        location_id = next(iter(item.get("location_ids") or []), None)
        location = locations_by_id.get(int(location_id)) if location_id is not None else None
        country = (location or {}).get("country") or {}
        city = country.get("city") or {}
        group_identifiers = [
            groups_by_id[group_id]["identifier"]
            for group_id in item.get("group_ids", []) or []
            if group_id in groups_by_id and groups_by_id[group_id].get("identifier")
        ]
        technology_identifiers = []
        for tech_entry in item.get("technologies", []) or []:
            tech_id = tech_entry.get("id")
            if tech_id in technologies_by_id:
                identifier = technologies_by_id[tech_id].get("identifier")
                if identifier:
                    technology_identifiers.append(identifier)

        normalized.append(
            NordServer(
                hostname=item["hostname"],
                name=item.get("name"),
                load=item.get("load"),
                station=item.get("station"),
                country_name=country.get("name", "Unknown"),
                country_code=country.get("code"),
                country_id=int(country.get("id", 0)),
                city_name=city.get("name"),
                city_id=int(city["id"]) if city.get("id") is not None else None,
                group_identifiers=group_identifiers,
                technology_identifiers=technology_identifiers,
                status=item.get("status"),
            )
        )

    return normalized


def supported_protocol_keys(payload: dict[str, Any], include_advanced: bool) -> list[str]:
    live_identifiers = {item.get("identifier") for item in payload.get("technologies", [])}
    keys: list[str] = []
    for key, spec in PROTOCOLS.items():
        if spec.technology not in live_identifiers:
            continue
        if spec.advanced and not include_advanced:
            continue
        keys.append(key)
    return keys


def supported_group_keys(payload: dict[str, Any], include_advanced: bool) -> list[str]:
    live_identifiers = {item.get("identifier") for item in payload.get("groups", [])}
    keys: list[str] = []
    for key, spec in GROUPS.items():
        if spec.identifier not in live_identifiers:
            continue
        if key not in {"standard", "p2p"} and not include_advanced:
            continue
        keys.append(key)
    return keys


def matches_country(country: Country, query: str) -> bool:
    normalized = normalize_text(query)
    if not normalized:
        return False
    aliases = {normalize_text(country.name)}
    if country.code:
        aliases.add(normalize_text(country.code))
    compact = re.sub(r"[^a-z0-9]+", "", country.name.casefold())
    aliases.add(compact[:3])
    aliases.update(COUNTRY_SYNONYMS.get(compact, set()))
    return normalized in aliases


def matches_city(city: City, query: str) -> bool:
    normalized = normalize_text(query)
    if not normalized:
        return False
    city_name = normalize_text(city.name)
    return normalized == city_name or normalized in city_name


def resolve_country(query: str, countries: Sequence[Country]) -> list[Country]:
    direct = [country for country in countries if matches_country(country, query)]
    if direct:
        return direct

    normalized = normalize_text(query)
    substring = [country for country in countries if normalized and normalized in normalize_text(country.name)]
    if substring:
        return substring

    names = {country.name: country for country in countries}
    close = difflib.get_close_matches(query.casefold(), [country.name.casefold() for country in countries], n=5, cutoff=0.55)
    if not close:
        return []

    matches: list[Country] = []
    for candidate in close:
        for country in countries:
            if country.name.casefold() == candidate:
                matches.append(country)
                break
    return matches


def resolve_city(query: str, cities: Sequence[City]) -> list[City]:
    direct = [city for city in cities if matches_city(city, query)]
    if direct:
        return direct

    close = difflib.get_close_matches(query.casefold(), [city.name.casefold() for city in cities], n=5, cutoff=0.55)
    matches: list[City] = []
    for candidate in close:
        for city in cities:
            if city.name.casefold() == candidate:
                matches.append(city)
                break
    return matches


class PrefixAutocompleteCompleter(Completer):
    def __init__(self, options: Sequence[AutocompleteOption]) -> None:
        self.options = list(options)

    def get_completions(self, document: Document, complete_event: Any) -> Iterable[Completion]:
        query = document.text_before_cursor
        for option in resolve_autocomplete_matches(query, self.options):
            yield Completion(
                option.label,
                start_position=-len(query),
                display=option.label,
                style="class:answer",
                selected_style="class:selected",
            )


def unique_aliases(*values: Optional[str]) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for value in values:
        if value is None:
            continue
        normalized = normalize_text(value)
        if normalized:
            seen.setdefault(normalized, None)
    return tuple(seen.keys())


def country_prompt_option(country: Country) -> AutocompleteOption:
    compact = re.sub(r"[^a-z0-9]+", "", country.name.casefold())
    return AutocompleteOption(
        label=country.name,
        value=country.code or country.name,
        aliases=unique_aliases(country.name, country.code, compact[:3], *COUNTRY_SYNONYMS.get(compact, set())),
    )


def city_prompt_option(city: City) -> AutocompleteOption:
    return AutocompleteOption(label=city.name, value=city.name, aliases=unique_aliases(city.name))


def protocol_prompt_option(key: str) -> AutocompleteOption:
    protocol = PROTOCOLS[key]
    return AutocompleteOption(
        label=protocol.label,
        value=key,
        aliases=unique_aliases(protocol.label, key),
    )


def group_prompt_option(key: str) -> AutocompleteOption:
    group = GROUPS[key]
    return AutocompleteOption(
        label=group.label,
        value=key,
        aliases=unique_aliases(group.label, key),
    )


def resolve_autocomplete_matches(query: str, options: Sequence[AutocompleteOption]) -> list[AutocompleteOption]:
    normalized = normalize_text(query)
    if not normalized:
        return list(options)

    return [option for option in options if normalized in normalize_text(option.label)]


def resolve_autocomplete_option(
    query: str,
    options: Sequence[AutocompleteOption],
    item_name: str,
) -> AutocompleteOption:
    normalized = normalize_text(query)
    if not normalized:
        raise CliError(f"{item_name} is required.")

    matches = resolve_autocomplete_matches(query, options)
    if not matches:
        raise CliError(f'Could not find a {item_name.casefold()} matching "{query}".')
    if len(matches) == 1:
        return matches[0]

    labels = ", ".join(option.label for option in matches[:10])
    if len(matches) > 10:
        labels = f"{labels}, ..."
    raise CliError(f'{item_name} "{query}" is ambiguous: {labels}')


def ask_autocomplete(
    message: str,
    options: Sequence[AutocompleteOption],
    resolver: Any,
    *,
    default: str = "",
    allow_blank: bool = False,
) -> Optional[str]:
    def validator(value: str) -> Any:
        stripped = value.strip()
        if allow_blank and not stripped:
            return True
        try:
            resolver(stripped)
        except CliError as exc:
            return str(exc)
        return True

    prompt = questionary.autocomplete(
        message,
        choices=[option.label for option in options],
        completer=PrefixAutocompleteCompleter(options),
        complete_style=CompleteStyle.COLUMN,
        match_middle=False,
        validate=validator,
        default=default,
        complete_while_typing=True,
        validate_while_typing=False,
        reserve_space_for_menu=min(max(len(options), 4), 10),
        style=PROMPT_STYLE,
    )
    buffer = prompt.application.current_buffer

    def refresh_completion(current_buffer: Any) -> None:
        if current_buffer.text.strip():
            current_buffer.start_completion(select_first=False)
        else:
            current_buffer.cancel_completion()

    buffer.on_text_changed += refresh_completion
    answer = prompt.ask()
    if answer is None:
        return None
    stripped = answer.strip()
    if allow_blank and not stripped:
        return None
    return stripped


def pick_country(
    query: str,
    countries: Sequence[Country],
    interactive: bool,
) -> Country:
    matches = resolve_country(query, countries)
    if not matches:
        raise CliError(f'Could not find a country matching "{query}".')
    if len(matches) == 1:
        return matches[0]
    if interactive:
        options = [country_prompt_option(country) for country in countries]
        answer = ask_autocomplete("Country", options, lambda text: resolve_autocomplete_option(text, options, "Country"), default=query)
        if answer is None:
            raise CliError("Prompt cancelled.")
        return pick_country(answer, countries, interactive=False)
    names = ", ".join(country.name for country in matches)
    raise CliError(f'Country "{query}" is ambiguous: {names}')


def pick_city(
    query: str,
    cities: Sequence[City],
    interactive: bool,
    country_name: str,
) -> City:
    matches = resolve_city(query, cities)
    if not matches:
        available = ", ".join(city.name for city in cities)
        raise CliError(f'Could not find city "{query}" for {country_name}. Available: {available}')
    if len(matches) == 1:
        return matches[0]
    if interactive:
        options = [city_prompt_option(city) for city in cities]
        answer = ask_autocomplete("City", options, lambda text: resolve_autocomplete_option(text, options, "City"), default=query)
        if answer is None:
            raise CliError("Prompt cancelled.")
        return pick_city(answer, cities, interactive=False, country_name=country_name)
    names = ", ".join(city.name for city in matches)
    raise CliError(f'City "{query}" is ambiguous for {country_name}: {names}')


def filter_servers(
    servers: Sequence[NordServer],
    country_id: int,
    city_id: Optional[int],
    group_identifier: str,
    technology_identifier: str,
) -> list[NordServer]:
    filtered: list[NordServer] = []
    for server in servers:
        if country_id and server.country_id != country_id:
            continue
        if city_id is not None and server.city_id != city_id:
            continue
        if server.status and server.status != "online":
            continue
        if group_identifier not in server.group_identifiers:
            continue
        if technology_identifier not in server.technology_identifiers:
            continue
        filtered.append(server)

    return sorted(filtered, key=lambda item: (item.load is None, item.load if item.load is not None else 9999, item.hostname))


def build_ping_command(hostname: str, count: int, platform: Optional[str] = None) -> list[str]:
    if is_windows_platform(platform):
        return ["ping", "-n", str(count), hostname]
    return ["ping", "-c", str(count), "-q", hostname]


def parse_ping_average(output: str) -> Optional[float]:
    summary_patterns = [
        r"(?:round-trip|rtt)[^=]*=\s*[\d.]+/([\d.]+)/[\d.]+(?:/[\d.]+)?",
        r"=\s*[\d.]+/([\d.]+)/[\d.]+",
        r"Average\s*=\s*([\d.]+)\s*ms",
    ]
    for pattern in summary_patterns:
        match = re.search(pattern, output, flags=re.IGNORECASE)
        if match:
            return float(match.group(1))

    timings = [float(value) for value in re.findall(r"time[=<]\s*([\d.]+)\s*ms", output, flags=re.IGNORECASE)]
    if timings:
        return sum(timings) / len(timings)

    return None


def ping_server(hostname: str, count: int) -> Optional[float]:
    command = build_ping_command(hostname, count)
    logger.debug("Running ping: %s", " ".join(command))
    try:
        result = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=max(6, count * 3),
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0:
        return None

    return parse_ping_average(result.stdout)


def score_candidates(
    servers: Sequence[NordServer],
    protocol_key: str,
    group_key: str,
    ping_enabled: bool,
    ping_count: int,
    show_ping_progress: bool = False,
) -> list[CandidateScore]:
    candidates: list[CandidateScore] = []
    ping_total = min(len(servers), DEFAULT_PING_TOP) if ping_enabled else 0
    if show_ping_progress and ping_total:
        console.print(f"[yellow]Running ping tests for top {ping_total} candidate(s)...[/yellow]")

    for index, server in enumerate(servers):
        avg_ping = None
        if ping_enabled and index < DEFAULT_PING_TOP:
            if show_ping_progress:
                console.print(
                    f"[cyan]Ping {index + 1}/{ping_total}:[/cyan] {server.hostname} "
                    f"(load {server.load if server.load is not None else '-'})"
                )
            avg_ping = ping_server(server.hostname, ping_count)
            if show_ping_progress:
                if avg_ping is None:
                    console.print(f"[yellow]  Result:[/yellow] ping failed or no ICMP reply")
                else:
                    console.print(f"[green]  Result:[/green] {avg_ping:.1f} ms average")
        score = average_score(server.load, avg_ping)
        candidates.append(
            CandidateScore(
                server=server,
                protocol=protocol_key,
                group=group_key,
                average_ping_ms=avg_ping,
                score=score,
            )
        )

    def candidate_key(candidate: CandidateScore) -> tuple[float, int, str]:
        score_value = candidate.score if candidate.score is not None else 99999.0
        load_value = candidate.server.load if candidate.server.load is not None else 9999
        return (score_value, load_value, candidate.server.hostname)

    candidates.sort(key=candidate_key)
    if candidates:
        candidates[0].recommended = True
    return candidates


def print_candidates(candidates: Sequence[CandidateScore]) -> None:
    table = Table(title="Recommended NordVPN OpenVPN candidates")
    table.add_column("#", justify="right")
    table.add_column("Hostname", style="cyan")
    table.add_column("Country")
    table.add_column("City")
    table.add_column("Protocol")
    table.add_column("Group")
    table.add_column("Load", justify="right")
    table.add_column("Ping", justify="right")
    table.add_column("Score", justify="right")
    table.add_column("Station")
    table.add_column("Note")

    for index, candidate in enumerate(candidates, start=1):
        ping_value = f"{candidate.average_ping_ms:.1f} ms" if candidate.average_ping_ms is not None else "-"
        score_value = f"{candidate.score:.1f}" if candidate.score is not None else "-"
        note = "RECOMMENDED" if candidate.recommended else ""
        table.add_row(
            str(index),
            candidate.server.hostname,
            candidate.server.country_name,
            candidate.server.city_name or "Country Wide",
            PROTOCOLS[candidate.protocol].label,
            GROUPS[candidate.group].label,
            "-" if candidate.server.load is None else str(candidate.server.load),
            ping_value,
            score_value,
            candidate.server.station or "-",
            note,
        )

    console.print(table)


def parse_selection(selection: str, candidate_count: int) -> list[int]:
    normalized = selection.strip().casefold()
    if normalized == "":
        return []
    if normalized == "all":
        return list(range(candidate_count))

    chosen: list[int] = []
    for chunk in selection.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        range_match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", chunk)
        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2))
            if start > end:
                raise CliError(f"Selection range must be ascending: {chunk}")
            if start < 1 or end > candidate_count:
                raise CliError(f"Selection range out of range: {chunk}")
            chosen.extend(range(start - 1, end))
            continue
        try:
            index = int(chunk) - 1
        except ValueError as exc:
            raise CliError(f"Invalid selection item: {chunk}") from exc
        if index < 0 or index >= candidate_count:
            raise CliError(f"Selection index out of range: {chunk}")
        chosen.append(index)
    return sorted(set(chosen))


def pick_interactive_selection(candidates: Sequence[CandidateScore]) -> list[int]:
    while True:
        answer = questionary.text(
            "Download which config(s)? Examples: 1, 1-5, 1,3-7,10, all (blank = skip)",
            default="",
            style=PROMPT_STYLE,
        ).ask()
        if answer is None:
            return []
        try:
            return parse_selection(answer, len(candidates))
        except CliError as exc:
            console.print(f"[yellow]Invalid download selection:[/yellow] {exc}")


def download_candidate(
    client: NordApiClient,
    candidate: CandidateScore,
    output_dir: Path,
    force: bool,
    dry_run: bool,
    auth_credentials: Optional[AuthCredentials] = None,
) -> Path:
    url = build_cdn_url(candidate.server.hostname, candidate.protocol)
    filename = format_output_filename(candidate.server, candidate.protocol, candidate.group)
    destination = output_dir / filename
    cleanup_atomic_temp_files(output_dir, destination.name)
    auth_destination = output_dir / format_auth_output_filename(destination)
    cleanup_atomic_temp_files(output_dir, auth_destination.name)

    if destination.exists() and not force:
        if sys.stdin.isatty():
            overwrite = questionary.confirm(
                f"{destination.name} already exists. Overwrite?",
                default=False,
                style=PROMPT_STYLE,
            ).ask()
            if not overwrite:
                raise CliError(f"Skipped existing file: {destination.name}")
        else:
            raise CliError(f"{destination} already exists. Use --force to overwrite.")

    if auth_credentials and auth_destination.exists() and not force:
        if sys.stdin.isatty():
            overwrite = questionary.confirm(
                f"{auth_destination.name} already exists. Overwrite?",
                default=False,
                style=PROMPT_STYLE,
            ).ask()
            if not overwrite:
                raise CliError(f"Skipped existing file: {auth_destination.name}")
        else:
            raise CliError(f"{auth_destination} already exists. Use --force to overwrite.")

    if dry_run:
        console.print(f"[yellow]DRY RUN[/yellow] {destination} <- {url}")
        if auth_credentials:
            console.print(
                f"[yellow]DRY RUN[/yellow] patch auth-user-pass -> {auth_destination.name} "
                f"(source: {auth_credentials.source})"
            )
        return destination

    output_dir.mkdir(parents=True, exist_ok=True)
    text = client.get_text(url)
    if not validate_ovpn_payload(text):
        raise CliError(f"Downloaded config for {candidate.server.hostname} did not validate.")

    if auth_credentials:
        patched_text = patch_ovpn_auth_user_pass(text, auth_destination.name)
        auth_text = build_auth_file_contents(auth_credentials)
        try:
            write_text_atomic(auth_destination, auth_text, encoding="utf-8")
            write_text_atomic(destination, patched_text, encoding="utf-8")
        except BaseException:
            try:
                auth_destination.unlink()
            except FileNotFoundError:
                pass
            raise
    else:
        write_text_atomic(destination, text, encoding="utf-8")
    return destination


def list_countries(countries: Sequence[Country]) -> None:
    table = Table(title="Available countries")
    table.add_column("Country")
    table.add_column("Code")
    for country in countries:
        table.add_row(country.name, country.code or "-")
    console.print(table)


def list_cities(country: Country, cities: Sequence[City]) -> None:
    table = Table(title=f"Cities for {country.name}")
    table.add_column("City")
    for city in cities:
        table.add_row(city.name)
    console.print(table)


def list_groups(group_keys: Sequence[str]) -> None:
    table = Table(title="Server groups")
    table.add_column("Key")
    table.add_column("Label")
    table.add_column("Identifier")
    for key in group_keys:
        group = GROUPS[key]
        table.add_row(group.key, group.label, group.identifier)
    console.print(table)


def list_technologies(payload: dict[str, Any]) -> None:
    table = Table(title="Nord technologies")
    table.add_column("Identifier")
    table.add_column("Name")
    for item in sorted(
        payload.get("technologies", []),
        key=lambda entry: entry.get("identifier", ""),
    ):
        table.add_row(item.get("identifier", "-"), item.get("name", "-"))
    console.print(table)


def interactive_country_prompt(countries: Sequence[Country]) -> str:
    options = [country_prompt_option(country) for country in countries]
    answer = ask_autocomplete("Country", options, lambda text: resolve_autocomplete_option(text, options, "Country"))
    if answer is None:
        raise CliError("Country is required.")
    return answer


def interactive_city_prompt(country: Country, cities: Sequence[City]) -> Optional[str]:
    if not cities:
        return None
    options = [city_prompt_option(city) for city in cities]
    return ask_autocomplete(
        "City (blank for best country-wide recommendation)",
        options,
        lambda text: resolve_autocomplete_option(text, options, "City"),
        allow_blank=True,
    )


def interactive_protocol_prompt(protocol_keys: Sequence[str]) -> str:
    options = [protocol_prompt_option(key) for key in protocol_keys]
    answer = ask_autocomplete(
        "Protocol (blank for UDP)",
        options,
        lambda text: resolve_autocomplete_option(text, options, "Protocol"),
        allow_blank=True,
    )
    if answer is None:
        return "udp"
    return resolve_autocomplete_option(answer, options, "Protocol").value


def interactive_group_prompt(group_keys: Sequence[str]) -> str:
    options = [group_prompt_option(key) for key in group_keys]
    answer = ask_autocomplete(
        "Server group (blank for Standard)",
        options,
        lambda text: resolve_autocomplete_option(text, options, "Group"),
        allow_blank=True,
    )
    if answer is None:
        return "standard"
    return resolve_autocomplete_option(answer, options, "Group").value


def interactive_limit_prompt() -> int:
    while True:
        answer = questionary.text("Result limit", default=str(DEFAULT_LIMIT), style=PROMPT_STYLE).ask()
        if answer is None or not answer.strip():
            return DEFAULT_LIMIT
        try:
            return parse_positive_int(answer, "Result limit")
        except CliError as exc:
            console.print(f"[yellow]Invalid limit:[/yellow] {exc}")


def interactive_ping_prompt() -> bool:
    answer = questionary.confirm("Run ping test on the top candidates?", default=True, style=PROMPT_STYLE).ask()
    return bool(answer)


def maybe_warn_obfuscated(group_key: str, protocol_key: str, interactive: bool) -> None:
    if group_key != "obfuscated" and not protocol_key.startswith("xor_"):
        return
    message = (
        "Obfuscated OpenVPN configs may require XOR/scramble support. "
        "Some OpenVPN clients reject them."
    )
    console.print(Panel(message, title="Obfuscated warning", border_style="yellow"))
    if interactive:
        proceed = questionary.confirm("Continue?", default=True, style=PROMPT_STYLE).ask()
        if not proceed:
            raise CliError("Cancelled after obfuscated warning.")


def gather_filters(
    args: argparse.Namespace,
    countries: Sequence[Country],
    cities_by_country: dict[int, list[City]],
    prompt_protocol_keys: Sequence[str],
    prompt_group_keys: Sequence[str],
    allowed_protocol_keys: Sequence[str],
    allowed_group_keys: Sequence[str],
) -> tuple[Country, Optional[City], str, str, int, bool]:
    interactive = sys.stdin.isatty()

    country_query = args.country
    if not country_query:
        if not interactive:
            raise CliError("--country is required in non-interactive mode.")
        country_query = interactive_country_prompt(countries)
    country = pick_country(country_query, countries, interactive)

    available_cities = cities_by_country.get(country.id, [])
    city: Optional[City] = None
    city_query = args.city
    if city_query is None and interactive:
        city_query = interactive_city_prompt(country, available_cities)
    if city_query:
        city = pick_city(city_query, available_cities, interactive, country.name)

    protocol_key = args.protocol.strip().casefold() if args.protocol else None
    if not protocol_key:
        protocol_key = interactive_protocol_prompt(prompt_protocol_keys) if interactive else "udp"
    if protocol_key not in allowed_protocol_keys:
        supported = ", ".join(allowed_protocol_keys)
        raise CliError(f"Unsupported protocol '{protocol_key}'. Supported right now: {supported}")

    group_key = args.group.strip().casefold() if args.group else None
    if not group_key:
        group_key = interactive_group_prompt(prompt_group_keys) if interactive else "standard"
    if group_key not in allowed_group_keys:
        supported = ", ".join(allowed_group_keys)
        raise CliError(f"Unsupported group '{group_key}'. Supported right now: {supported}")

    limit = args.limit if args.limit is not None else (interactive_limit_prompt() if interactive else DEFAULT_LIMIT)
    partial_interactive = interactive and any(
        value is None for value in (args.country, args.city, args.protocol, args.group, args.limit)
    )
    ping_enabled = False if args.no_ping else (interactive_ping_prompt() if partial_interactive else True)

    maybe_warn_obfuscated(group_key, protocol_key, interactive)
    return country, city, protocol_key, group_key, limit, ping_enabled


def fetch_candidates(
    client: NordApiClient,
    v2_payload: dict[str, Any],
    country: Country,
    city: Optional[City],
    protocol_key: str,
    group_key: str,
    limit: int,
    refresh_cache: bool,
    full_data: bool,
) -> list[NordServer]:
    protocol = PROTOCOLS[protocol_key]
    group = GROUPS[group_key]
    recommendation_limit = max(DEFAULT_FETCH_LIMIT, min(max(limit * 5, DEFAULT_FETCH_LIMIT), 2500))
    recommended_raw = client.get_recommendations(
        country_id=country.id,
        group_identifier=group.identifier,
        technology_identifier=protocol.technology,
        limit=recommendation_limit,
        refresh=refresh_cache,
    )
    recommended_servers = filter_servers(
        [recommendation_to_server(item) for item in recommended_raw],
        country_id=country.id,
        city_id=city.id if city else None,
        group_identifier=group.identifier,
        technology_identifier=protocol.technology,
    )
    recommended_servers = dedupe_servers(recommended_servers)
    if recommended_servers and not full_data and (city is None or len(recommended_servers) >= min(limit, 3)):
        return recommended_servers[:limit]

    normalized_v2 = normalize_v2_servers(v2_payload)
    fallback_servers = filter_servers(
        normalized_v2,
        country_id=country.id,
        city_id=city.id if city else None,
        group_identifier=group.identifier,
        technology_identifier=protocol.technology,
    )
    fallback_servers = dedupe_servers(fallback_servers)
    return fallback_servers[:limit]


def download_selected_candidates(
    client: NordApiClient,
    candidates: Sequence[CandidateScore],
    selected_indexes: Sequence[int],
    output_dir: Path,
    force: bool,
    dry_run: bool,
    auth_credentials: Optional[AuthCredentials],
) -> tuple[list[Path], list[str]]:
    downloaded: list[Path] = []
    errors: list[str] = []

    for index in selected_indexes:
        try:
            downloaded.append(
                download_candidate(
                    client=client,
                    candidate=candidates[index],
                    output_dir=output_dir,
                    force=force,
                    dry_run=dry_run,
                    auth_credentials=auth_credentials,
                )
            )
        except CliError as exc:
            errors.append(str(exc))
            console.print(f"[red]Download error:[/red] {exc}")

    return downloaded, errors


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Find and download NordVPN OpenVPN configs.",
        allow_abbrev=False,
    )
    parser.add_argument("--country", help="Country name or code.")
    parser.add_argument("--city", help="City name.")
    parser.add_argument("--protocol", help="Protocol to use.")
    parser.add_argument("--group", help="Server group to use.")
    parser.add_argument("--limit", type=argparse_positive_int, help="Number of results to show.")
    parser.add_argument("--output-dir", type=Path, default=get_default_output_dir(), help="Download directory.")
    download_group = parser.add_mutually_exclusive_group()
    download_group.add_argument("--download-best", action="store_true", help="Download the top candidate.")
    download_group.add_argument("--download-top", type=argparse_positive_int, help="Download the top N candidates.")
    parser.add_argument("--full-data", action="store_true", help="Force the V2 dataset path.")
    parser.add_argument("--no-ping", action="store_true", help="Skip ping testing.")
    parser.add_argument(
        "--ping-count",
        type=argparse_positive_int,
        default=DEFAULT_PING_COUNT,
        help="Ping attempts per host.",
    )
    parser.add_argument("--refresh-cache", action="store_true", help="Refresh cached API payloads.")
    parser.add_argument("--list-countries", action="store_true", help="List available countries.")
    parser.add_argument("--list-cities", action="store_true", help="List available cities for the selected country.")
    parser.add_argument("--list-groups", action="store_true", help="List supported groups.")
    parser.add_argument("--list-technologies", action="store_true", help="List Nord technologies from V2.")
    parser.add_argument("--advanced", action="store_true", help="Expose advanced prompt choices such as XOR.")
    parser.add_argument("--auth-username", help="Override auth config username for downloaded OpenVPN auth files.")
    parser.add_argument("--auth-password", help="Override auth config password for downloaded OpenVPN auth files.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files.")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing files.")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    configure_logging(args.verbose)
    auth_credentials = resolve_auth_credentials(args)
    client = NordApiClient()
    v2_payload = client.get_v2_dataset(refresh=args.refresh_cache)
    prompt_protocol_keys = supported_protocol_keys(v2_payload, args.advanced)
    prompt_group_keys = supported_group_keys(v2_payload, args.advanced)
    allowed_protocol_keys = supported_protocol_keys(v2_payload, include_advanced=True)
    allowed_group_keys = supported_group_keys(v2_payload, include_advanced=True)

    countries, cities_by_country = parse_countries(v2_payload)

    if args.list_countries:
        list_countries(countries)
        return 0
    if args.list_groups:
        list_groups(allowed_group_keys)
        return 0
    if args.list_technologies:
        list_technologies(v2_payload)
        return 0

    if args.list_cities:
        if not args.country:
            raise CliError("--country is required with --list-cities.")
        country = pick_country(args.country, countries, interactive=sys.stdin.isatty())
        list_cities(country, cities_by_country.get(country.id, []))
        return 0

    country, city, protocol_key, group_key, limit, ping_enabled = gather_filters(
        args,
        countries,
        cities_by_country,
        prompt_protocol_keys,
        prompt_group_keys,
        allowed_protocol_keys,
        allowed_group_keys,
    )
    candidates = score_candidates(
        fetch_candidates(
            client=client,
            v2_payload=v2_payload,
            country=country,
            city=city,
            protocol_key=protocol_key,
            group_key=group_key,
            limit=limit,
            refresh_cache=args.refresh_cache,
            full_data=args.full_data,
        ),
        protocol_key=protocol_key,
        group_key=group_key,
        ping_enabled=ping_enabled,
        ping_count=args.ping_count,
        show_ping_progress=ping_enabled and sys.stdout.isatty(),
    )

    if not candidates:
        raise CliError("No NordVPN servers matched the selected filters.")

    print_candidates(candidates)

    selected_indexes: list[int] = []
    if args.download_best:
        selected_indexes = [0]
    elif args.download_top:
        selected_indexes = list(range(min(args.download_top, len(candidates))))
    elif sys.stdin.isatty():
        selected_indexes = pick_interactive_selection(candidates)

    if not selected_indexes:
        return 0

    output_dir = args.output_dir.expanduser().resolve()
    downloaded, download_errors = download_selected_candidates(
        client=client,
        candidates=candidates,
        selected_indexes=selected_indexes,
        output_dir=output_dir,
        force=args.force,
        dry_run=args.dry_run,
        auth_credentials=auth_credentials,
    )

    if downloaded:
        table = Table(title="Downloaded configs")
        table.add_column("Path", style="green")
        for path in downloaded:
            table.add_row(str(path))
        console.print(table)

    if download_errors:
        raise CliError(f"{len(download_errors)} download(s) failed. See errors above.")

    return 0


if __name__ == "__main__":
    previous_signal_handlers = install_signal_handlers()
    try:
        raise SystemExit(main())
    except CancelledError as exc:
        console.print(f"[yellow]{exc.message}[/yellow]")
        raise SystemExit(130)
    except KeyboardInterrupt:
        console.print("[yellow]Cancelled by user.[/yellow]")
        raise SystemExit(130)
    except CliError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise SystemExit(1)
    finally:
        restore_signal_handlers(previous_signal_handlers)
