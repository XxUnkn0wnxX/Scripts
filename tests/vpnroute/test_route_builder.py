from pathlib import Path

import pytest

import vpnroute
from vpnroute import CliError, DomainResult, RouteOptions, build_route_line, render_output, write_text_atomic


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
        ["first.example", "second.example"],
        RouteOptions(netmask="255.255.255.255", gateway=None, metric=None, no_comments=False),
    )

    assert unique_routes == 3
    assert results[0].route_lines == [
        "route 1.1.1.1 255.255.255.255",
        "route 2.2.2.2 255.255.255.255",
    ]
    assert results[1].route_lines == ["route 3.3.3.3 255.255.255.255"]


def test_render_output_includes_failed_domain_comment() -> None:
    rendered = render_output(
        [
            DomainResult("example.com", ["route 1.1.1.1 255.255.255.255"], ["1.1.1.1"]),
            DomainResult("broken.example", [], [], failure_reason="no IPv4 records found"),
        ],
        no_comments=False,
    )

    assert "# example.com" in rendered
    assert "route 1.1.1.1 255.255.255.255" in rendered
    assert "# FAILED: broken.example - no IPv4 records found" in rendered


def test_render_output_no_comments_keeps_only_routes() -> None:
    rendered = render_output(
        [
            DomainResult("example.com", ["route 1.1.1.1 255.255.255.255"], ["1.1.1.1"]),
            DomainResult("broken.example", [], [], failure_reason="no IPv4 records found"),
        ],
        no_comments=True,
    )

    assert rendered == "route 1.1.1.1 255.255.255.255\n"


def test_write_text_atomic_replaces_destination(tmp_path: Path) -> None:
    destination = tmp_path / "vpn_routes.txt"
    write_text_atomic(destination, "route 1.1.1.1 255.255.255.255\n")
    assert destination.read_text(encoding="utf-8") == "route 1.1.1.1 255.255.255.255\n"
