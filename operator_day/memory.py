from __future__ import annotations

import math
import re
from collections import Counter
from hashlib import sha256

from operator_day.security import neutralize_external_text

TOKEN_PATTERN = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9]{2,}")
VECTOR_SIZE = 64


def normalize_memory_text(text: str, *, limit: int = 8000) -> str:
    cleaned = neutralize_external_text(text, limit=limit)
    return " ".join(cleaned.split())


def memory_hash(text: str) -> str:
    return sha256(normalize_memory_text(text).encode("utf-8")).hexdigest()


def text_tokens(text: str) -> list[str]:
    normalized = normalize_memory_text(text).lower()
    return TOKEN_PATTERN.findall(normalized)


def local_embedding(text: str, *, size: int = VECTOR_SIZE) -> list[float]:
    counts = Counter(text_tokens(text))
    vector = [0.0] * size
    if not counts:
        return vector
    for token, count in counts.items():
        bucket = int(sha256(token.encode("utf-8")).hexdigest(), 16) % size
        vector[bucket] += float(count)
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [round(value / norm, 6) for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    length = min(len(left), len(right))
    if length == 0:
        return 0.0
    numerator = sum(left[index] * right[index] for index in range(length))
    left_norm = math.sqrt(sum(value * value for value in left)) or 1.0
    right_norm = math.sqrt(sum(value * value for value in right)) or 1.0
    return numerator / (left_norm * right_norm)
