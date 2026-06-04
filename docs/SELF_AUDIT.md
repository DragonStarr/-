# Self Audit

## Closed

- Backend has tenant-scoped repositories, encrypted account tokens, idempotent confirmations and audit log.
- Telegram webhook checks the secret header when configured.
- LLM gateway is model-agnostic: local primary, external optional, offline fallback for safe test logic without spending external tokens.
- Prompt-injection and secret redaction are applied before LLM prompts.
- Plugin buttons use manifests and action allow-list, not arbitrary code.
- Self-update pipeline records last-known-good, sandbox/test/LLM/canary gates and rollback state.
- Mini App builds as a real Telegram-style Next.js 16 App Router PWA with bottom navigation, simple Russian copy and backend rewrites.
- Telegram bot mirrors live-readiness blockers in the `Кабинеты` screen, including write-scope blockers, without exposing replay/internal terms.
- Semantic memory is tenant-scoped, sanitized before persistence and pgvector-ready for a production embedding backend.
- CI covers backend lint/tests and Mini App typecheck/build/audit; Docker/compose and backup/restore runbooks are present.
- Runtime does not depend on live upstream SDK imports.
- `/api/release-gate` exposes a 20-point final readiness check and separates safe simulation from blockers before real operation.

## Still Needs Real Deployment Inputs

- Production local LLM host and model size must be selected for the actual VPS/GPU/CPU before heavy live use.
- Real marketplace tokens must be connected and validated by the owner.
- Postgres + pgvector production migration and backup restore test are needed before live seller data.
- Real external code vendoring should be added component by component with license hashes.
