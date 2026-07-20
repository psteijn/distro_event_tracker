# Agent Guide

Read `docs/architecture.md` before changing code and
`docs/persistence-contracts.md` before changing embeds, parsing, or raw output.

## Rules

- Discord history remains the datastore; preserve all persistence contracts.
- Put domain behavior in the owning feature package, not `bot.py`.
- Add Discord commands and listeners to the owning feature Cog.
- Keep Discord handlers thin and inject dependencies into testable behavior.
- Do not introduce import-time network access or production mutations.
- Use `send_long_message` for long Discord output.

## Validation

Run focused tests while editing, then run `check.bat` on Windows or `./check.sh`.
Deployment is separate and must only run when explicitly requested.

## Production

- Treat this Windows checkout as the only Git checkout and secret-file source.
- Use the SSH alias `steijnserver`; never embed an IP address, password, token, or env value in commands or committed files.
- Deploy only a clean `HEAD` that equals `origin/main` using `deploy.ps1`.
- Preserve the ignored local environment files unless the user explicitly requests `-SyncSecrets` or `-SecretsOnly`.
- Production bots run as rootless Podman Quadlets under `psteijn`; do not use rootful Podman or edit generated systemd units by hand.
- MicroK8s was decommissioned in July 2026. Do not reintroduce Kubernetes-specific deployment paths.
- Discord gateway readiness and historical reconstruction are separate states. A service can be healthy while reconstruction continues; allow up to 60 minutes when a deployment must verify the final reconstruction marker.
- Use `ops/remote-status.ps1` for read-only status and the deployment and operations skills for production changes and diagnostics.
