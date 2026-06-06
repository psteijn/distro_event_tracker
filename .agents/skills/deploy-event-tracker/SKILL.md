---
name: deploy-event-tracker
description: Deploy and verify the Windows Scheduled Task instances of this Discord bot after validated code changes.
---

# Deploy Event Tracker

1. Run `check.bat`; stop if it fails.
2. Run `deploy.bat`.
3. Run `python deploy_report.py`.
4. Inspect fresh distro and ocean task logs for successful connections and new errors.
5. Report each instance as healthy or explain the failure. Never deploy unless explicitly requested.
