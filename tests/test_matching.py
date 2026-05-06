import json
from pathlib import Path

import pytest

from nord_ovpn_picker import CliError, parse_countries, pick_city, pick_country, recommendation_to_server

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_country_alias_matching() -> None:
    countries, cities_by_country = parse_countries(load_fixture("countries.json"))
    assert pick_country("AU", countries, interactive=False).name == "Australia"
    assert pick_country("australia", countries, interactive=False).id == 13
    assert pick_city("Melb", cities_by_country[13], interactive=False, country_name="Australia").name == "Melbourne"


def test_ambiguous_country_raises_without_interactive() -> None:
    countries, _ = parse_countries(load_fixture("countries.json"))
    with pytest.raises(CliError):
        pick_country("aus", countries, interactive=False)


def test_recommendation_to_server_conversion() -> None:
    recommendation = load_fixture("recommendations.json")[0]
    server = recommendation_to_server(recommendation)
    assert server.hostname == "au666.nordvpn.com"
    assert server.city_name == "Melbourne"
    assert "legacy_standard" in server.group_identifiers
