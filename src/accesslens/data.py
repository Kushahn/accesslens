"""Local standards knowledge: the deterministic retrieval tier.

This is the default knowledge base. Any alternate tier (a hosted LLM, a
vector store) implements the same ``Retriever`` protocol, so the stages
never know which tier served them.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from accesslens.models import CitationRef, Effort

DATA_DIR = Path(__file__).parent / "data"
WCAG_TAG_RE = re.compile(r"^wcag(\d)(\d)(\d+)$")


def parse_wcag_tag(tag: str) -> str | None:
    """Convert an axe-core tag like ``wcag111`` to an SC number like ``1.1.1``.

    Level tags (``wcag2a``, ``wcag22aa``) and non-WCAG tags return None.
    """
    match = WCAG_TAG_RE.match(tag)
    if match is None:
        return None
    principle, guideline, criterion = match.groups()
    return f"{principle}.{guideline}.{criterion}"


@lru_cache(maxsize=1)
def _load_criteria() -> dict[str, dict]:
    return json.loads((DATA_DIR / "wcag_criteria.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _load_efforts() -> dict[str, str]:
    return json.loads((DATA_DIR / "rule_effort.json").read_text(encoding="utf-8"))


class Retriever(Protocol):
    """Interface shared by the local tier and any alternate tier."""

    def lookup(self, wcag_tags: list[str]) -> list[CitationRef]: ...

    def effort(self, rule_id: str) -> Effort: ...


class LocalRetriever:
    """Deterministic lookup against bundled WCAG 2.2 criteria data."""

    def lookup(self, wcag_tags: list[str]) -> list[CitationRef]:
        criteria = _load_criteria()
        refs: list[CitationRef] = []
        for tag in wcag_tags:
            sc_number = parse_wcag_tag(tag)
            if sc_number is None or sc_number not in criteria:
                continue
            entry = criteria[sc_number]
            refs.append(
                CitationRef(
                    source_id="wcag22",
                    section=f"{sc_number} {entry['name']} (Level {entry['level']})",
                    url=entry["url"],
                    quote=entry["summary"],
                )
            )
        return refs

    def effort(self, rule_id: str) -> Effort:
        efforts = _load_efforts()
        return Effort(efforts.get(rule_id, efforts["_default"]))
