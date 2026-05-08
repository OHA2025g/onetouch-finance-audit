from __future__ import annotations

import hashlib
import math
from abc import ABC, abstractmethod
from typing import List


class EmbeddingProvider(ABC):
    name: str
    dim: int

    @abstractmethod
    async def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError


class HashEmbeddingProvider(EmbeddingProvider):
    """Deterministic local embedding fallback (no external keys, no heavy deps).

    Not semantically strong, but allows the platform to ship with the abstraction,
    persistence, rebuild/reindex flows, and tests. Can be replaced by a real provider later.
    """

    name = "hash-v1"
    dim = 64

    async def embed(self, texts: List[str]) -> List[List[float]]:
        out: List[List[float]] = []
        for t in texts:
            h = hashlib.sha256(t.encode("utf-8", errors="ignore")).digest()
            # Expand to dim floats in [-1, 1]
            v = []
            for i in range(self.dim):
                b = h[i % len(h)]
                v.append((b / 255.0) * 2.0 - 1.0)
            # L2 normalize
            norm = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / norm for x in v])
        return out


def cosine(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))

