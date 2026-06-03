from __future__ import annotations

import base64
import hashlib
import re

from cryptography.fernet import Fernet

SECRET_PATTERNS = [
    re.compile(r"fe_oa_[a-zA-Z0-9]+"),
    re.compile(r"ghp_[a-zA-Z0-9_]+"),
    re.compile(r"github_pat_[a-zA-Z0-9_]+"),
    re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{30,}\b"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?[^'\"\s]+"),
]

PROMPT_INJECTION_PATTERNS = [
    re.compile(r"(?i)ignore\s+(all\s+)?previous\s+instructions"),
    re.compile(r"(?i)system\s*prompt"),
    re.compile(r"(?i)developer\s+message"),
    re.compile(r"(?i)reveal\s+(your\s+)?(rules|instructions|secrets)"),
    re.compile(r"(?i)act\s+as\s+(system|developer|admin)"),
    re.compile(r"(?i)jailbreak"),
    re.compile(r"(?i)не\s+выполняй\s+предыдущ"),
    re.compile(r"(?i)игнорируй\s+(все\s+)?(инструкции|правила)"),
    re.compile(r"(?i)раскрой\s+(системн|секрет|ключ)"),
]


def redact_secret(value: str) -> str:
    redacted = value
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def neutralize_external_text(value: str, *, limit: int = 12_000) -> str:
    """Treat untrusted text as data before it reaches an LLM prompt."""
    cleaned = redact_secret(value)[:limit]
    for pattern in PROMPT_INJECTION_PATTERNS:
        cleaned = pattern.sub("[blocked external instruction]", cleaned)
    return cleaned


def fingerprint_secret(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return digest[:10]


def _dev_fernet_key(seed: str) -> bytes:
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


class TokenCipher:
    def __init__(self, key: str) -> None:
        raw_key = key.encode("utf-8") if key else _dev_fernet_key("operator-day-local-dev-key")
        self._fernet = Fernet(raw_key)

    def encrypt(self, token: str) -> str:
        return self._fernet.encrypt(token.encode("utf-8")).decode("utf-8")

    def decrypt(self, token_enc: str) -> str:
        return self._fernet.decrypt(token_enc.encode("utf-8")).decode("utf-8")
