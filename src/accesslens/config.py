"""Runtime settings. Mock mode is the default so judges need zero credentials."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _flag(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes")


@dataclass(frozen=True)
class Settings:
    mock: bool
    allow_local: bool
    foundry_endpoint: str
    foundry_model: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            mock=_flag("ACCESSLENS_MOCK", "1"),
            allow_local=_flag("ACCESSLENS_ALLOW_LOCAL", "0"),
            foundry_endpoint=os.getenv("FOUNDRY_PROJECT_ENDPOINT", ""),
            foundry_model=os.getenv("FOUNDRY_MODEL", "gpt-4o-mini"),
        )
