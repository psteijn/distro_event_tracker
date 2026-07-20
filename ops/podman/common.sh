#!/usr/bin/env bash

service_name() {
  printf 'distro-event-tracker-%s.service' "$1"
}

container_name() {
  printf 'distro-event-tracker-%s' "$1"
}

wait_for_bot() {
  local instance="$1"
  local started_at="$2"
  local mode="${3:-fast}"
  local service container deadline health state logs
  service="$(service_name "$instance")"
  container="$(container_name "$instance")"
  case "$mode" in
    fast) deadline=$((SECONDS + 120)) ;;
    full) deadline=$((SECONDS + 3600)) ;;
    *) echo "Unknown verification mode: $mode" >&2; return 2 ;;
  esac

  while (( SECONDS < deadline )); do
    state="$(systemctl --user show "$service" -p ActiveState --value 2>/dev/null || true)"
    if [[ "$state" != "active" ]]; then
      sleep 5
      continue
    fi
    health="$(podman inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container" 2>/dev/null || true)"
    if [[ "$health" == "healthy" ]]; then
      logs="$(podman logs --since "$started_at" "$container" 2>&1 || true)"
      if python3 "$(dirname "${BASH_SOURCE[0]}")/verify_logs.py" --mode "$mode" <<<"$logs"; then
        return 0
      fi
    fi
    sleep 5
  done

  echo "Timed out waiting for $instance $mode verification." >&2
  systemctl --user status "$service" --no-pager >&2 || true
  podman logs --tail 100 "$container" >&2 2>&1 || true
  return 1
}

verify_bot_revision() {
  local instance="$1"
  local expected_revision="$2"
  local container actual_revision health
  container="$(container_name "$instance")"
  actual_revision="$(podman inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$container")"
  health="$(podman inspect --format '{{.State.Health.Status}}' "$container")"
  [[ "$actual_revision" == "$expected_revision" ]] || {
    echo "$instance is running revision $actual_revision instead of $expected_revision." >&2
    return 1
  }
  [[ "$health" == "healthy" ]] || {
    echo "$instance health is $health instead of healthy." >&2
    return 1
  }
}
