from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from agentic.brain_vault import BrainVault


@dataclass
class MemoryCitation:
    path: str
    title: str
    preview: str
    score: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "title": self.title,
            "preview": self.preview,
            "score": self.score,
        }


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9_-]{3,}", value.lower())
        if token not in {"the", "and", "for", "with", "from", "this", "that"}
    }


class BrainMemoryRetriever:
    def __init__(self, vault: BrainVault):
        self.vault = vault

    def retrieve(
        self,
        query: str,
        *,
        specialist: str | None = None,
        limit: int = 5,
    ) -> list[MemoryCitation]:
        query_tokens = _tokens(query)
        if specialist:
            query_tokens |= _tokens(specialist)

        candidates = self.vault.search("", limit=500)
        ranked: list[MemoryCitation] = []

        for item in candidates:
            haystack = " ".join(
                [
                    str(item.get("name", "")),
                    str(item.get("path", "")),
                    str(item.get("preview", "")),
                ]
            )
            haystack_tokens = _tokens(haystack)
            score = len(query_tokens & haystack_tokens)

            path = str(item.get("path", ""))
            if specialist and specialist.lower() in path.lower():
                score += 3
            if "01-Projects/AIOS-ONE" in path:
                score += 1
            if score <= 0:
                continue

            ranked.append(
                MemoryCitation(
                    path=path,
                    title=str(item.get("name", path)),
                    preview=str(item.get("preview", "")),
                    score=score,
                )
            )

        ranked.sort(key=lambda item: (-item.score, item.path.lower()))
        return ranked[: max(1, min(limit, 20))]

    def build_context(
        self,
        query: str,
        *,
        specialist: str | None = None,
        limit: int = 5,
    ) -> dict[str, Any]:
        citations = self.retrieve(query, specialist=specialist, limit=limit)
        blocks = [
            f"[{index}] {item.title}\nPath: {item.path}\n{item.preview}"
            for index, item in enumerate(citations, start=1)
        ]
        return {
            "query": query,
            "specialist": specialist,
            "citations": [item.as_dict() for item in citations],
            "context": "\n\n".join(blocks),
        }
