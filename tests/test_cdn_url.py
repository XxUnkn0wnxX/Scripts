import pytest

from nord_ovpn_picker import CliError, build_cdn_url, parse_selection


def test_build_udp_cdn_url() -> None:
    assert (
        build_cdn_url("au666.nordvpn.com", "udp")
        == "https://downloads.nordcdn.com/configs/files/ovpn_udp/servers/au666.nordvpn.com.udp.ovpn"
    )


def test_build_tcp_cdn_url() -> None:
    assert (
        build_cdn_url("au666.nordvpn.com", "tcp")
        == "https://downloads.nordcdn.com/configs/files/ovpn_tcp/servers/au666.nordvpn.com.tcp.ovpn"
    )


def test_parse_selection_variants() -> None:
    assert parse_selection("none", 5) == []
    assert parse_selection("top3", 5) == [0, 1, 2]
    assert parse_selection("top 3", 5) == [0, 1, 2]
    assert parse_selection("1,3,5", 5) == [0, 2, 4]


@pytest.mark.parametrize("selection", ["top", "foo", "1,a", "0", "9", "top0"])
def test_parse_selection_invalid_variants(selection: str) -> None:
    with pytest.raises(CliError):
        parse_selection(selection, 3)
