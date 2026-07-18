# Binder configuration

This directory exists only to make the public demo notebook launchable on
Binder without changing the repository's primary install story.

- `environment.yml` defines the lightweight Binder runtime.
- `postBuild` installs the package from the checked-out repository source.

Keep normal developer and production installation guidance in the repo root
(`pyproject.toml`, docs, README). Binder should remain a clearly separate demo
surface.

When sharing a Binder link, prefer a commit-pinned URL over a moving branch so
the notebook environment stays reproducible.
