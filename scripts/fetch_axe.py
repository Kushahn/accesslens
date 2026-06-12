"""Download axe-core into the package so scans work offline.

axe-core is MPL-2.0 licensed (c) Deque Systems - attribution kept in README.
"""

import urllib.request
from pathlib import Path

AXE_URL = "https://cdn.jsdelivr.net/npm/axe-core@4.10.2/axe.min.js"
DEST = (
    Path(__file__).parent.parent
    / "src"
    / "accesslens"
    / "web"
    / "static"
    / "vendor"
    / "axe.min.js"
)


def main() -> None:
    DEST.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {AXE_URL} -> {DEST}")
    urllib.request.urlretrieve(AXE_URL, DEST)
    size_kb = DEST.stat().st_size // 1024
    print(f"Done ({size_kb} KB)")


if __name__ == "__main__":
    main()
