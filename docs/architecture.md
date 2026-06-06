# Architecture

The application is an installable package under `src/distro_event_tracker`.

## Dependency Direction

1. Feature models, scoring rules, and persistence constants are pure Python.
2. Feature services may depend on their feature's pure modules and shared helpers.
3. Discord adapters may depend on services and Discord.py.
4. Runtime composition may depend on every layer.

Pure feature modules must never import `discord` or `distro_event_tracker.bot`. The
architecture test and import-linter contract enforce this rule.

## Current Runtime Boundary

`distro_event_tracker.bot` retains compatibility callbacks for existing tests and
persistence-heavy behavior. Production registration is owned by `events/cog.py` and
`dibs/cog.py`, composed by `bootstrap.py`. Do not add new commands or domain rules to
`bot.py`; put feature behavior in a service and expose it through the owning Cog.

## Common Changes

- Scoring or attendance behavior: `events/scoring.py`, then focused scoring tests.
- Persistence format: the owning feature's `persistence.py` and compatibility tests.
- New command: implement feature behavior first, then add a thin Discord adapter.
- Startup/configuration: `config.py`, `bootstrap.py`, and `__main__.py`.
