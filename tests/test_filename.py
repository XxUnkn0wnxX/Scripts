from nord_ovpn_picker import NordServer, format_output_filename, sanitize_filename


def make_server() -> NordServer:
    return NordServer(
        hostname="au666.nordvpn.com",
        name="Australia #666",
        load=11,
        station="103.137.14.211",
        country_name="Australia",
        country_code="AU",
        country_id=13,
        city_name="Melbourne",
        city_id=1001,
        group_identifiers=["legacy_standard", "legacy_p2p"],
        technology_identifiers=["openvpn_udp", "openvpn_tcp"],
        status="online",
    )


def test_format_output_filename() -> None:
    assert (
        format_output_filename(make_server(), "udp", "standard")
        == "Australia (AU) - Melbourne [UDP] [Standard] - au666.nordvpn.com.ovpn"
    )


def test_sanitize_filename_replaces_invalid_characters() -> None:
    assert sanitize_filename('bad:/\\\\name*?"<>|') == "bad-name-"
