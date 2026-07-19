---
name: deploy-event-tracker
description: Deploy, dry-run, roll back, or explicitly synchronize configuration for the distro and ocean Discord bots from the Windows Git checkout to the approved Ubuntu MicroK8s host.
---

# Deploy Event Tracker

1. Work only from `D:\dev\distro_event_tracker` and target only `steijnserver`.
2. Never display `.env` contents or secret values. Preserve existing Secrets unless the user explicitly requests synchronization.
3. Use `deploy.ps1 -DryRun` to preview a release without changing Kubernetes or Secrets.
4. Use `deploy.ps1` for a normal release. It must reject dirty worktrees and require `HEAD == origin/main`.
5. Use `deploy.ps1 -SyncSecrets` only when code and both local env files must be synchronized together.
6. Use `deploy.ps1 -SecretsOnly` only for an explicitly requested configuration rotation.
7. Use `deploy.ps1 -Rollback <full-sha>` only for a retained production release.
8. Wait for both rollouts and confirm the immutable image SHA, readiness, Discord connection, Kubernetes warnings, and recent errors.
9. Never manually copy a source tree or secret file to Ubuntu; the deployment script archives tracked files and streams Secrets over SSH stdin.
