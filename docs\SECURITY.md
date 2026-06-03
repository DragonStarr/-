# Security

## Secrets

- Secrets are read from env or a real secret store.
- Tokens are encrypted at rest and never returned by API responses.
- GitHub, Telegram and FreeModel tokens are redacted before logs or LLM calls.
- Production requires `TOKEN_ENCRYPTION_KEY` and `TELEGRAM_WEBHOOK_SECRET`.

## Webhooks

Telegram webhook requests must include `X-Telegram-Bot-Api-Secret-Token` when the secret is configured.

## Access

Owner-only operations include account connection, plugin installation, self-update, LLM status and architecture gate.
PVZ operators can see operational tasks but cannot change money, staff rates or tokens.

## LLM

External text is neutralized before prompts. LLM output is never the only source of permissions, payments, writes or readiness.
