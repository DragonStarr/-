# Architecture

`Оператор дня` is a Telegram bot + Mini App backend for sellers and PVZ owners.

## Flow

Marketplace account API -> transport safety gates -> workers -> database -> orchestrator -> bot/Mini App -> user confirmation -> action -> audit -> feedback.

## Boundaries

- Marketplace writes require `DO_CONFIRM` and idempotency.
- User data is tenant-scoped in repositories and prepared for Postgres RLS.
- The local LLM is the primary brain. External models are optional accelerators.
- Plugin buttons are declarative manifests, not arbitrary code.
- Self-update never promotes a candidate without sandbox, tests, LLM review and canary.

## Services

- FastAPI: API, Telegram webhook, Mini App backend.
- aiogram: Telegram bot interaction.
- Celery/Redis: sync and scheduled work.
- Postgres + pgvector target: business data and memory.
- Local LLM via OpenAI-compatible endpoint: review, drafts and self-update checks.
- Mini App: Telegram-first UI and PWA shell.
