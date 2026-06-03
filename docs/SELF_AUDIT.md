# Self Audit

## Closed

- Backend has tenant-scoped repositories, encrypted account tokens, idempotent confirmations and audit log.
- Telegram webhook checks the secret header when configured.
- LLM gateway is model-agnostic: local primary, external optional, offline fallback for safe demo.
- Prompt-injection and secret redaction are applied before LLM prompts.
- Plugin buttons use manifests and action allow-list, not arbitrary code.
- Self-update pipeline records last-known-good, sandbox/test/LLM/canary gates and rollback state.
- Mini App builds as a real Telegram-style React app with bottom navigation and simple Russian copy.
- Runtime does not depend on live upstream SDK imports.

## Still Needs Real Deployment Inputs

- Production local LLM host and model size must be selected for the actual VPS/GPU/CPU.
- Real marketplace tokens must be connected and validated by the owner.
- Postgres + pgvector production migration and backup restore test are needed before live seller data.
- Real external code vendoring should be added component by component with license hashes.
