from pathlib import Path

import pytest

import vpnroute
from vpnroute import DomainResult, InputEntry, RouteOptions, build_route_line, render_output, resolve_output_path, write_text_atomic


def test_build_route_line_defaults_to_destination_and_netmask_only() -> None:
    assert build_route_line("104.19.222.79", "255.255.255.255") == "route 104.19.222.79 255.255.255.255"


def test_build_route_line_adds_gateway() -> None:
    assert (
        build_route_line("104.19.222.79", "255.255.255.255", gateway="vpn_gateway")
        == "route 104.19.222.79 255.255.255.255 vpn_gateway"
    )


def test_build_route_line_adds_default_gateway_for_metric_only() -> None:
    assert (
        build_route_line("104.19.222.79", "255.255.255.255", metric="default")
        == "route 104.19.222.79 255.255.255.255 default default"
    )


def test_build_route_line_adds_gateway_and_metric() -> None:
    assert (
        build_route_line("104.19.222.79", "255.255.255.255", gateway="vpn_gateway", metric="default")
        == "route 104.19.222.79 255.255.255.255 vpn_gateway default"
    )


def test_resolve_domains_deduplicates_ips_globally(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = {
        "first.example": ["1.1.1.1", "2.2.2.2"],
        "second.example": ["2.2.2.2", "3.3.3.3"],
    }

    monkeypatch.setattr(vpnroute, "build_resolver", lambda: object())
    monkeypatch.setattr(vpnroute, "resolve_ipv4_records", lambda domain, resolver=None: responses[domain])

    results, unique_routes = vpnroute.resolve_domains(
        [
            InputEntry(source_text="https://first.example/path", hostname="first.example"),
            InputEntry(source_text="https://second.example/path", hostname="second.example"),
        ],
        RouteOptions(netmask="255.255.255.255", gateway=None, metric=None, no_comments=False, ip_only=False),
    )

    assert unique_routes == 3
    assert results[0].unique_ips == ["1.1.1.1", "2.2.2.2"]
    assert results[0].route_lines == [
        "route 1.1.1.1 255.255.255.255",
        "route 2.2.2.2 255.255.255.255",
    ]
    assert results[1].unique_ips == ["3.3.3.3"]
    assert results[1].route_lines == ["route 3.3.3.3 255.255.255.255"]


def test_render_output_includes_failed_domain_comment() -> None:
    rendered = render_output(
        [
            DomainResult("example.com", "https://example.com/path", ["route 1.1.1.1 255.255.255.255"], ["1.1.1.1"], ["1.1.1.1"]),
            DomainResult("broken.example", "https://broken.example/path", [], [], [], failure_reason="no IPv4 records found"),
        ],
        RouteOptions(netmask="255.255.255.255", gateway=None, metric=None, no_comments=False, ip_only=False),
    )

    assert "# example.com" in rendered
    assert "route 1.1.1.1 255.255.255.255" in rendered
    assert "# invalid urls" in rendered
    assert "https://broken.example/path" in rendered


def test_render_output_no_comments_keeps_only_routes() -> None:
    rendered = render_output(
        [
            DomainResult("example.com", "https://example.com/path", ["route 1.1.1.1 255.255.255.255"], ["1.1.1.1"], ["1.1.1.1"]),
            DomainResult("broken.example", "https://broken.example/path", [], [], [], failure_reason="no IPv4 records found"),
        ],
        RouteOptions(netmask="255.255.255.255", gateway=None, metric=None, no_comments=True, ip_only=False),
    )

    assert rendered == "route 1.1.1.1 255.255.255.255\n"


def test_render_output_no_comments_flattens_multiple_domains_into_one_block() -> None:
    rendered = render_output(
        [
            DomainResult("first.example", "https://first.example/path", ["route 1.1.1.1 255.255.255.255"], ["1.1.1.1"], ["1.1.1.1"]),
            DomainResult("second.example", "https://second.example/path", ["route 2.2.2.2 255.255.255.255"], ["2.2.2.2"], ["2.2.2.2"]),
        ],
        RouteOptions(netmask="255.255.255.255", gateway=None, metric=None, no_comments=True, ip_only=False),
    )

    assert rendered == "route 1.1.1.1 255.255.255.255\nroute 2.2.2.2 255.255.255.255\n"


def test_render_output_iponly_keeps_comments_by_default() -> None:
    rendered = render_output(
        [
            DomainResult("example.com", "https://example.com/path", ["route 1.1.1.1 255.255.255.255"], ["1.1.1.1"], ["1.1.1.1"]),
            DomainResult("broken.example", "https://broken.example/path", [], [], [], failure_reason="no IPv4 records found"),
        ],
        RouteOptions(netmask="255.255.255.255", gateway=None, metric=None, no_comments=False, ip_only=True),
    )

    assert rendered == "# example.com\n1.1.1.1\n\n# invalid urls\nhttps://broken.example/path\n"


def test_render_output_iponly_with_no_comments_keeps_only_ips() -> None:
    rendered = render_output(
        [
            DomainResult(
                "example.com",
                "https://example.com/path",
                ["route 1.1.1.1 255.255.255.255", "route 2.2.2.2 255.255.255.255"],
                ["1.1.1.1", "2.2.2.2"],
                ["1.1.1.1", "2.2.2.2"],
            ),
            DomainResult("broken.example", "https://broken.example/path", [], [], [], failure_reason="no IPv4 records found"),
        ],
        RouteOptions(netmask="255.255.255.255", gateway=None, metric=None, no_comments=True, ip_only=True),
    )

    assert rendered == "1.1.1.1\n2.2.2.2\n"


def test_write_text_atomic_replaces_destination(tmp_path: Path) -> None:
    destination = tmp_path / "vpn_routes.txt"
    write_text_atomic(destination, "route 1.1.1.1 255.255.255.255\n")
    assert destination.read_text(encoding="utf-8") == "route 1.1.1.1 255.255.255.255\n"


def test_write_text_atomic_overwrites_existing_destination(tmp_path: Path) -> None:
    destination = tmp_path / "vpn_routes.txt"
    destination.write_text("old payload\n", encoding="utf-8")
    write_text_atomic(destination, "new payload\n")
    assert destination.read_text(encoding="utf-8") == "new payload\n"


def test_resolve_output_path_uses_current_working_directory_for_relative_paths(tmp_path: Path) -> None:
    assert resolve_output_path(Path("vpn_routes.txt"), cwd=tmp_path) == tmp_path / "vpn_routes.txt"
    assert resolve_output_path(Path("nested/routes.conf"), cwd=tmp_path) == tmp_path / "nested" / "routes.conf"


def test_resolve_output_path_keeps_absolute_paths() -> None:
    absolute = Path("/tmp/vpnroute-output.conf")
    assert resolve_output_path(absolute, cwd=Path("/private/tmp/ignored")) == absolute
