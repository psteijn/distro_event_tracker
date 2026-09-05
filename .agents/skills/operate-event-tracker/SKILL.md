---
name: operate-event-tracker
description: Inspect and operate the production distro and ocean Discord bots as rootless Podman services on the approved Ubuntu host, including status checks, logs, restarts, DNS diagnosis, persistence checks, and explicit configuration rotation.
---

# Operate Event Tracker

## Access and diagnosis

Paths below are relative to the repository root. Read the
[server access contract](../../../docs/server-access.md) before remote work.
Use `ops/verify-access.ps1` for read-only account, sudo, journal, and staging checks
when access fails; add `-TransferProbe` only for an in-scope disposable transfer test.

Dot-source `ops/remote.ps1` and use `Invoke-DistroRuntime -Command ...` for additional
owner-specific diagnostics. It selects `psteijn` and sets the home, working directory,
resolved runtime directory, and user bus. Use `ops/remote-admin.ps1 -Command ...`
for protected host diagnostics through codex and `sudo -n`; its commands run as root.
Do not run bot Podman commands in that root context or fall back to another account.

On key, host-key, or sudo failure, report the failed check and needed repair; do not
repoint shared aliases, weaken strict host-key checking, or request a routine TTY.
Status/log requests stay read-only. Access-policy repairs, restarts, secret rotations,
and deployment require the corresponding user request; never restart to test access.

## Runtime checks

1. Target only `steijnserver`; bot runtime operations belong to the `psteijn` rootless Podman user manager, while protected host diagnostics use codex/root.
2. Start with `ops/remote-status.ps1`; report each service's health, restarts, immutable image, warnings, and Discord connection state.
3. Treat historical rollout warnings separately from current failures. Check current DNS resolution when logs show Discord name-resolution errors.
4. Use `systemctl --user`, `podman inspect`, `podman logs`, `journalctl --user`, and read-only health checks for diagnosis.
5. Readiness means the Discord gateway is connected; full historical reconstruction is a separate log milestone. Normal deployments verify three reconstructed events within two minutes; use `deploy.ps1 -VerifyFullInitialization` only when the final marker matters.
6. Use `deploy.ps1 -SecretsOnly` for explicitly requested configuration rotation. Never print, copy, or inspect secret values.
7. Verify reminder opt-out persistence by comparing checksums or metadata before and after service recreation; do not display user IDs.
8. Never edit release directories, Quadlets, environment files, container filesystems, or live generated units by hand. Route lasting changes through a committed deployment.
9. MicroK8s is intentionally absent. Report its reappearance as unexpected infrastructure drift.
