from datetime import datetime, timezone

from accesslens.models import (
    IMPACT_WEIGHT,
    AxeViolation,
    CitationRef,
    Impact,
    MappedFinding,
    PipelineEvent,
    EventType,
    RemediationPlan,
    RemediationStep,
    ScanReport,
)


def test_impact_weights_are_ordered():
    assert (
        IMPACT_WEIGHT[Impact.MINOR]
        < IMPACT_WEIGHT[Impact.MODERATE]
        < IMPACT_WEIGHT[Impact.SERIOUS]
        < IMPACT_WEIGHT[Impact.CRITICAL]
    )


def test_scan_report_roundtrip():
    report = ScanReport(
        url="https://example.org",
        scanned_at=datetime.now(timezone.utc),
        violations=[
            AxeViolation(
                rule_id="image-alt",
                impact=Impact.CRITICAL,
                description="Images must have alternate text",
                help_url="https://dequeuniversity.com/rules/axe/4.10/image-alt",
                wcag_tags=["wcag2a", "wcag111"],
            )
        ],
    )
    restored = ScanReport.model_validate_json(report.model_dump_json())
    assert restored.violations[0].rule_id == "image-alt"


def test_mapped_finding_defaults_to_evidence_present():
    finding = MappedFinding(
        rule_id="image-alt", impact=Impact.CRITICAL, summary="Missing alt text"
    )
    assert finding.insufficient_evidence is False
    assert finding.standard_refs == []


def test_remediation_plan_holds_cited_steps():
    plan = RemediationPlan(
        url="https://example.org",
        generated_at=datetime.now(timezone.utc),
        summary="1 critical issue",
        steps=[
            RemediationStep(
                rule_id="image-alt",
                title="Add alt text",
                recommendation="Provide a text alternative for every informative image.",
                citations=[
                    CitationRef(source_id="wcag22", section="1.1.1 Non-text Content")
                ],
            )
        ],
    )
    assert plan.steps[0].citations[0].section.startswith("1.1.1")


def test_pipeline_event_serializes_for_sse():
    event = PipelineEvent(
        stage="scanner", type=EventType.STAGE_START, message="Scanning"
    )
    data = event.model_dump_json()
    assert '"scanner"' in data and '"stage_start"' in data
