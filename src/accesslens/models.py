"""Typed contracts for every pipeline boundary.

Each stage consumes exactly one of these models and produces exactly one,
so handoffs are schema-validated and the reasoning chain is observable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class Impact(str, Enum):
    MINOR = "minor"
    MODERATE = "moderate"
    SERIOUS = "serious"
    CRITICAL = "critical"


IMPACT_WEIGHT: dict[Impact, int] = {
    Impact.MINOR: 1,
    Impact.MODERATE: 2,
    Impact.SERIOUS: 3,
    Impact.CRITICAL: 4,
}


class NodeSnippet(BaseModel):
    target: str
    html: str


class AxeViolation(BaseModel):
    rule_id: str
    impact: Impact
    description: str
    help_url: str = ""
    wcag_tags: list[str] = Field(default_factory=list)
    nodes: list[NodeSnippet] = Field(default_factory=list)


class ScanReport(BaseModel):
    url: str
    page_title: str = ""
    scanned_at: datetime
    duration_ms: int = 0
    violations: list[AxeViolation] = Field(default_factory=list)
    error: str | None = None


class CitationRef(BaseModel):
    source_id: str
    section: str
    url: str = ""
    quote: str = ""


class MappedFinding(BaseModel):
    rule_id: str
    impact: Impact
    summary: str
    affected_nodes: int = 0
    standard_refs: list[CitationRef] = Field(default_factory=list)
    insufficient_evidence: bool = False


class MappedFindings(BaseModel):
    url: str
    findings: list[MappedFinding] = Field(default_factory=list)


class Effort(str, Enum):
    QUICK = "quick"
    MODERATE = "moderate"
    INVOLVED = "involved"


class PrioritizedFinding(BaseModel):
    finding: MappedFinding
    priority_score: float
    effort: Effort
    rationale: str


class PrioritizedFindings(BaseModel):
    url: str
    findings: list[PrioritizedFinding] = Field(default_factory=list)


class RemediationStep(BaseModel):
    rule_id: str
    title: str
    recommendation: str
    code_suggestion: str = ""
    citations: list[CitationRef] = Field(default_factory=list)
    insufficient_evidence: bool = False


class RemediationPlan(BaseModel):
    url: str
    generated_at: datetime
    summary: str
    steps: list[RemediationStep] = Field(default_factory=list)


class EventType(str, Enum):
    STAGE_START = "stage_start"
    TOOL_CALL = "tool_call"
    RETRIEVAL = "retrieval"
    GUARDRAIL = "guardrail"
    STAGE_RESULT = "stage_result"
    ERROR = "error"
    DONE = "done"


class PipelineEvent(BaseModel):
    stage: str
    type: EventType
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict = Field(default_factory=dict)
