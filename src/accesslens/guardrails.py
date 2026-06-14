"""Guardrails pipeline: named rules enforced at every stage boundary.

Severities: BLOCK halts the pipeline with a user-readable reason,
WARN transforms or annotates and continues, INFO is purely informational.
"""

from __future__ import annotations

import ipaddress
import re
import socket
import urllib.parse
from enum import Enum
from typing import Any, Callable

from pydantic import BaseModel

from accesslens.models import MappedFindings, RemediationPlan, ScanReport

MAX_VIOLATIONS = 200
MAX_TEXT_LEN = 2000
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
PRIVATE_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


class Severity(str, Enum):
    BLOCK = "block"
    WARN = "warn"
    INFO = "info"


class RuleResult(BaseModel):
    rule: str
    severity: Severity
    passed: bool
    message: str = ""


class GuardrailBlocked(Exception):
    def __init__(self, result: RuleResult):
        self.result = result
        super().__init__(f"[{result.rule}] {result.message}")


Rule = Callable[[Any], tuple[Any, RuleResult]]


IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


def _ip_is_blocked(ip: IPAddress) -> bool:
    """True for any non-public address an SSRF attacker might target."""
    # ::ffff:a.b.c.d routes to the embedded IPv4 but only got flagged by the
    # IPv6 ruleset from CPython 3.12.4 on (CVE-2024-4032); unwrap it ourselves
    # so the guard holds on every interpreter satisfying requires-python.
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        return _ip_is_blocked(mapped)
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local  # 169.254/16 (incl. cloud metadata), fe80::/10
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _candidate_ips(host: str) -> list[IPAddress]:
    """Every IP the host might reach: a literal address, browser-accepted
    numeric encodings (decimal/hex/octal/short, e.g. ``2130706433``,
    ``0x7f000001``, ``127.1``), and DNS A/AAAA records. Resolving here is what
    catches a public hostname deliberately pointed at a private IP.
    """
    try:  # already a literal address, e.g. 127.0.0.1 or ::1
        return [ipaddress.ip_address(host)]
    except ValueError:
        pass

    try:  # browser-accepted numeric forms: 2130706433, 0x7f000001, 127.1
        return [ipaddress.IPv4Address(socket.inet_aton(host))]
    except (OSError, ValueError):
        pass

    ips: list[IPAddress] = []  # a real hostname: check every DNS answer
    try:
        for info in socket.getaddrinfo(host, None):
            addr = info[4][0].split("%")[0]  # drop any IPv6 scope id
            try:
                ips.append(ipaddress.ip_address(addr))
            except ValueError:
                pass
    except OSError:
        pass
    return ips


def _is_private_host(host: str) -> bool:
    if host.lower() in PRIVATE_HOSTS:
        return True
    return any(_ip_is_blocked(ip) for ip in _candidate_ips(host))


def url_scheme_rule(url: str) -> tuple[str, RuleResult]:
    scheme = urllib.parse.urlparse(url).scheme
    ok = scheme in ("http", "https")
    return url, RuleResult(
        rule="url_scheme",
        severity=Severity.BLOCK,
        passed=ok,
        message="OK"
        if ok
        else f"Only http/https URLs can be scanned (got '{scheme or 'none'}').",
    )


def make_private_host_rule(allow_local: bool) -> Rule:
    def private_host_rule(url: str) -> tuple[str, RuleResult]:
        host = urllib.parse.urlparse(url).hostname or ""
        private = False if allow_local else _is_private_host(host)
        ok = allow_local or not private
        return url, RuleResult(
            rule="private_host",
            severity=Severity.BLOCK,
            passed=ok,
            message="OK"
            if ok
            else "Scanning private or local hosts is disabled (SSRF guard).",
        )

    return private_host_rule


def pii_scrub_rule(report: ScanReport) -> tuple[ScanReport, RuleResult]:
    scrubbed = 0
    for violation in report.violations:
        for node in violation.nodes:
            cleaned = EMAIL_RE.sub("[email]", node.html)
            cleaned = PHONE_RE.sub("[phone]", cleaned)
            if cleaned != node.html:
                node.html = cleaned
                scrubbed += 1
    return report, RuleResult(
        rule="pii_scrub",
        severity=Severity.WARN,
        passed=True,
        message=f"Scrubbed PII from {scrubbed} snippet(s)."
        if scrubbed
        else "No PII found.",
    )


def scan_size_rule(report: ScanReport) -> tuple[ScanReport, RuleResult]:
    truncated = len(report.violations) > MAX_VIOLATIONS
    if truncated:
        report.violations = report.violations[:MAX_VIOLATIONS]
    return report, RuleResult(
        rule="scan_size",
        severity=Severity.WARN,
        passed=True,
        message=f"Truncated to {MAX_VIOLATIONS} violations."
        if truncated
        else "Within size limits.",
    )


def empty_scan_rule(report: ScanReport) -> tuple[ScanReport, RuleResult]:
    empty = not report.violations and report.error is None
    return report, RuleResult(
        rule="empty_scan",
        severity=Severity.INFO,
        passed=True,
        message="No violations detected - the page passes automated checks."
        if empty
        else "Violations present.",
    )


def scan_error_rule(report: ScanReport) -> tuple[ScanReport, RuleResult]:
    ok = report.error is None
    return report, RuleResult(
        rule="scan_error",
        severity=Severity.BLOCK,
        passed=ok,
        message="OK" if ok else f"Scan failed: {report.error}",
    )


def evidence_honesty_rule(
    findings: MappedFindings,
) -> tuple[MappedFindings, RuleResult]:
    dishonest = [
        f.rule_id
        for f in findings.findings
        if not f.standard_refs and not f.insufficient_evidence
    ]
    ok = not dishonest
    return findings, RuleResult(
        rule="evidence_honesty",
        severity=Severity.BLOCK,
        passed=ok,
        message="OK"
        if ok
        else f"Findings without evidence must be flagged: {dishonest}",
    )


def citation_required_rule(plan: RemediationPlan) -> tuple[RemediationPlan, RuleResult]:
    uncited = [
        s.rule_id for s in plan.steps if not s.citations and not s.insufficient_evidence
    ]
    ok = not uncited
    return plan, RuleResult(
        rule="citation_required",
        severity=Severity.BLOCK,
        passed=ok,
        message="OK"
        if ok
        else f"Recommendations without citations are not allowed: {uncited}",
    )


def output_length_rule(plan: RemediationPlan) -> tuple[RemediationPlan, RuleResult]:
    clipped = 0
    for step in plan.steps:
        if len(step.recommendation) > MAX_TEXT_LEN:
            step.recommendation = step.recommendation[:MAX_TEXT_LEN] + "..."
            clipped += 1
    return plan, RuleResult(
        rule="output_length",
        severity=Severity.WARN,
        passed=True,
        message=f"Clipped {clipped} overlong step(s)." if clipped else "Lengths OK.",
    )


def plan_completeness_rule(plan: RemediationPlan) -> tuple[RemediationPlan, RuleResult]:
    ok = bool(plan.summary)
    return plan, RuleResult(
        rule="plan_completeness",
        severity=Severity.BLOCK,
        passed=ok,
        message="OK" if ok else "Plan must include a summary.",
    )


class GuardrailsPipeline:
    """Runs the registered rules for a named boundary, in order."""

    def __init__(self, allow_local: bool = False):
        self.boundaries: dict[str, list[Rule]] = {
            "pre_scan": [url_scheme_rule, make_private_host_rule(allow_local)],
            "post_scan": [
                scan_error_rule,
                pii_scrub_rule,
                scan_size_rule,
                empty_scan_rule,
            ],
            "post_map": [evidence_honesty_rule],
            "post_plan": [
                plan_completeness_rule,
                citation_required_rule,
                output_length_rule,
            ],
        }

    def run(self, boundary: str, payload: Any) -> tuple[Any, list[RuleResult]]:
        results: list[RuleResult] = []
        for rule in self.boundaries[boundary]:
            payload, result = rule(payload)
            results.append(result)
            if result.severity == Severity.BLOCK and not result.passed:
                raise GuardrailBlocked(result)
        return payload, results
