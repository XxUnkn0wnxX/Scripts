from pathlib import Path

import pytest

import nord_ovpn_picker as picker
from nord_ovpn_picker import CandidateScore, CliError, NordServer, download_selected_candidates, parse_args


def make_candidate(hostname: str) -> CandidateScore:
    return CandidateScore(
        server=NordServer(
            hostname=hostname,
            name=hostname,
            load=10,
            station="127.0.0.1",
            country_name="Australia",
            country_code="AU",
            country_id=13,
            city_name="Melbourne",
            city_id=1001,
            group_identifiers=["legacy_standard"],
            technology_identifiers=["openvpn_udp"],
            status="online",
        ),
        protocol="udp",
        group="standard",
        average_ping_ms=20.0,
        score=40.0,
    )


@pytest.mark.parametrize(
    "argv",
    [
        ["--limit", "0"],
        ["--limit", "-1"],
        ["--download-top", "0"],
        ["--download-top", "-1"],
        ["--ping-count", "0"],
        ["--ping-count", "-1"],
    ],
)
def test_parse_args_rejects_non_positive_numeric_values(argv: list[str]) -> None:
    with pytest.raises(SystemExit):
        parse_args(argv)


def test_download_selected_candidates_continues_after_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[str] = []

    def fake_download_candidate(**kwargs) -> Path:
        hostname = kwargs["candidate"].server.hostname
        calls.append(hostname)
        if hostname == "au001.nordvpn.com":
            raise CliError("first failed")
        return tmp_path / f"{hostname}.ovpn"

    monkeypatch.setattr(picker, "download_candidate", fake_download_candidate)

    downloaded, errors = download_selected_candidates(
        client=None,  # type: ignore[arg-type]
        candidates=[make_candidate("au001.nordvpn.com"), make_candidate("au002.nordvpn.com")],
        selected_indexes=[0, 1],
        output_dir=tmp_path,
        force=False,
        dry_run=True,
    )

    assert calls == ["au001.nordvpn.com", "au002.nordvpn.com"]
    assert downloaded == [tmp_path / "au002.nordvpn.com.ovpn"]
    assert errors == ["first failed"]
