"""Runtime settings.

Live scanning is the default: enter a URL, AccessLens scans it. Set
``ACCESSLENS_MOCK=1`` to replay a bundled scan instead (offline demo / CI).
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _flag(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes")


@dataclass(frozen=True)
class Settings:
    mock: bool
    allow_local: bool

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            mock=_flag("ACCESSLENS_MOCK", "0"),
            allow_local=_flag("ACCESSLENS_ALLOW_LOCAL", "0"),
        )
