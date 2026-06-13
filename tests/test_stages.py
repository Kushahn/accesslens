from datetime import datetime, timezone

from accesslens.data import LocalRetriever
from accesslens.models import (
    AxeViolation,
    Impact,
    NodeSnippet,
    ScanReport,
)
from accesslens.stages import ImpactAssessor, RemediationPlanner, StandardsMapper


def make_report() -> ScanReport:
    return ScanReport(
        url="https://example.org",
        scanned_at=datetime.now(timezone.utc),
        violations=[
            AxeViolation(
                rule_id="image-alt",
                impact=Impact.CRITICAL,
                description="Images must have alternate text",
                wcag_tags=["wcag2a", "wcag111"],
                nodes=[NodeSnippet(target="img", html="<img src='x.png'>")],
            ),
            AxeViolation(
                rule_id="some-exotic-rule",
                impact=Impact.MINOR,
                description="No WCAG tag on this one",
                wcag_tags=[],
            ),
        ],
    )


def test_mapper_attaches_citations_and_flags_gaps():
    mapped = StandardsMapper(LocalRetriever()).run(make_report())
    by_rule = {f.rule_id: f for f in mapped.findings}
    assert by_rule["image-alt"].standard_refs[0].section.startswith("1.1.1")
    assert by_rule["image-alt"].insufficient_evidence is False
    assert by_rule["some-exotic-rule"].standard_refs == []
    assert by_rule["some-exotic-rule"].insufficient_evidence is True


def test_assessor_orders_by_priority_and_explains():
    mapped = StandardsMapper(LocalRetriever()).run(make_report())
    prioritized = ImpactAssessor(LocalRetriever()).run(mapped)
    scores = [f.priority_score for f in prioritized.findings]
    assert scores == sorted(scores, reverse=True)
    assert prioritized.findings[0].finding.rule_id == "image-alt"
    assert "critical" in prioritized.findings[0].rationale.lower()


def test_planner_emits_cited_or_honest_steps():
    mapped = StandardsMapper(LocalRetriever()).run(make_report())
    prioritized = ImpactAssessor(LocalRetriever()).run(mapped)
    plan = RemediationPlanner(LocalRetriever()).run(prioritized)
    assert plan.summary
    by_rule = {s.rule_id: s for s in plan.steps}
    assert by_rule["image-alt"].citations
    assert by_rule["image-alt"].code_suggestion
    assert by_rule["some-exotic-rule"].insufficient_evidence is True
