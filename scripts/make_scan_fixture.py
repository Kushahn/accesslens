"""Record a real scan of the broken fixture page as the mock-mode ScanReport."""

import asyncio
from pathlib import Path

from accesslens.scanner import scan_url

ROOT = Path(__file__).parent.parent
FIXTURE_PAGE = ROOT / "tests" / "fixtures" / "broken_page.html"
DEST = ROOT / "src" / "accesslens" / "fixtures" / "scan_report.json"


async def main() -> None:
    report = await scan_url(FIXTURE_PAGE.as_uri(), bypass_url_guard=True)
    if report.error:
        raise SystemExit(f"Fixture scan failed: {report.error}")
    # Present the fixture as the bundled demo page, not a local file path.
    report.url = "https://demo.accesslens.example/broken-page"
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    print(f"Wrote {DEST} with {len(report.violations)} violations")


if __name__ == "__main__":
    asyncio.run(main())
