---
name: deploy-event-tracker
description: Deploy, dry-run, roll back, or explicitly synchronize configuration for the distro and ocean Discord bots from the Windows Git checkout to rootless Podman on the approved Ubuntu host.
---

# Deploy Event Tracker

1. Work only from `D:\dev\distro_event_tracker` and target only `steijnserver`.
2. Never display `.env` contents or secret values. Preserve existing remote environment files unless the user explicitly requests synchronization.
3. Use `deploy.ps1 -DryRun` to preview a release without changing Podman services or remote configuration.
4. Use `deploy.ps1` for a normal release. It must reject dirty worktrees and require `HEAD == origin/main`.
5. Use `deploy.ps1 -SyncSecrets` only when code and both local env files must be synchronized together.
6. Use `deploy.ps1 -SecretsOnly` only for an explicitly requested configuration rotation.
7. Use `deploy.ps1 -Rollback <full-sha>` only for a retained production release.
8. Normal deploys use a server-side two-minute startup gate per bot: immutable image SHA, active/healthy service, Discord connection, three reconstructed events, and no new error-level startup signals. Use `deploy.ps1 -VerifyFullInitialization` only when the final reconstruction marker is required.
9. Never manually copy a source tree or environment file to Ubuntu; the deployment script archives tracked files and atomically streams configuration over SSH stdin.
10. MicroK8s was permanently removed in July 2026. Do not use or recreate the retired migration tooling.
11. Successful deployments retain five immutable releases and matching image tags, then prune dangling rootless image layers. Do not manually delete retained releases or migration backups.
12. If a normal release fails the bounded gate, the deployment script automatically restores both bots to the prior retained release. Explicit rollback and secrets-only failures require diagnosis rather than recursive rollback.

Use `ops/remote.ps1` with explicit psteijn runtime access. Protected host diagnostics go through `ops/remote-admin.ps1` as codex/root. See `docs/server-access.md`; never change the shared alias user.
