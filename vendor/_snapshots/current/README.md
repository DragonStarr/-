# Last Known Good Snapshot

This folder marks the runtime snapshot used when an upstream repository disappears or an update fails.

The self-update pipeline may create candidate snapshots next to this directory, but production continues
to use `current` until sandbox, tests, LLM review and canary gates pass.
