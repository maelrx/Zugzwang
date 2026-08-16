"""Deterministic seed derivation (design §10.7).

Seeds are derived from ``run_seed + condition_index + episode_index``, never
from scheduling order, so concurrency cannot change episode seeds or IDs.
"""

from __future__ import annotations

import hashlib


def derive_seed(run_seed: int, condition_index: int, episode_index: int) -> int:
    """Derive a deterministic 63-bit seed for a condition/episode position."""
    if run_seed < 0 or condition_index < 0 or episode_index < 0:
        raise ValueError("seed inputs must be non-negative")
    material = f"{run_seed}:{condition_index}:{episode_index}".encode()
    digest = hashlib.sha256(material).digest()
    return int.from_bytes(digest[:8], "big", signed=False) % (2**63)


def derive_step_seed(episode_seed: int, step_ordinal: int) -> int:
    """Derive a per-step seed from the episode seed and step ordinal."""
    material = f"{episode_seed}:{step_ordinal}".encode()
    digest = hashlib.sha256(material).digest()
    return int.from_bytes(digest[:8], "big", signed=False) % (2**63)
