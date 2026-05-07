import json
from pathlib import Path
from types import SimpleNamespace

import nord_ovpn_picker as picker
from nord_ovpn_picker import (
    Country,
    NordServer,
    filter_servers,
    gather_filters,
    normalize_v2_servers,
    score_candidates,
    supported_group_keys,
    supported_protocol_keys,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_supported_keys_from_v2_fixture() -> None:
    payload = load_fixture("v2_servers.json")
    assert supported_group_keys(payload, include_advanced=False) == ["standard", "p2p"]
    assert supported_protocol_keys(payload, include_advanced=False) == ["udp", "tcp"]


def test_normalize_and_filter_v2_servers() -> None:
    payload = load_fixture("v2_servers.json")
    servers = normalize_v2_servers(payload)
    filtered = filter_servers(
        servers,
        country_id=13,
        city_id=1001,
        group_identifier="legacy_standard",
        technology_identifier="openvpn_udp",
    )
    assert [server.hostname for server in filtered] == ["au666.nordvpn.com"]


def test_score_candidates_can_prefer_lower_load_over_slightly_lower_ping(monkeypatch) -> None:
    ping_values = {
        "au-load11.example": 3.6,
        "au-load12.example": 3.2,
    }

    monkeypatch.setattr(picker, "ping_server", lambda hostname, count: ping_values[hostname])

    servers = [
        NordServer(
            hostname="au-load11.example",
            name=None,
            load=11,
            station=None,
            country_name="Australia",
            country_code="AU",
            country_id=13,
            city_name="Melbourne",
            city_id=1001,
            group_identifiers=["legacy_standard"],
            technology_identifiers=["openvpn_udp"],
            status="online",
        ),
        NordServer(
            hostname="au-load12.example",
            name=None,
            load=12,
            station=None,
            country_name="Australia",
            country_code="AU",
            country_id=13,
            city_name="Melbourne",
            city_id=1001,
            group_identifiers=["legacy_standard"],
            technology_identifiers=["openvpn_udp"],
            status="online",
        ),
    ]

    candidates = score_candidates(
        servers,
        protocol_key="udp",
        group_key="standard",
        ping_enabled=True,
        ping_count=1,
    )

    assert candidates[0].server.hostname == "au-load11.example"
    assert candidates[0].score == 25.6
    assert candidates[1].score == 27.2


def test_gather_filters_accepts_case_insensitive_cli_values() -> None:
    args = SimpleNamespace(
        country="Australia",
        city=None,
        protocol="UDP",
        group="P2P",
        limit=5,
        no_ping=True,
    )
    countries = [Country(id=13, name="Australia", code="AU")]

    country, city, protocol_key, group_key, limit, ping_enabled = gather_filters(
        args,
        countries,
        {13: []},
        prompt_protocol_keys=["udp", "tcp"],
        prompt_group_keys=["standard", "p2p"],
        allowed_protocol_keys=["udp", "tcp", "xor_udp"],
        allowed_group_keys=["standard", "p2p", "obfuscated"],
    )

    assert country.id == 13
    assert city is None
    assert protocol_key == "udp"
    assert group_key == "p2p"
    assert limit == 5
    assert ping_enabled is False


def test_gather_filters_accepts_explicit_advanced_cli_values_without_advanced_flag() -> None:
    args = SimpleNamespace(
        country="Australia",
        city=None,
        protocol="xor_udp",
        group="Obfuscated",
        limit=5,
        no_ping=True,
    )
    countries = [Country(id=13, name="Australia", code="AU")]

    _, _, protocol_key, group_key, _, _ = gather_filters(
        args,
        countries,
        {13: []},
        prompt_protocol_keys=["udp", "tcp"],
        prompt_group_keys=["standard", "p2p"],
        allowed_protocol_keys=["udp", "tcp", "xor_udp"],
        allowed_group_keys=["standard", "p2p", "obfuscated"],
    )

    assert protocol_key == "xor_udp"
    assert group_key == "obfuscated"
