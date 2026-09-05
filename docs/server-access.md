## Server access contract

Use the existing `steijnserver` SSH alias with an explicit user for every SSH/SCP
operation. Keep both `steijnserver` and `steijnserver-psteijn` defaulting to
`psteijn` for compatibility. Host, port and the existing `steijnserver_codex`
identity come from the local SSH config; never commit keys or credentials.

| Purpose | Login | Execution |
| --- | --- | --- |
| Host administration and protected logs | codex | root via sudo -n |
| Distro deployment, secrets, lifecycle and logs | psteijn | psteijn rootless Podman |
| Home Assistant uploads and safe downloads | psteijn | psteijn |
| Home Assistant administration | codex | sudo -n /usr/local/sbin/ha-ops |
| Game infrastructure administration | codex | root, or explicitly gameserver |

Each repository owns its transport helper; no sibling checkout is required.
The helper sets `BatchMode=yes`, `StrictHostKeyChecking=yes`,
`ConnectTimeout=10`, `IdentitiesOnly=yes`, and an explicit `User`.
Ordinary operations never allocate a terminal. A missing key, unknown host key,
failed command or missing sudo grant is a failure, not an authentication prompt.
Use `powershell.exe -NoProfile -ExecutionPolicy Bypass -File <tool.ps1>`
on machines that block scripts; this does not change the machine execution policy.

When administering as a workload owner, use `sudo -n -H -u <owner>`, change to
that owner's home, and explicitly set `XDG_RUNTIME_DIR=/run/user/<resolved-uid>`
and `DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/<resolved-uid>/bus`.
Do not run rootless containers under root or change existing data ownership.
Full-root access remains confined to codex. Keep the LAN-only firewall,
secret files, backup safeguards, readiness gates and rollback procedures intact.

MicroK8s absence was verified on 2026-09-04. Do not introduce Kubernetes workloads.

### Distro tools

`deploy.ps1` and `ops/remote-status.ps1` select psteijn, checking the login,
home directory, user manager and rootless Podman context before uploads or restarts.
Secrets remain opt-in via `-SyncSecrets` / `-SecretsOnly`; ordinary deployment
never uploads environment files. Immutable release review, startup gates and automatic
rollback are unchanged. Use `deploy.ps1 -DryRun` after checks, commit and push.

Use `ops/remote-admin.ps1 -Command 'journalctl -n 20 --no-pager'` for protected
host diagnostics; it runs the supplied command as root through codex and sudo -n.
This entrypoint grants full host operations; use it only for reviewed work. For
owner-specific admin commands explicitly set home, cwd, runtime and bus as above.

### Access smoke test

Run `ops/verify-access.ps1` for read-only identity, privilege, journal,
staging-permission and failure-propagation checks. Add `-TransferProbe` to upload
and download a unique non-secret file, compare checksums, then remove only those
probe files. It does not restart services or synchronize secrets.

### Local rollout verification — 2026-09-04

Identity, non-interactive root/journal access, failure propagation, and disposable
upload/download checks passed. Probe checksums matched; only probe files were removed.
Shared SSH aliases still use psteijn and the existing steijnserver_codex identity.
No secrets were synchronized, no workload ownership changed, and no applications restarted.

Service start timestamps were unchanged before and after the local tooling rollout (UTC):

| Service | State | Last started |
| --- | --- | --- |
| Home Assistant | active | 2026-08-11 06:45:04 |
| Z-Wave JS UI | active | 2026-08-11 06:45:00 |
| Piper | active | 2026-08-11 06:44:56 |
| Distro bot | active, healthy | 2026-09-04 23:59:08 |
| Ocean bot | active, healthy | 2026-09-04 23:40:07 |
| Game switchboard | active | 2026-08-30 22:26:50 |

All game instances remained stopped. Home Assistant API and deployed tooling
fingerprints passed; the game backup status reported a verified, non-stale snapshot.
Runtime reinstall is not needed for the account-routing changes: they take effect
in the local PowerShell tools. Updated Linux deployment scripts are for the next
reviewed deployment; do not force an application restart to install them.
