# Runbook

## Local Dev

1. Start dependencies with `docker compose -f infra/compose/dev.yml up -d`.
2. Pull a local model in Ollama, for example `ollama pull qwen3:8b`.
3. Put secrets only in `.env`.
4. Run migrations before safe test or live operation.

## Release Gate

- `uv run ruff check .`
- `uv run pytest`
- `npm ci && npm run typecheck && npm run build && npm audit --audit-level=moderate` in `apps/miniapp`
- Secret scan before push
- Browser check for desktop and mobile

## Rollback

Use the last green commit plus `vendor/_snapshots/current`. Never promote a self-update candidate until tests, LLM review, canary and metrics are green.

## Backups

Run `infra/backups/backup.ps1` on the host. Restore is checked only on an isolated copy.
