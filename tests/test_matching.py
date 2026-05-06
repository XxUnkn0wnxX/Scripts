import json
from pathlib import Path

import pytest

from nord_ovpn_picker import CliError, Country, parse_countries, pick_city, pick_country, recommendation_to_server

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_country_alias_matching() -> None:
    countries, cities_by_country = parse_countries(load_fixture("countries.json"))
    assert pick_country("AU", countries, interactive=False).name == "Australia"
    assert pick_country("australia", countries, interactive=False).id == 13
    assert pick_city("Melb", cities_by_country[13], interactive=False, country_name="Australia").name == "Melbourne"


def test_fixture_country_names_and_codes_resolve() -> None:
    countries, _ = parse_countries(load_fixture("countries.json"))
    for country in countries:
        assert pick_country(country.name, countries, interactive=False).id == country.id
        assert pick_country(country.code or country.name, countries, interactive=False).id == country.id


def test_fixture_city_names_resolve() -> None:
    countries, cities_by_country = parse_countries(load_fixture("countries.json"))
    for country in countries:
        for city in cities_by_country[country.id]:
            assert pick_city(city.name, cities_by_country[country.id], interactive=False, country_name=country.name).id == city.id


def test_common_country_synonyms_resolve() -> None:
    countries = [
        Country(id=225, name="United States", code="US"),
        Country(id=227, name="United Kingdom", code="GB"),
        Country(id=228, name="United Arab Emirates", code="AE"),
    ]

    assert pick_country("USA", countries, interactive=False).name == "United States"
    assert pick_country("America", countries, interactive=False).name == "United States"
    assert pick_country("United States of America", countries, interactive=False).name == "United States"
    assert pick_country("UK", countries, interactive=False).name == "United Kingdom"
    assert pick_country("UAE", countries, interactive=False).name == "United Arab Emirates"


def test_exact_country_code_wins_over_name_initials() -> None:
    countries = [
        Country(id=18, name="Bangladesh", code="BD"),
        Country(id=34, name="Brunei Darussalam", code="BN"),
    ]

    assert pick_country("BD", countries, interactive=False).name == "Bangladesh"
    assert pick_country("BN", countries, interactive=False).name == "Brunei Darussalam"


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
