---
name: operate-event-tracker
description: Inspect and operate the production distro and ocean Discord bots as rootless Podman services on the approved Ubuntu host, including status checks, logs, restarts, DNS diagnosis, persistence checks, and explicit configuration rotation.
---

# Operate Event Tracker

1. Target only `steijnserver` and the `psteijn` rootless Podman user manager.
2. Start with `ops/remote-status.ps1`; report each service's health, restarts, immutable image, warnings, and Discord connection state.
3. Treat historical rollout warnings separately from current failures. Check current DNS resolution when logs show Discord name-resolution errors.
4. Use `systemctl --user`, `podman inspect`, `podman logs`, `journalctl --user`, and read-only health checks for diagnosis.
5. Readiness means the Discord gateway is connected; full historical reconstruction is a separate log milestone. Normal deployments verify three reconstructed events within two minutes; use `deploy.ps1 -VerifyFullInitialization` only when the final marker matters.
6. Use `deploy.ps1 -SecretsOnly` for explicitly requested configuration rotation. Never print, copy, or inspect secret values.
7. Verify reminder opt-out persistence by comparing checksums or metadata before and after service recreation; do not display user IDs.
8. Never edit release directories, Quadlets, environment files, container filesystems, or live generated units by hand. Route lasting changes through a committed deployment.
9. MicroK8s is intentionally absent. Report its reappearance as unexpected infrastructure drift.

Use `ops/remote.ps1` with explicit psteijn runtime access. Protected host diagnostics go through `ops/remote-admin.ps1` as codex/root. See `docs/server-access.md`; never change the shared alias user.
