# Self-Update

Self-update is controlled autonomy, not automatic production mutation.

## Pipeline

1. Watcher detects a new upstream release or commit.
2. Mirror copies it into an isolated candidate snapshot.
3. Prompt-injection scan treats README, comments and code text as data.
4. Sandbox build runs without secrets and without write access to production data.
5. Contract tests run against mock marketplace APIs.
6. Local LLM reviews the diff for security, license and interface risks.
7. Canary opens the candidate for one tenant or a small percentage.
8. Rollback returns to `vendor/_snapshots/current`.

## Runtime Rule

The app always runs from last known good. A candidate becomes current only after all gates pass and owner promotion is recorded in audit.
