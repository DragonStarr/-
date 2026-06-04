from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from pathlib import Path
from time import time
from typing import Any
from urllib.parse import parse_qsl

from cryptography.fernet import Fernet

from operator_day.domain import Role, TenantContext

SECRET_PATTERNS = [
    re.compile(r"fe_oa_[a-zA-Z0-9]+"),
    re.compile(r"ghp_[a-zA-Z0-9_]+"),
    re.compile(r"github_pat_[a-zA-Z0-9_]+"),
    re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{30,}\b"),
    re.compile(r"(?i)(api\s*[_-]?\s*key|token|secret|password)\s*[:=]\s*['\"]?[^'\"\s]+"),
    re.compile(
        r"(?i)(api\s*ключ|апи\s*ключ|ключ\s*api|токен|секрет|пароль)\s*[:=]\s*['\"]?[^'\"\s]+"
    ),
]

PROMPT_INJECTION_PATTERNS = [
    re.compile(r"(?i)ignore\s+(all\s+)?previous\s+instructions"),
    re.compile(r"(?i)system\s*prompt"),
    re.compile(r"(?i)developer\s+message"),
    re.compile(r"(?i)tool\s+message"),
    re.compile(r"(?i)reveal\s+(your\s+)?(rules|instructions|secrets)"),
    re.compile(r"(?i)print\s+(your\s+)?(system|developer)\s+(prompt|message)"),
    re.compile(r"(?i)disregard\s+(all\s+)?(prior|previous)\s+instructions"),
    re.compile(r"(?i)forget\s+(all\s+)?(prior|previous)\s+instructions"),
    re.compile(r"(?i)act\s+as\s+(system|developer|admin)"),
    re.compile(r"(?i)jailbreak"),
    re.compile(r"(?i)не\s+выполняй\s+предыдущ"),
    re.compile(r"(?i)забудь\s+(все\s+)?(инструкции|правила)"),
    re.compile(r"(?i)игнорируй\s+(все\s+)?(инструкции|правила)"),
    re.compile(r"(?i)покажи\s+(системн|инструкц|правил|секрет|ключ)"),
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


class AuthError(ValueError):
    pass


def verify_telegram_init_data(
    init_data: str,
    bot_token: str,
    *,
    ttl_seconds: int = 86_400,
    now: int | None = None,
) -> dict[str, Any]:
    if not bot_token:
        raise AuthError("telegram bot token is not configured")
    pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=False)
    values = dict(pairs)
    expected_hash = values.pop("hash", "")
    if not expected_hash:
        raise AuthError("telegram init data hash is missing")
    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(values.items())
    )
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    actual_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(actual_hash, expected_hash):
        raise AuthError("telegram init data signature is invalid")
    auth_date_raw = values.get("auth_date", "")
    try:
        auth_date = int(auth_date_raw)
    except ValueError as exc:
        raise AuthError("telegram init data auth_date is invalid") from exc
    current = int(time() if now is None else now)
    if ttl_seconds > 0 and current - auth_date > ttl_seconds:
        raise AuthError("telegram init data is expired")
    return values


def tenant_context_from_telegram_init_data(values: dict[str, Any]) -> TenantContext:
    raw_user = values.get("user") or "{}"
    try:
        user = json.loads(str(raw_user))
    except json.JSONDecodeError as exc:
        raise AuthError("telegram user payload is invalid") from exc
    tg_id = str(user.get("id") or "").strip()
    if not tg_id:
        raise AuthError("telegram user id is missing")
    return TenantContext(
        tenant_id=f"tg-{tg_id}",
        user_id=tg_id,
        role=Role.OWNER,
    )


def create_session_token(
    ctx: TenantContext,
    secret: str,
    *,
    ttl_seconds: int = 3_600,
    now: int | None = None,
) -> str:
    if not secret:
        raise AuthError("session secret is not configured")
    current = int(time() if now is None else now)
    payload = {
        "tenant_id": ctx.tenant_id,
        "user_id": ctx.user_id,
        "role": ctx.role.value,
        "exp": current + ttl_seconds,
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    body = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    signature = hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256)
    return f"{body}.{signature.hexdigest()}"


def verify_session_token(token: str, secret: str, *, now: int | None = None) -> TenantContext:
    if not secret:
        raise AuthError("session secret is not configured")
    try:
        body, signature = token.split(".", 1)
    except ValueError as exc:
        raise AuthError("session token is malformed") from exc
    actual = hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256)
    if not hmac.compare_digest(actual.hexdigest(), signature):
        raise AuthError("session token signature is invalid")
    padded = body + "=" * (-len(body) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
    except (ValueError, json.JSONDecodeError) as exc:
        raise AuthError("session token payload is invalid") from exc
    current = int(time() if now is None else now)
    if int(payload.get("exp") or 0) < current:
        raise AuthError("session token is expired")
    try:
        role = Role(str(payload["role"]))
        tenant_id = str(payload["tenant_id"])
        user_id = str(payload["user_id"])
    except (KeyError, ValueError) as exc:
        raise AuthError("session token context is invalid") from exc
    return TenantContext(tenant_id=tenant_id, user_id=user_id, role=role)


def _local_fernet_key(scope: str) -> bytes:
    scoped_seed = f"local-token-cipher:{scope}:{Path.cwd().resolve()}"
    scoped_digest = hashlib.sha256(scoped_seed.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(scoped_digest)


class TokenCipher:
    def __init__(self, key: str, *, local_fallback_scope: str | None = None) -> None:
        if key:
            raw_key = key.encode("utf-8")
        elif local_fallback_scope:
            raw_key = _local_fernet_key(local_fallback_scope)
        else:
            raise AuthError("TOKEN_ENCRYPTION_KEY is required for token encryption")
        self._fernet = Fernet(raw_key)

    def encrypt(self, token: str) -> str:
        return self._fernet.encrypt(token.encode("utf-8")).decode("utf-8")

    def decrypt(self, token_enc: str) -> str:
        raw = token_enc.encode("utf-8")
        return self._fernet.decrypt(raw).decode("utf-8")
