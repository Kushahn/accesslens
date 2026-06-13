from accesslens.data import LocalRetriever, parse_wcag_tag


def test_parse_wcag_tag_three_digit():
    assert parse_wcag_tag("wcag111") == "1.1.1"


def test_parse_wcag_tag_four_digit():
    assert parse_wcag_tag("wcag1410") == "1.4.10"


def test_parse_wcag_tag_ignores_level_tags():
    assert parse_wcag_tag("wcag2a") is None
    assert parse_wcag_tag("wcag22aa") is None
    assert parse_wcag_tag("best-practice") is None


def test_local_retriever_returns_citations():
    retriever = LocalRetriever()
    refs = retriever.lookup(["wcag2a", "wcag111"])
    assert len(refs) == 1
    assert refs[0].section.startswith("1.1.1")
    assert refs[0].source_id == "wcag22"
    assert refs[0].url


def test_local_retriever_unknown_tag_returns_empty():
    retriever = LocalRetriever()
    assert retriever.lookup(["wcag999"]) == []


def test_effort_lookup_has_default():
    retriever = LocalRetriever()
    assert retriever.effort("color-contrast").value == "quick"
    assert retriever.effort("totally-unknown-rule").value == "moderate"
