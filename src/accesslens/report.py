"""Export a RemediationPlan as shareable artifacts: JSON or a standalone,
self-contained HTML report.

The HTML report renders agent-produced text, so every dynamic value is
HTML-escaped and every citation link is validated to http(s) — the static
report must never become an XSS vector when opened or shared.
"""

from __future__ import annotations

import html
import urllib.parse

from accesslens.models import RemediationPlan

_REPORT_CSS = """
  body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
         color: #1a1a2e; max-width: 60rem; margin: 0 auto; padding: 1.5rem;
         line-height: 1.55; }
  h1 { margin-bottom: .2rem; }
  .meta { color: #3a3a4a; }
  .summary { font-weight: 600; }
  a { color: #0b5394; }
  ol { list-style: none; padding: 0; }
  li { border: 1px solid #c9d1dc; border-radius: 6px; padding: .8rem 1rem;
       margin: .6rem 0; }
  li h2 { font-size: 1.05rem; margin: 0 0 .4rem; }
  .badge { font-size: .8rem; font-weight: 700; color: #8a5a00;
           border: 1px solid #8a5a00; border-radius: 4px; padding: 0 .35rem;
           margin-left: .4rem; }
  pre { background: #f5f7fa; border-radius: 4px; padding: .6rem;
        overflow-x: auto; }
"""


def render_json(plan: RemediationPlan) -> str:
    """Serialize the plan to indented JSON."""
    return plan.model_dump_json(indent=2)


def _safe_href(url: str) -> str:
    """Return ``url`` only if it is an http(s) link, else ``#``."""
    try:
        if urllib.parse.urlparse(url).scheme in ("http", "https"):
            return url
    except ValueError:
        pass
    return "#"


def _esc(value: str) -> str:
    return html.escape(value, quote=True)


def render_html(plan: RemediationPlan) -> str:
    """Render the plan as a self-contained, accessible HTML report."""
    steps_html: list[str] = []
    for step in plan.steps:
        parts = ["<li>"]
        badge = (
            ' <span class="badge">manual review</span>'
            if step.insufficient_evidence
            else ""
        )
        parts.append(f"<h2>{_esc(step.title)}{badge}</h2>")
        parts.append(f"<p>{_esc(step.recommendation)}</p>")
        if step.code_suggestion:
            parts.append(f"<pre><code>{_esc(step.code_suggestion)}</code></pre>")
        if step.citations:
            links = "; ".join(
                f'<a href="{_esc(_safe_href(c.url))}" rel="noopener noreferrer" '
                f'target="_blank">{_esc(c.section)}</a>'
                for c in step.citations
            )
            parts.append(f"<p>Sources: {links}</p>")
        parts.append("</li>")
        steps_html.append("".join(parts))

    scanned_link = f'<a href="{_esc(_safe_href(plan.url))}">{_esc(plan.url)}</a>'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy"
      content="default-src 'none'; style-src 'unsafe-inline'; img-src data:">
<title>AccessLens report — {_esc(plan.url)}</title>
<style>{_REPORT_CSS}</style>
</head>
<body>
<main>
<h1>AccessLens remediation report</h1>
<p class="meta">Scanned: {scanned_link}</p>
<p class="meta">Generated: {_esc(plan.generated_at.isoformat())}</p>
<p class="summary">{_esc(plan.summary)}</p>
<ol>
{chr(10).join(steps_html)}
</ol>
</main>
</body>
</html>
"""
