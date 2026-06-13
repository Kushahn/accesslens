from pathlib import Path

import pytest

from accesslens.scanner import scan_url

FIXTURE = Path(__file__).parent / "fixtures" / "broken_page.html"


@pytest.mark.browser
async def test_scan_finds_known_violations():
    report = await scan_url(FIXTURE.as_uri(), bypass_url_guard=True)
    assert report.error is None
    rule_ids = {v.rule_id for v in report.violations}
    assert "image-alt" in rule_ids
    assert "html-has-lang" in rule_ids
    assert "label" in rule_ids
    image_alt = next(v for v in report.violations if v.rule_id == "image-alt")
    assert image_alt.nodes and image_alt.nodes[0].html


@pytest.mark.browser
async def test_scan_unreachable_url_returns_error_report():
    report = await scan_url("http://nonexistent.invalid.example", timeout_s=10)
    assert report.error is not None
    assert report.violations == []
