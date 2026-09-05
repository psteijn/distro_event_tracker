---
name: deploy-event-tracker
description: Deploy, dry-run, roll back, or explicitly synchronize configuration for the distro and ocean Discord bots from the Windows Git checkout to rootless Podman on the approved Ubuntu host.
---

# Deploy Event Tracker

## Access and scope

Paths below are relative to the repository root. Before remote work, read the
[server access contract](../../../docs/server-access.md). `deploy.ps1` uses
`ops/remote.ps1` to select `psteijn` explicitly for rootless runtime operations,
uploads, rollback, and streamed secret synchronization. Its identity, home,
user-manager, and Podman checks must pass before upload or restart.

For access diagnosis, run `ops/verify-access.ps1` without switches first.
`-TransferProbe` creates and removes disposable files; use it only when transfer
verification is in scope. Do not switch runtime operations to codex/root, change
the shared alias user, disable host-key checking, or add a TTY to bypass a failure.
Use `ops/remote-admin.ps1` only for authorized protected host work, not bot deployment.

A request to review code, edit skills, commit, or push is not a deployment request.
Do not restart bots just to test authentication or install local tooling changes.

## Release workflow

1. Work only from `D:\dev\distro_event_tracker` and target only `steijnserver`.
2. Never display `.env` contents or secret values. Preserve existing remote environment files unless the user explicitly requests synchronization.
3. For an authorized release preview, use `deploy.ps1 -DryRun` after local checks and a clean commit pushed to `origin/main`. It uploads a temporary archive and renders Quadlets without changing Podman services or remote configuration.
4. Use `deploy.ps1` for a normal release. It must reject dirty worktrees and require `HEAD == origin/main`.
5. Use `deploy.ps1 -SyncSecrets` only when code and both local env files must be synchronized together.
6. Use `deploy.ps1 -SecretsOnly` only for an explicitly requested configuration rotation.
7. Use `deploy.ps1 -Rollback <full-sha>` only for a retained production release.
8. Normal deploys use a server-side two-minute startup gate per bot: immutable image SHA, active/healthy service, Discord connection, three reconstructed events, and no new error-level startup signals. Use `deploy.ps1 -VerifyFullInitialization` only when the final reconstruction marker is required.
9. Never manually copy a source tree or environment file to Ubuntu; the deployment script archives tracked files and atomically streams configuration over SSH stdin.
10. MicroK8s was permanently removed in July 2026. Do not use or recreate the retired migration tooling.
11. Successful deployments retain five immutable releases and matching image tags, then prune dangling rootless image layers. Do not manually delete retained releases or migration backups.
12. If a normal release fails the bounded gate, the deployment script automatically restores both bots to the prior retained release. Explicit rollback and secrets-only failures require diagnosis rather than recursive rollback.
