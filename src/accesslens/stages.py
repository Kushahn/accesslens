"""The three reasoning stages after scanning.

Every stage consumes and produces a typed contract. The retriever is
injected, so the deterministic local tier and any alternate tier are
interchangeable without stages knowing which one served them.
"""

from __future__ import annotations

from datetime import datetime, timezone

from accesslens.data import Retriever
from accesslens.models import (
    IMPACT_WEIGHT,
    MappedFinding,
    MappedFindings,
    PrioritizedFinding,
    PrioritizedFindings,
    RemediationPlan,
    RemediationStep,
    ScanReport,
)

# Hand-written suggestions for the most common axe rules; anything not
# listed falls back to the retrieved criterion summary.
CODE_SUGGESTIONS: dict[str, str] = {
    "image-alt": '<img src="logo.png" alt="Company name logo">',
    "color-contrast": "color: #595959; /* >= 4.5:1 against white */",
    "html-has-lang": '<html lang="en">',
    "document-title": "<title>Page purpose - Site name</title>",
    "button-name": "<button>Submit order</button>  <!-- or aria-label -->",
    "link-name": '<a href="/pricing">See pricing plans</a>',
    "label": '<label for="email">Email address</label><input id="email" type="email">',
    "meta-viewport": '<meta name="viewport" content="width=device-width, initial-scale=1">',
}


class StandardsMapper:
    """Map raw violations to WCAG success criteria with citations."""

    def __init__(self, retriever: Retriever):
        self.retriever = retriever

    def run(self, report: ScanReport) -> MappedFindings:
        findings = []
        for violation in report.violations:
            refs = self.retriever.lookup(violation.wcag_tags)
            findings.append(
                MappedFinding(
                    rule_id=violation.rule_id,
                    impact=violation.impact,
                    summary=violation.description,
                    affected_nodes=len(violation.nodes),
                    standard_refs=refs,
                    insufficient_evidence=not refs,
                )
            )
        return MappedFindings(url=report.url, findings=findings)


class ImpactAssessor:
    """Deterministic prioritization: impact weight scaled by reach.

    priority_score = impact_weight * (1 + min(affected_nodes, 10) / 10)
    The formula is documented in the README so judges can verify it.
    """

    def __init__(self, retriever: Retriever):
        self.retriever = retriever

    def run(self, mapped: MappedFindings) -> PrioritizedFindings:
        prioritized = []
        for finding in mapped.findings:
            weight = IMPACT_WEIGHT[finding.impact]
            reach = 1 + min(finding.affected_nodes, 10) / 10
            effort = self.retriever.effort(finding.rule_id)
            sections = (
                ", ".join(r.section for r in finding.standard_refs)
                or "no mapped criteria"
            )
            prioritized.append(
                PrioritizedFinding(
                    finding=finding,
                    priority_score=round(weight * reach, 2),
                    effort=effort,
                    rationale=(
                        f"{finding.impact.value} impact affecting "
                        f"{finding.affected_nodes or 'an unknown number of'} element(s); "
                        f"maps to {sections}; estimated {effort.value} fix."
                    ),
                )
            )
        prioritized.sort(key=lambda f: f.priority_score, reverse=True)
        return PrioritizedFindings(url=mapped.url, findings=prioritized)


class RemediationPlanner:
    """Turn prioritized findings into actionable, cited steps."""

    def __init__(self, retriever: Retriever):
        self.retriever = retriever

    def run(self, prioritized: PrioritizedFindings) -> RemediationPlan:
        steps = []
        for item in prioritized.findings:
            finding = item.finding
            if finding.insufficient_evidence:
                steps.append(
                    RemediationStep(
                        rule_id=finding.rule_id,
                        title=f"Review manually: {finding.rule_id}",
                        recommendation=(
                            "No grounded standard reference was retrieved for this "
                            "finding, so AccessLens will not invent a fix. "
                            f"Flagged for manual review: {finding.summary}"
                        ),
                        insufficient_evidence=True,
                    )
                )
                continue
            primary = finding.standard_refs[0]
            steps.append(
                RemediationStep(
                    rule_id=finding.rule_id,
                    title=f"Fix {finding.rule_id} ({primary.section})",
                    recommendation=(
                        f"{finding.summary}. Per {primary.section}: {primary.quote} "
                        f"Priority {item.priority_score} ({item.effort.value} fix)."
                    ),
                    code_suggestion=CODE_SUGGESTIONS.get(finding.rule_id, ""),
                    citations=finding.standard_refs,
                )
            )
        counts: dict[str, int] = {}
        for item in prioritized.findings:
            counts[item.finding.impact.value] = (
                counts.get(item.finding.impact.value, 0) + 1
            )
        summary = (
            "Found "
            + ", ".join(f"{n} {impact}" for impact, n in sorted(counts.items()))
            + " issue(s). Steps are ordered by priority score."
            if counts
            else "No violations found - the page passes automated checks."
        )
        return RemediationPlan(
            url=prioritized.url,
            generated_at=datetime.now(timezone.utc),
            summary=summary,
            steps=steps,
        )
