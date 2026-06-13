"""Command-line interface: scan a URL and produce a remediation plan.

accesslens scan https://example.com
accesslens scan https://example.com --json plan.json --html report.html
accesslens scan https://example.com --mock --quiet
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from accesslens.config import Settings
from accesslens.models import EventType, RemediationPlan
from accesslens.pipeline import run_pipeline
from accesslens.report import render_html, render_json


def _run_scan(args: argparse.Namespace) -> int:
    settings = Settings(mock=args.mock, allow_local=args.allow_local)
    plan_dict: dict | None = None
    error: str | None = None

    async def drive() -> None:
        nonlocal plan_dict, error
        async for event in run_pipeline(args.url, settings):
            if not args.quiet:
                print(f"[{event.stage}] {event.message}")
            if event.type == EventType.DONE:
                plan_dict = event.payload["plan"]
            elif event.type == EventType.ERROR:
                error = event.message

    asyncio.run(drive())

    if error is not None:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if plan_dict is None:
        print("error: pipeline produced no plan", file=sys.stderr)
        return 1

    plan = RemediationPlan.model_validate(plan_dict)
    if args.json:
        Path(args.json).write_text(render_json(plan), encoding="utf-8")
        print(f"wrote {args.json}")
    if args.html:
        Path(args.html).write_text(render_html(plan), encoding="utf-8")
        print(f"wrote {args.html}")
    if args.quiet:
        print(plan.summary)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="accesslens",
        description="Scan a web page for accessibility issues and produce a "
        "cited remediation plan.",
    )
    sub = parser.add_subparsers(dest="command")

    scan = sub.add_parser("scan", help="scan a URL and produce a remediation plan")
    scan.add_argument("url", help="page URL to scan (http/https)")
    scan.add_argument(
        "--mock", action="store_true", help="replay the bundled fixture offline"
    )
    scan.add_argument(
        "--allow-local",
        action="store_true",
        help="permit scanning localhost / private hosts (SSRF guard off)",
    )
    scan.add_argument("--json", metavar="PATH", help="write the plan as JSON")
    scan.add_argument("--html", metavar="PATH", help="write a standalone HTML report")
    scan.add_argument(
        "--quiet", action="store_true", help="suppress the streaming reasoning log"
    )

    args = parser.parse_args(argv)
    if args.command == "scan":
        return _run_scan(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
