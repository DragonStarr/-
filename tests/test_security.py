from operator_day.config import Settings
from operator_day.security import fingerprint_secret, redact_secret


def test_redact_secret_masks_freemodel_key() -> None:
    text = "key=" + "fe_oa_" + "example_secret"

    assert "fe_oa_" not in redact_secret(text)


def test_redact_secret_masks_russian_secret_labels() -> None:
    text = "API ключ: temporary-value токен=another-value пароль: pass123"

    redacted = redact_secret(text)

    assert "temporary-value" not in redacted
    assert "another-value" not in redacted
    assert "pass123" not in redacted


def test_fingerprint_is_stable_and_short() -> None:
    assert fingerprint_secret("abc") == fingerprint_secret("abc")
    assert len(fingerprint_secret("abc")) == 10


def test_production_requires_token_encryption_key() -> None:
    settings = Settings(app_env="production", token_encryption_key="")

    try:
        settings.validate_runtime()
    except ValueError as exc:
        assert "TOKEN_ENCRYPTION_KEY" in str(exc)
    else:
        raise AssertionError("production settings must require encryption key")
