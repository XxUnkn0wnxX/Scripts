import json
from pathlib import Path

from nord_ovpn_picker import (
    filter_servers,
    normalize_v2_servers,
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
