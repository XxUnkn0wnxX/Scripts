import pytest

from vpnroute import normalize_netmask


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("32", "255.255.255.255"),
        ("/32", "255.255.255.255"),
        ("24", "255.255.255.0"),
        ("/24", "255.255.255.0"),
        ("255.255.255.255", "255.255.255.255"),
    ],
)
def test_normalize_netmask_accepts_cidr_and_dotted_quad(value: str, expected: str) -> None:
    assert normalize_netmask(value) == expected


@pytest.mark.parametrize("value", ["", "33", "/99", "banana"])
def test_normalize_netmask_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        normalize_netmask(value)
