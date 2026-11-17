import pytest

from nord_ovpn_picker import CliError, build_cdn_url, parse_selection


@pytest.mark.parametrize(
    ("protocol", "cdn_dir", "suffix"),
    [("udp", "ovpn_udp", "udp"), ("tcp", "ovpn_tcp", "tcp"), ("xor_udp", "ovpn_xor_udp", "udp"), ("xor_tcp", "ovpn_xor_tcp", "tcp")],
)
def test_build_cdn_url_selects_modern_by_default_and_legacy_when_requested(
    protocol: str, cdn_dir: str, suffix: str
) -> None:
    base = f"https://downloads.nordcdn.com/configs/files/{cdn_dir}/servers/au666.nordvpn.com.{suffix}"

    assert build_cdn_url("au666.nordvpn.com", protocol) == f"{base}_2.6.ovpn"
    assert build_cdn_url("au666.nordvpn.com", protocol, legacy=True) == f"{base}.ovpn"


def test_parse_selection_variants() -> None:
    assert parse_selection("", 5) == []
    assert parse_selection("1,3,5", 5) == [0, 2, 4]
    assert parse_selection("1-3", 5) == [0, 1, 2]
    assert parse_selection("1,3-5", 5) == [0, 2, 3, 4]
    assert parse_selection("1,3-5,5", 5) == [0, 2, 3, 4]

@pytest.mark.parametrize("selection", ["top", "top3", "none", "foo", "1,a", "0", "9", "0-2", "5-3", "3-9", "3-7-10"])
def test_parse_selection_invalid_variants(selection: str) -> None:
    with pytest.raises(CliError):
        parse_selection(selection, 3)
