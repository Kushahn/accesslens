from datetime import datetime, timezone

import pytest

from accesslens.guardrails import GuardrailBlocked, GuardrailsPipeline, Severity
from accesslens.models import (
    AxeViolation,
    CitationRef,
    Impact,
    MappedFinding,
    MappedFindings,
    NodeSnippet,
    RemediationPlan,
    RemediationStep,
    ScanReport,
)


def make_report(**kwargs) -> ScanReport:
    defaults = dict(url="https://example.org", scanned_at=datetime.now(timezone.utc))
    defaults.update(kwargs)
    return ScanReport(**defaults)


def test_pre_scan_blocks_file_scheme():
    pipeline = GuardrailsPipeline(allow_local=False)
    with pytest.raises(GuardrailBlocked):
        pipeline.run("pre_scan", "file:///etc/passwd")


def test_pre_scan_blocks_private_host():
    pipeline = GuardrailsPipeline(allow_local=False)
    with pytest.raises(GuardrailBlocked):
        pipeline.run("pre_scan", "http://192.168.1.1/admin")
    with pytest.raises(GuardrailBlocked):
        pipeline.run("pre_scan", "http://localhost:8000")


def test_pre_scan_allows_localhost_when_configured():
    pipeline = GuardrailsPipeline(allow_local=True)
    url, results = pipeline.run("pre_scan", "http://localhost:8000")
    assert url == "http://localhost:8000"
    assert all(r.passed for r in results)


def test_post_scan_scrubs_pii_from_snippets():
    pipeline = GuardrailsPipeline()
    report = make_report(
        violations=[
            AxeViolation(
                rule_id="label",
                impact=Impact.SERIOUS,
                description="d",
                nodes=[
                    NodeSnippet(target="#x", html='<input value="bob@example.com">')
                ],
            )
        ]
    )
    scrubbed, results = pipeline.run("post_scan", report)
    assert "bob@example.com" not in scrubbed.violations[0].nodes[0].html
    assert any(r.rule == "pii_scrub" for r in results)


def test_post_scan_empty_scan_is_info_not_block():
    pipeline = GuardrailsPipeline()
    report, results = pipeline.run("post_scan", make_report(violations=[]))
    empty = [r for r in results if r.rule == "empty_scan"]
    assert empty and empty[0].severity == Severity.INFO


def test_post_map_blocks_dishonest_finding():
    pipeline = GuardrailsPipeline()
    findings = MappedFindings(
        url="https://example.org",
        findings=[
            MappedFinding(
                rule_id="x",
                impact=Impact.MINOR,
                summary="no refs but claims evidence",
                standard_refs=[],
                insufficient_evidence=False,
            )
        ],
    )
    with pytest.raises(GuardrailBlocked):
        pipeline.run("post_map", findings)


def test_post_plan_blocks_uncited_recommendation():
    pipeline = GuardrailsPipeline()
    plan = RemediationPlan(
        url="https://example.org",
        generated_at=datetime.now(timezone.utc),
        summary="s",
        steps=[RemediationStep(rule_id="x", title="t", recommendation="do things")],
    )
    with pytest.raises(GuardrailBlocked):
        pipeline.run("post_plan", plan)


def test_post_plan_passes_cited_or_honest_steps():
    pipeline = GuardrailsPipeline()
    plan = RemediationPlan(
        url="https://example.org",
        generated_at=datetime.now(timezone.utc),
        summary="s",
        steps=[
            RemediationStep(
                rule_id="a",
                title="cited",
                recommendation="fix per standard",
                citations=[CitationRef(source_id="wcag22", section="1.1.1")],
            ),
            RemediationStep(
                rule_id="b",
                title="honest",
                recommendation="needs manual review",
                insufficient_evidence=True,
            ),
        ],
    )
    checked, results = pipeline.run("post_plan", plan)
    assert checked is plan
