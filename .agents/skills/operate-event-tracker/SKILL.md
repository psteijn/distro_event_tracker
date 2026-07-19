---
name: operate-event-tracker
description: Inspect and operate the production distro and ocean Discord bots on the approved Ubuntu MicroK8s host, including status checks, logs, restarts, DNS diagnosis, persistence checks, and explicit secret rotation.
---

# Operate Event Tracker

1. Target only `steijnserver` and namespace `distro-event-tracker`.
2. Start with `ops/remote-status.ps1`; report each pod's readiness, restarts, immutable image, warnings, and Discord connection state.
3. Treat historical rollout warnings separately from current failures. Check current DNS resolution when logs show Discord name-resolution errors.
4. Use `microk8s kubectl logs`, `describe`, `get events`, and read-only health checks for diagnosis.
5. Restart a Deployment only when requested or when diagnosis establishes that recovery requires it; use `kubectl rollout restart` and wait for readiness.
6. Use `deploy.ps1 -SecretsOnly` for explicitly requested configuration rotation. Never print, copy, or inspect secret values.
7. Verify reminder opt-out persistence by comparing checksums or metadata before and after pod recreation; do not display user IDs.
8. Never edit release directories, container filesystems, or live manifests by hand. Route lasting changes through a committed deployment.
