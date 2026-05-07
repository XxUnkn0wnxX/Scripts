#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

APP_NAME = "vpnroute"
SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
REPO_VENV_DIR = SCRIPT_DIR / ".venv"
REQUIREMENTS_PATH = SCRIPT_DIR / "requirements.txt"
DOCS_PATH = SCRIPT_DIR / "docs" / "vpnroute.md"
REEXEC_ENV = "VPNROUTE_REEXEC"


def is_windows_platform(platform: str | None = None) -> bool:
    active_platform = platform or sys.platform
    return active_platform.startswith("win")


def get_repo_venv_python_candidates(venv_dir: Path, platform: str | None = None) -> list[Path]:
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


def resolve_repo_venv_python(venv_dir: Path) -> Path | None:
    for candidate in get_repo_venv_python_candidates(venv_dir):
        if candidate.exists():
            return candidate
    return None


def docs_hint() -> str:
    return str(DOCS_PATH.relative_to(SCRIPT_DIR)) if DOCS_PATH.exists() else "docs/vpnroute.md"


def fail_with_docs(reason: str, exit_code: int = 1) -> None:
    print(f"{reason}\n")
    print("Read setup instructions here:")
    print(f"  {docs_hint()}")
    raise SystemExit(exit_code)


def ensure_requirements_file_exists() -> None:
    if not REQUIREMENTS_PATH.exists():
        fail_with_docs("Missing requirements.txt next to vpnroute.py.")


def ensure_repo_venv_or_reexec(argv: list[str] | None = None) -> None:
    ensure_requirements_file_exists()

    active_argv = list(argv if argv is not None else sys.argv[1:])
    repo_venv_python = resolve_repo_venv_python(REPO_VENV_DIR)

    if not REPO_VENV_DIR.exists() or repo_venv_python is None:
        fail_with_docs("No local .venv was found for vpnroute.py.")

    current_prefix = Path(sys.prefix)
    target_prefix = REPO_VENV_DIR

    if (
        normalize_platform_path(current_prefix) != normalize_platform_path(target_prefix)
        and os.environ.get(REEXEC_ENV) != "1"
    ):
        os.environ[REEXEC_ENV] = "1"
        os.execv(str(repo_venv_python), [str(repo_venv_python), str(SCRIPT_PATH), *active_argv])


ensure_repo_venv_or_reexec()


import argparse
import builtins
import ipaddress
import logging
import signal
import tempfile
from typing import Callable, Iterable
from urllib.parse import urlsplit

try:
    import dns.exception
    import dns.resolver
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table
except ImportError as exc:
    package_name = getattr(exc, "name", None) or str(exc)
    fail_with_docs(
        f"Missing Python dependency: {package_name}\n\n"
        "Your repo-local .venv exists, but dependencies do not look installed."
    )

DEFAULT_OUTPUT = Path("vpn_routes.txt")
DEFAULT_NETMASK = "255.255.255.255"
DNS_TIMEOUT = 5.0

console = Console()
logger = logging.getLogger(APP_NAME)


class CliError(RuntimeError):
    """Raised for user-visible CLI failures."""


class CancelledError(KeyboardInterrupt):
    """Raised when the user cancels the script."""


@dataclass(frozen=True)
class RouteOptions:
    netmask: str
    gateway: str | None
    metric: str | None
    no_comments: bool


@dataclass(frozen=True)
class DomainResult:
    domain: str
    route_lines: list[str]
    resolved_ips: list[str]
    failure_reason: str | None = None


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=SCRIPT_PATH.name,
        description="Convert websites/domains into OpenVPN or Viscosity route commands.",
        allow_abbrev=False,
    )
    parser.add_argument("input_file", nargs="?", type=Path, help="Optional file containing one domain or URL per line.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output file path. Default: vpn_routes.txt")
    parser.add_argument(
        "--netmask",
        default=DEFAULT_NETMASK,
        help="IPv4 netmask or CIDR value such as 255.255.255.255, 32, /32, 24, or /24.",
    )
    parser.add_argument("--gateway", help="Optional route gateway.")
    parser.add_argument("--metric", help="Optional route metric.")
    parser.add_argument("--no-comments", action="store_true", help="Write only route lines without grouping comments.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing output file.")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    return parser.parse_args(argv)


def normalize_netmask(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        raise ValueError("Netmask cannot be blank")

    if candidate.startswith("/"):
        candidate = candidate[1:]

    if candidate.isdigit():
        cidr = int(candidate)
        if cidr < 0 or cidr > 32:
            raise ValueError("CIDR must be between 0 and 32")
        return str(ipaddress.IPv4Network(f"0.0.0.0/{cidr}").netmask)

    network = ipaddress.IPv4Network(f"0.0.0.0/{candidate}")
    return str(network.netmask)


def strip_inline_comment(value: str) -> str:
    if "#" not in value:
        return value
    return value.split("#", 1)[0].strip()


def extract_hostname(raw_line: str) -> str | None:
    stripped = raw_line.strip()
    if not stripped or stripped.startswith("#"):
        return None

    candidate = strip_inline_comment(stripped)
    if not candidate:
        return None

    if "://" in candidate:
        parsed = urlsplit(candidate)
    else:
        parsed = urlsplit(f"//{candidate}")

    hostname = parsed.hostname
    if not hostname:
        return None

    normalized = hostname.strip().lower().rstrip(".")
    return normalized or None


def normalize_domains(lines: Iterable[str]) -> list[str]:
    domains: list[str] = []
    seen: set[str] = set()

    for line in lines:
        hostname = extract_hostname(line)
        if not hostname or hostname in seen:
            continue
        seen.add(hostname)
        domains.append(hostname)

    return domains


def load_input_lines(input_file: Path | None) -> list[str]:
    if input_file is None:
        return collect_interactive_lines()

    try:
        return input_file.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise CliError(f"Input file not found: {input_file}") from exc
    except OSError as exc:
        raise CliError(f"Unable to read input file: {input_file}") from exc


def collect_interactive_lines(
    input_func: Callable[[str], str] | None = None,
    active_console: Console | None = None,
) -> list[str]:
    runner = input_func or builtins.input
    ui = active_console or console
    ui.print(
        Panel.fit(
            "Paste domains/URLs below, one per line.\nPress ENTER on a blank line to process.",
            title="vpnroute",
        )
    )

    lines: list[str] = []
    while True:
        try:
            line = runner("")
        except EOFError:
            break

        if line.strip() == "":
            if lines:
                break
            ui.print("No input provided.")
            return []

        lines.append(line)

    return lines


def build_route_line(ip_address: str, netmask: str, gateway: str | None = None, metric: str | None = None) -> str:
    parts = ["route", ip_address, netmask]

    if gateway:
        parts.append(gateway)

    if metric:
        if not gateway:
            parts.append("default")
        parts.append(metric)

    return " ".join(parts)


def build_resolver() -> dns.resolver.Resolver:
    resolver = dns.resolver.Resolver(configure=True)
    resolver.lifetime = DNS_TIMEOUT
    resolver.timeout = DNS_TIMEOUT
    return resolver


def resolve_ipv4_records(domain: str, resolver: dns.resolver.Resolver | None = None) -> list[str]:
    active_resolver = resolver or build_resolver()

    try:
        answers = active_resolver.resolve(domain, "A")
    except dns.resolver.NXDOMAIN as exc:
        raise CliError("no IPv4 records found") from exc
    except dns.resolver.NoAnswer as exc:
        raise CliError("no IPv4 records found") from exc
    except dns.resolver.NoNameservers as exc:
        raise CliError("no reachable nameservers") from exc
    except dns.exception.Timeout as exc:
        raise CliError("DNS lookup timed out") from exc
    except dns.exception.DNSException as exc:
        raise CliError(str(exc) or "DNS lookup failed") from exc

    seen: set[str] = set()
    ipv4_records: list[str] = []
    for record in answers:
        address = getattr(record, "address", str(record))
        if address not in seen:
            seen.add(address)
            ipv4_records.append(address)

    if not ipv4_records:
        raise CliError("no IPv4 records found")

    return ipv4_records


def resolve_domains(domains: list[str], route_options: RouteOptions) -> tuple[list[DomainResult], int]:
    resolver = build_resolver()
    seen_ips: set[str] = set()
    results: list[DomainResult] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task_id = progress.add_task("Resolving domains...", total=None)

        for domain in domains:
            progress.update(task_id, description=f"Resolving {domain}")
            try:
                resolved_ips = resolve_ipv4_records(domain, resolver=resolver)
            except CliError as exc:
                results.append(DomainResult(domain=domain, route_lines=[], resolved_ips=[], failure_reason=str(exc)))
                continue

            route_lines: list[str] = []
            for ip_address in resolved_ips:
                if ip_address in seen_ips:
                    continue
                seen_ips.add(ip_address)
                route_lines.append(
                    build_route_line(
                        ip_address,
                        route_options.netmask,
                        gateway=route_options.gateway,
                        metric=route_options.metric,
                    )
                )

            results.append(DomainResult(domain=domain, route_lines=route_lines, resolved_ips=resolved_ips))

    return results, len(seen_ips)


def render_output(results: list[DomainResult], no_comments: bool) -> str:
    chunks: list[str] = []

    for result in results:
        lines: list[str] = []
        if result.failure_reason:
            if no_comments:
                continue
            lines.append(f"# FAILED: {result.domain} - {result.failure_reason}")
        else:
            if not no_comments:
                lines.append(f"# {result.domain}")
            lines.extend(result.route_lines)

        if lines:
            chunks.append("\n".join(lines))

    rendered = "\n\n".join(chunks).strip()
    return f"{rendered}\n" if rendered else ""


def ensure_output_path(output_path: Path, force: bool) -> None:
    if output_path.exists() and not force:
        raise CliError(f"Output file already exists: {output_path}. Use --force to overwrite it.")

    parent = output_path.parent
    if parent != Path(""):
        parent.mkdir(parents=True, exist_ok=True)


def write_text_atomic(destination: Path, content: str, encoding: str = "utf-8") -> None:
    destination_parent = destination.parent if str(destination.parent) else Path(".")
    temp_fd = -1
    temp_name = ""

    try:
        temp_fd, temp_name = tempfile.mkstemp(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=str(destination_parent),
        )
        with os.fdopen(temp_fd, "w", encoding=encoding) as handle:
            temp_fd = -1
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, destination)
    except Exception:
        if temp_fd != -1:
            os.close(temp_fd)
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
        raise


def print_results_table(results: list[DomainResult]) -> None:
    table = Table(title="Route Resolution Summary")
    table.add_column("Domain")
    table.add_column("Status")
    table.add_column("IPv4")

    for result in results:
        if result.failure_reason:
            table.add_row(result.domain, f"[yellow]FAILED[/yellow]", result.failure_reason)
            continue

        count = len(result.route_lines)
        label = "OK" if count else "DUPLICATE"
        table.add_row(result.domain, f"[green]{label}[/green]", str(count))

    console.print(table)


def print_summary(results: list[DomainResult], unique_routes: int, output_path: Path) -> None:
    failed_count = sum(1 for result in results if result.failure_reason)
    summary = (
        "Done.\n"
        f"Domains processed: {len(results)}\n"
        f"Unique IPv4 routes: {unique_routes}\n"
        f"Failures: {failed_count}\n"
        f"Output written to: {output_path}"
    )
    console.print(Panel.fit(summary, title="vpnroute"))


def install_signal_handlers() -> dict[int, signal.Handlers]:
    previous: dict[int, signal.Handlers] = {}
    for signum in (signal.SIGINT, signal.SIGTERM):
        previous[signum] = signal.getsignal(signum)
        signal.signal(signum, handle_termination_signal)
    return previous


def restore_signal_handlers(previous: dict[int, signal.Handlers]) -> None:
    for signum, handler in previous.items():
        signal.signal(signum, handler)


def handle_termination_signal(signum: int, frame: object | None) -> None:
    raise CancelledError(f"Cancelled by user ({signal.Signals(signum).name}).")


def print_generated_output(content: str) -> None:
    console.print(Panel.fit("Generated route output", title="vpnroute"))
    if content:
        console.print(content.rstrip("\n"))
    else:
        console.print("[yellow]No route lines were generated.[/yellow]")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(args.verbose)

    try:
        normalized_netmask = normalize_netmask(args.netmask)
        lines = load_input_lines(args.input_file)
        if not lines and args.input_file is None:
            return 0
        domains = normalize_domains(lines)
        if not domains:
            raise CliError("No valid domains or URLs were provided.")

        route_options = RouteOptions(
            netmask=normalized_netmask,
            gateway=args.gateway,
            metric=args.metric,
            no_comments=args.no_comments,
        )

        previous_handlers = install_signal_handlers()
        try:
            results, unique_routes = resolve_domains(domains, route_options)
            output_text = render_output(results, args.no_comments)
            output_path = args.output.expanduser()
            ensure_output_path(output_path, args.force)
            write_text_atomic(output_path, output_text)
        finally:
            restore_signal_handlers(previous_handlers)

        print_generated_output(output_text)
        print_results_table(results)
        print_summary(results, unique_routes, output_path)
        return 0
    except CancelledError:
        console.print("Cancelled by user.")
        return 130
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        return 1
    except CliError as exc:
        console.print(f"[red]{exc}[/red]")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
