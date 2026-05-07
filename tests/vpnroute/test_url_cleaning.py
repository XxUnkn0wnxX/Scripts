from vpnroute import extract_hostname, normalize_domains, parse_input_entries


def test_extract_hostname_strips_url_parts() -> None:
    assert extract_hostname("https://example.com/path?q=1#frag") == "example.com"
    assert extract_hostname("http://www.example.com") == "www.example.com"
    assert extract_hostname("example.com/some/path") == "example.com"


def test_extract_hostname_ignores_blank_and_comment_lines() -> None:
    assert extract_hostname("   ") is None
    assert extract_hostname("# full line comment") is None


def test_extract_hostname_removes_inline_comments_and_trailing_dot() -> None:
    assert extract_hostname("Example.COM. # note") == "example.com"


def test_normalize_domains_preserves_order_and_deduplicates() -> None:
    assert normalize_domains(
        [
            "https://example.com/path",
            "example.com/path",
            "# comment",
            "ifconfig.me # inline comment",
        ]
    ) == ["example.com", "ifconfig.me"]


def test_parse_input_entries_preserves_first_source_text_for_failed_or_successful_lookup() -> None:
    entries = parse_input_entries(
        [
            "https://Example.com/path",
            "example.com/duplicate",
            "https://broken.example/path?q=1",
        ]
    )

    assert entries[0].source_text == "https://Example.com/path"
    assert entries[0].hostname == "example.com"
    assert entries[1].source_text == "https://broken.example/path?q=1"
    assert entries[1].hostname == "broken.example"
