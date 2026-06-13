import json
from datetime import datetime, timezone

from accesslens.models import CitationRef, RemediationPlan, RemediationStep
from accesslens.report import render_html, render_json


def make_plan() -> RemediationPlan:
    return RemediationPlan(
        url="https://example.org",
        generated_at=datetime.now(timezone.utc),
        summary="Found 1 critical, 1 minor issue(s).",
        steps=[
            RemediationStep(
                rule_id="image-alt",
                title="Fix image-alt (1.1.1 Non-text Content)",
                recommendation="Provide a text alternative for every informative image.",
                code_suggestion='<img src="logo.png" alt="Company logo">',
                citations=[
                    CitationRef(
                        source_id="wcag22",
                        section="1.1.1 Non-text Content (Level A)",
                        url="https://www.w3.org/WAI/WCAG22/Understanding/non-text-content.html",
                    )
                ],
            ),
            RemediationStep(
                rule_id="region",
                title="Review manually: region",
                recommendation="No grounded standard reference; flagged for manual review.",
                insufficient_evidence=True,
            ),
        ],
    )


def test_render_json_roundtrips():
    data = json.loads(render_json(make_plan()))
    assert data["summary"].startswith("Found 1 critical")
    assert data["steps"][0]["rule_id"] == "image-alt"
    assert data["steps"][0]["citations"][0]["section"].startswith("1.1.1")


def test_render_html_is_self_contained_and_shows_content():
    out = render_html(make_plan())
    assert "<!DOCTYPE html>" in out
    assert '<html lang="en">' in out
    assert "Found 1 critical" in out
    assert "1.1.1 Non-text Content (Level A)" in out
    assert "Review manually: region" in out
    # standalone: no external scripts/styles
    assert "<script" not in out.lower()
    assert 'http-equiv="Content-Security-Policy"' in out


def test_render_html_escapes_dynamic_content():
    plan = RemediationPlan(
        url="https://example.org",
        generated_at=datetime.now(timezone.utc),
        summary="x",
        steps=[
            RemediationStep(
                rule_id="x",
                title="<script>alert(1)</script>",
                recommendation="<img src=x onerror=alert(2)>",
                code_suggestion="<b>not bold</b>",
                citations=[
                    CitationRef(source_id="s", section="S", url="javascript:alert(3)")
                ],
            )
        ],
    )
    out = render_html(plan)
    # raw injected markup must not appear unescaped
    assert "<script>alert(1)</script>" not in out
    assert "onerror=alert(2)" not in out or "&lt;img" in out
    # javascript: scheme must be neutralised in hrefs
    assert 'href="javascript:alert(3)"' not in out
