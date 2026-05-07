from nord_ovpn_picker import NordServer, format_hostname_label, format_output_filename, sanitize_filename


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
        == "Australia (AU) - Melbourne [UDP] [Standard] - au666.ovpn"
    )


def test_sanitize_filename_replaces_invalid_characters() -> None:
    assert sanitize_filename('bad:/\\\\name*?"<>|') == "bad-name-"


def test_format_hostname_label_trims_domain_suffix() -> None:
    assert format_hostname_label("au666.nordvpn.com") == "au666"
    assert format_hostname_label("au666") == "au666"
