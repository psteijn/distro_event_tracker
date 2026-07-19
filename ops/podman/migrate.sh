#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 || ! "$1" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Usage: migrate.sh <full-commit-sha>" >&2
  exit 2
fi

RELEASE_SHA="$1"
SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RELEASE_ROOT="$(cd "${RELEASE_ROOT:-$SCRIPT_ROOT/../..}" && pwd)"
RELEASE_BASE="/srv/releases/distro-event-tracker"
DATA_ROOT="$HOME/.local/share/distro-event-tracker"
BACKUP_ROOT="$DATA_ROOT/migration-backup/$(date -u +%Y%m%dT%H%M%SZ)"
NAMESPACE="distro-event-tracker"

source "$SCRIPT_ROOT/common.sh"

cutover_instances=()
migration_verified=0

rollback_all() {
  local instance service
  if (( ${#cutover_instances[@]} == 0 )); then
    return 0
  fi
  echo "Restoring MicroK8s replicas for the interrupted migration." >&2
  set +e
  for instance in "${cutover_instances[@]}"; do
    service="$(service_name "$instance")"
    systemctl --user stop "$service" >/dev/null 2>&1 || true
    microk8s kubectl -n "$NAMESPACE" scale \
      "deployment/distro-event-tracker-$instance" --replicas=1 >/dev/null 2>&1 || true
    microk8s kubectl -n "$NAMESPACE" rollout status \
      "deployment/distro-event-tracker-$instance" --timeout=600s >/dev/null 2>&1 || true
  done
  set -e
}

on_exit() {
  local status=$?
  if (( status != 0 && migration_verified == 0 )); then
    rollback_all
  fi
  exit "$status"
}
trap on_exit EXIT

command -v microk8s >/dev/null || { echo "MicroK8s is required for migration." >&2; exit 1; }
[[ "$(loginctl show-user "$(id -un)" -p Linger --value)" == "yes" ]] || {
  echo "User lingering must be enabled before migration." >&2
  exit 1
}
for instance in distro ocean; do
  [[ "$(microk8s_replica_count "$instance")" == "1" ]] || {
    echo "Expected one healthy MicroK8s replica for $instance." >&2
    exit 1
  }
  microk8s kubectl -n "$NAMESPACE" wait --for=condition=Available \
    "deployment/distro-event-tracker-$instance" --timeout=60s >/dev/null
done

install -d -m 700 "$BACKUP_ROOT"

migrate_instance() {
  local instance="$1"
  local claim pv pv_path source_file target_dir target_file source_sum target_sum service
  claim="distro-event-tracker-${instance}-data"
  service="$(service_name "$instance")"
  pv="$(microk8s kubectl -n "$NAMESPACE" get "pvc/$claim" -o jsonpath='{.spec.volumeName}')"
  pv_path="$(microk8s kubectl get "pv/$pv" -o jsonpath='{.spec.hostPath.path}')"
  source_file="$pv_path/reminders_opt_out.txt"
  target_dir="$DATA_ROOT/$instance"
  target_file="$target_dir/reminders_opt_out.txt"
  [[ -r "$source_file" ]] || { echo "Cannot read $instance reminder state." >&2; return 1; }

  source_sum="$(sha256sum "$source_file" | awk '{print $1}')"
  install -m 600 "$source_file" "$BACKUP_ROOT/${instance}-reminders_opt_out.txt"
  printf '%s  %s\n' "$source_sum" "${instance}-reminders_opt_out.txt" \
    > "$BACKUP_ROOT/${instance}.sha256"

  systemctl --user stop "$service" 2>/dev/null || true
  microk8s kubectl -n "$NAMESPACE" scale "deployment/distro-event-tracker-$instance" --replicas=0 >/dev/null
  microk8s kubectl -n "$NAMESPACE" wait --for=delete pod \
    -l "app.kubernetes.io/name=distro-event-tracker,app.kubernetes.io/instance=$instance" \
    --timeout=90s >/dev/null

  cutover_instances+=("$instance")

  install -d -m 700 "$target_dir"
  install -m 600 "$source_file" "$target_file"
  target_sum="$(sha256sum "$target_file" | awk '{print $1}')"
  if [[ "$source_sum" != "$target_sum" ]]; then
    echo "$instance reminder state checksum changed during migration." >&2
    return 1
  fi
  systemctl --user start "$service"
  wait_for_bot "$instance"
  verify_bot_revision "$instance" "$RELEASE_SHA"
  [[ "$(microk8s_replica_count "$instance")" == "0" ]] || {
    echo "$instance MicroK8s Deployment unexpectedly has a live replica." >&2
    return 1
  }
  echo "Migrated and verified $instance."
}

migrate_instance distro
migrate_instance ocean

for unit in homeassistant.service piper.service zwave-js-ui.service; do
  systemctl is-active --quiet "$unit" || {
    echo "$unit is no longer active; refusing to decommission MicroK8s." >&2
    exit 1
  }
done

echo "$RELEASE_SHA" > "$BACKUP_ROOT/release-revision"
chmod 600 "$BACKUP_ROOT/release-revision"
ln -sfn "$RELEASE_ROOT" "$RELEASE_BASE/current"
ln -sfn "$RELEASE_ROOT" /srv/src/distro_event_tracker
  migration_verified=1
echo "Both bots are healthy under Podman. Migration backup: $BACKUP_ROOT"
