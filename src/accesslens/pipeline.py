"""Pipeline orchestrator: runs the four stages with guardrails between
them and yields ``PipelineEvent`` objects for the UI's live reasoning log.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import AsyncIterator

from accesslens.config import Settings
from accesslens.data import LocalRetriever, Retriever
from accesslens.guardrails import GuardrailBlocked, GuardrailsPipeline, RuleResult
from accesslens.models import EventType, PipelineEvent, ScanReport
from accesslens.stages import ImpactAssessor, RemediationPlanner, StandardsMapper

logger = logging.getLogger(__name__)

MOCK_SCAN = Path(__file__).parent / "fixtures" / "scan_report.json"


def _guardrail_events(stage: str, results: list[RuleResult]) -> list[PipelineEvent]:
    return [
        PipelineEvent(
            stage=stage,
            type=EventType.GUARDRAIL,
            message=f"[{r.severity.value}] {r.rule}: {r.message}",
            payload={"rule": r.rule, "severity": r.severity.value, "passed": r.passed},
        )
        for r in results
    ]


def _get_retriever() -> Retriever:
    # The bundled WCAG 2.2 knowledge base grounds every finding. Alternate
    # tiers (a hosted LLM, a vector store) can plug in here by implementing
    # the Retriever protocol — no stage or pipeline change required.
    return LocalRetriever()


async def _scan(url: str, settings: Settings) -> ScanReport:
    if settings.mock:
        return ScanReport.model_validate_json(MOCK_SCAN.read_text(encoding="utf-8"))
    from accesslens.scanner import scan_url

    return await scan_url(url)


async def run_pipeline(url: str, settings: Settings) -> AsyncIterator[PipelineEvent]:
    guardrails = GuardrailsPipeline(allow_local=settings.allow_local)
    retriever = _get_retriever()
    try:
        # Stage 1: Scanner
        yield PipelineEvent(
            stage="scanner", type=EventType.STAGE_START, message=f"Scanning {url}"
        )
        url, results = guardrails.run("pre_scan", url)
        for event in _guardrail_events("scanner", results):
            yield event
        yield PipelineEvent(
            stage="scanner",
            type=EventType.TOOL_CALL,
            message="Running axe-core via Playwright",
        )
        report = await _scan(url, settings)
        report, results = guardrails.run("post_scan", report)
        for event in _guardrail_events("scanner", results):
            yield event
        yield PipelineEvent(
            stage="scanner",
            type=EventType.STAGE_RESULT,
            message=f"Found {len(report.violations)} violation(s) on '{report.page_title or url}'",
        )

        # Stage 2: StandardsMapper
        yield PipelineEvent(
            stage="standards_mapper",
            type=EventType.STAGE_START,
            message="Mapping violations to standards",
        )
        yield PipelineEvent(
            stage="standards_mapper",
            type=EventType.RETRIEVAL,
            message="Retrieving criteria from the WCAG 2.2 knowledge base",
        )
        mapped = StandardsMapper(retriever).run(report)
        mapped, results = guardrails.run("post_map", mapped)
        for event in _guardrail_events("standards_mapper", results):
            yield event
        cited = sum(1 for f in mapped.findings if f.standard_refs)
        yield PipelineEvent(
            stage="standards_mapper",
            type=EventType.STAGE_RESULT,
            message=f"Mapped {cited}/{len(mapped.findings)} finding(s) to cited criteria",
        )

        # Stage 3: ImpactAssessor
        yield PipelineEvent(
            stage="impact_assessor",
            type=EventType.STAGE_START,
            message="Scoring impact and effort",
        )
        prioritized = ImpactAssessor(retriever).run(mapped)
        top = (
            prioritized.findings[0].finding.rule_id if prioritized.findings else "none"
        )
        yield PipelineEvent(
            stage="impact_assessor",
            type=EventType.STAGE_RESULT,
            message=f"Prioritized {len(prioritized.findings)} finding(s); top priority: {top}",
        )

        # Stage 4: RemediationPlanner
        yield PipelineEvent(
            stage="remediation_planner",
            type=EventType.STAGE_START,
            message="Drafting cited remediation plan",
        )
        plan = RemediationPlanner(retriever).run(prioritized)
        plan, results = guardrails.run("post_plan", plan)
        for event in _guardrail_events("remediation_planner", results):
            yield event
        yield PipelineEvent(
            stage="remediation_planner",
            type=EventType.DONE,
            message=plan.summary,
            payload={"plan": json.loads(plan.model_dump_json())},
        )
    except GuardrailBlocked as blocked:
        yield PipelineEvent(
            stage="guardrails",
            type=EventType.ERROR,
            message=blocked.result.message,
            payload={"rule": blocked.result.rule},
        )
    except Exception as exc:  # noqa: BLE001 - last-resort boundary for the SSE stream
        logger.exception("Pipeline failed")
        yield PipelineEvent(
            stage="pipeline", type=EventType.ERROR, message=f"Unexpected failure: {exc}"
        )
