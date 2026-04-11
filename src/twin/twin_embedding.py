"""
Tier 4 — Twin Embedding Utilities

  - Cosine similarity between two financial DNA vectors
  - Cohort clustering: bucket users by DNA distance into persona groups
  - Nearest-neighbour lookup for peer benchmarking (in-memory, offline use)
"""

from __future__ import annotations

import math
from typing import Optional


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Return cosine similarity ∈ [-1, 1] between two equal-length vectors."""
    if len(a) != len(b):
        raise ValueError(f"DNA dim mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a < 1e-9 or norm_b < 1e-9:
        return 0.0
    return dot / (norm_a * norm_b)


def euclidean_distance(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


class DNACohortIndex:
    """
    In-memory index of DNA vectors for fast nearest-neighbour lookup.
    Used during offline batch twin bootstrap and peer benchmarking.
    """

    def __init__(self) -> None:
        self._entries: list[tuple[str, list[float]]] = []  # (user_id, dna)

    def add(self, user_id: str, dna: list[float]) -> None:
        self._entries.append((user_id, dna))

    def nearest(
        self,
        query: list[float],
        k: int = 5,
        exclude: Optional[str] = None,
    ) -> list[tuple[str, float]]:
        """
        Return top-k (user_id, similarity) neighbours by cosine similarity.
        Excludes `exclude` user_id if set (so you don't match yourself).
        """
        scored = []
        for uid, dna in self._entries:
            if uid == exclude:
                continue
            sim = cosine_similarity(query, dna)
            scored.append((uid, sim))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]

    def __len__(self) -> int:
        return len(self._entries)
