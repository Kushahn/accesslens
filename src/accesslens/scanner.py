"""Website scanning: Playwright loads the page, injected axe-core finds violations.

This is the agent's function tool in live mode and the pipeline's first
stage in every mode. Failures never raise - they come back as a
``ScanReport`` with ``error`` set, so the agent can explain them.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright

from accesslens.models import AxeViolation, Impact, NodeSnippet, ScanReport

logger = logging.getLogger(__name__)

AXE_PATH = Path(__file__).parent / "web" / "static" / "vendor" / "axe.min.js"
MAX_NODES_PER_VIOLATION = 5


def _to_violation(raw: dict) -> AxeViolation:
    return AxeViolation(
        rule_id=raw["id"],
        impact=Impact(raw.get("impact") or "moderate"),
        description=raw.get("description", ""),
        help_url=raw.get("helpUrl", ""),
        wcag_tags=[t for t in raw.get("tags", []) if t.startswith("wcag")],
        nodes=[
            NodeSnippet(
                target=", ".join(map(str, n.get("target", []))), html=n.get("html", "")
            )
            for n in raw.get("nodes", [])[:MAX_NODES_PER_VIOLATION]
        ],
    )


async def scan_url(
    url: str, timeout_s: int = 30, bypass_url_guard: bool = False
) -> ScanReport:
    """Scan ``url`` with axe-core and return a structured report.

    ``bypass_url_guard`` exists only for tests that scan file:// fixtures;
    production callers go through the guardrails pipeline first.
    """
    started = time.monotonic()
    scanned_at = datetime.now(timezone.utc)
    if not bypass_url_guard and not url.startswith(("http://", "https://")):
        return ScanReport(url=url, scanned_at=scanned_at, error="URL must be http(s).")
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                # Wait for full load (not just DOM): accessibility checks like
                # color-contrast need computed styles, so axe must run against
                # the fully rendered page, not a half-laid-out one.
                await page.goto(url, timeout=timeout_s * 1000, wait_until="load")
                await page.add_script_tag(path=str(AXE_PATH))
                results = await page.evaluate("async () => await axe.run()")
                title = await page.title()
            finally:
                await browser.close()
        return ScanReport(
            url=url,
            page_title=title,
            scanned_at=scanned_at,
            duration_ms=int((time.monotonic() - started) * 1000),
            violations=[_to_violation(v) for v in results.get("violations", [])],
        )
    except Exception as exc:  # noqa: BLE001 - tool boundary: report, never crash
        logger.warning("Scan failed for %s: %s", url, exc)
        return ScanReport(
            url=url,
            scanned_at=scanned_at,
            duration_ms=int((time.monotonic() - started) * 1000),
            error=f"{type(exc).__name__}: {exc}",
        )
