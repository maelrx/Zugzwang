from __future__ import annotations

import hashlib
import math
import re


SparseVector = dict[int, float]
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def tokenize_text(text: str) -> list[str]:
    if not text:
        return []
    return TOKEN_PATTERN.findall(text.lower())


def embed_text(text: str, dims: int = 384) -> SparseVector:
    tokens = tokenize_text(text)
    if not tokens:
        return {}

    raw: dict[int, float] = {}
    for token in tokens:
        bucket = _bucket_for_token(token, dims=dims)
        raw[bucket] = raw.get(bucket, 0.0) + 1.0

    norm = math.sqrt(sum(value * value for value in raw.values()))
    if norm <= 0:
        return {}
    return {bucket: value / norm for bucket, value in raw.items()}


def cosine_similarity(left: SparseVector, right: SparseVector) -> float:
    if not left or not right:
        return 0.0
    if len(left) > len(right):
        left, right = right, left
    dot = 0.0
    for idx, value in left.items():
        dot += value * right.get(idx, 0.0)
    return dot


def _bucket_for_token(token: str, dims: int) -> int:
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % max(dims, 1)
