#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: deploy.sh <full-commit-sha> [--dry-run|--verify-full|--rollback|--rollback-full]" >&2
  exit 2
fi

[[ "$(id -un)" == psteijn && "$HOME" == /home/psteijn ]] || {
  echo "Deployment requires the psteijn login and home directory." >&2
  exit 1
}
cd "$HOME"
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"
[[ -S "$XDG_RUNTIME_DIR/bus" ]] || { echo "User bus is unavailable." >&2; exit 1; }
systemctl --user show-environment >/dev/null

RELEASE_SHA="$1"
MODE="${2:-apply}"
if [[ ! "$RELEASE_SHA" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Release revision must be a full lowercase Git SHA." >&2
  exit 2
fi
VERIFY_MODE=fast
AUTO_ROLLBACK=1
case "$MODE" in
  apply) ;;
  --dry-run) ;;
  --verify-full) VERIFY_MODE=full ;;
  --rollback) AUTO_ROLLBACK=0 ;;
  --rollback-full) VERIFY_MODE=full; AUTO_ROLLBACK=0 ;;
  *) echo "Unknown deployment mode: $MODE" >&2; exit 2 ;;
esac

SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${RELEASE_ROOT:-$SCRIPT_ROOT/../..}" && pwd)"
RELEASE_BASE="/srv/releases/distro-event-tracker"
QUADLET_DIR="$HOME/.config/containers/systemd"
CONFIG_DIR="$HOME/.config/distro-event-tracker"
DATA_DIR="$HOME/.local/share/distro-event-tracker"
IMAGE_TAG="git-${RELEASE_SHA:0:12}"
IMAGE="localhost/distro-event-tracker:${IMAGE_TAG}"
RENDER_DIR="$(mktemp -d)"
trap 'rm -rf -- "$RENDER_DIR"' EXIT

source "$SCRIPT_ROOT/common.sh"

command -v podman >/dev/null || { echo "podman is required" >&2; exit 1; }
command -v python3 >/dev/null || { echo "python3 is required for deployment verification" >&2; exit 1; }
[[ "$(podman info --format '{{.Host.Security.Rootless}}')" == "true" ]] || {
  echo "The deployment must use rootless Podman." >&2
  exit 1
}
[[ "$(podman info --format '{{.Host.CgroupsVersion}}')" == "v2" ]] || {
  echo "Podman Quadlets require cgroup v2." >&2
  exit 1
}
[[ -f "$ROOT_DIR/.release-revision" ]] || { echo "Missing release metadata." >&2; exit 1; }
[[ "$(tr -d '\r\n' < "$ROOT_DIR/.release-revision")" == "$RELEASE_SHA" ]] || {
  echo "Release metadata does not match requested revision." >&2
  exit 1
}

for instance in distro ocean; do
  sed "s/RELEASE_TAG/${IMAGE_TAG}/g" \
    "$ROOT_DIR/ops/podman/distro-event-tracker-${instance}.container.in" \
    > "$RENDER_DIR/distro-event-tracker-${instance}.container"
done

QUADLET_UNIT_DIRS="$RENDER_DIR" /usr/lib/systemd/system-generators/podman-system-generator --user --dryrun >/dev/null

if [[ "$MODE" == "--dry-run" ]]; then
  for instance in distro ocean; do
    installed="$QUADLET_DIR/distro-event-tracker-${instance}.container"
    if [[ -f "$installed" ]]; then
      diff -u "$installed" "$RENDER_DIR/distro-event-tracker-${instance}.container" || true
    else
      echo "Would install $installed"
    fi
  done
  echo "Podman dry run complete for $RELEASE_SHA; no resources changed."
  exit 0
fi

PREVIOUS_RELEASE=""
PREVIOUS_SHA=""
if [[ -L "$RELEASE_BASE/current" ]]; then
  candidate="$(readlink -f "$RELEASE_BASE/current")"
  if [[ "$candidate" == "$RELEASE_BASE"/* && -f "$candidate/.release-revision" ]]; then
    PREVIOUS_RELEASE="$candidate"
    PREVIOUS_SHA="$(tr -d '\r\n' < "$candidate/.release-revision")"
  fi
fi

for instance in distro ocean; do
  [[ -s "$CONFIG_DIR/${instance}.env" ]] || {
    echo "Missing Podman environment file for $instance; synchronize configuration first." >&2
    exit 1
  }
done

install -d -m 700 "$QUADLET_DIR" "$CONFIG_DIR" "$DATA_DIR/distro" "$DATA_DIR/ocean"
podman image exists "$IMAGE" || podman build --pull=never --build-arg "VCS_REF=${RELEASE_SHA}" -t "$IMAGE" "$ROOT_DIR"
for instance in distro ocean; do
  install -m 600 "$RENDER_DIR/distro-event-tracker-${instance}.container" \
    "$QUADLET_DIR/distro-event-tracker-${instance}.container"
done
systemctl --user daemon-reload

start_and_verify_bots() {
  local expected_sha="$1"
  local instance started_at
  for instance in distro ocean; do
    started_at="$(date --utc --iso-8601=seconds)"
    systemctl --user restart "$(service_name "$instance")" || return 1
    wait_for_bot "$instance" "$started_at" "$VERIFY_MODE" || return 1
    verify_bot_revision "$instance" "$expected_sha" || return 1
  done
}

rollback_both_bots() {
  local previous_tag previous_image instance
  if [[ -z "$PREVIOUS_RELEASE" || ! "$PREVIOUS_SHA" =~ ^[0-9a-f]{40}$ ]]; then
    echo "No retained prior release is available for automatic rollback." >&2
    return 1
  fi
  echo "Fast verification failed; rolling both bots back to $PREVIOUS_SHA." >&2
  previous_tag="git-${PREVIOUS_SHA:0:12}"
  previous_image="localhost/distro-event-tracker:${previous_tag}"
  for instance in distro ocean; do
    sed "s/RELEASE_TAG/${previous_tag}/g" \
      "$PREVIOUS_RELEASE/ops/podman/distro-event-tracker-${instance}.container.in" \
      > "$RENDER_DIR/distro-event-tracker-${instance}.container"
  done
  QUADLET_UNIT_DIRS="$RENDER_DIR" /usr/lib/systemd/system-generators/podman-system-generator --user --dryrun >/dev/null
  podman image exists "$previous_image" || podman build --pull=never \
    --build-arg "VCS_REF=${PREVIOUS_SHA}" -t "$previous_image" "$PREVIOUS_RELEASE"
  for instance in distro ocean; do
    install -m 600 "$RENDER_DIR/distro-event-tracker-${instance}.container" \
      "$QUADLET_DIR/distro-event-tracker-${instance}.container"
  done
  systemctl --user daemon-reload
  start_and_verify_bots "$PREVIOUS_SHA"
  ln -sfn "$PREVIOUS_RELEASE" "$RELEASE_BASE/current"
  ln -sfn "$PREVIOUS_RELEASE" /srv/src/distro_event_tracker
}

if ! start_and_verify_bots "$RELEASE_SHA"; then
  deploy_status=1
  if (( AUTO_ROLLBACK )); then
    if rollback_both_bots; then
      echo "Deployment $RELEASE_SHA failed; both bots were restored to $PREVIOUS_SHA." >&2
    else
      echo "Deployment $RELEASE_SHA failed and automatic rollback also failed." >&2
    fi
  fi
  exit "$deploy_status"
fi

ln -sfn "$ROOT_DIR" "$RELEASE_BASE/current"
ln -sfn "$ROOT_DIR" /srv/src/distro_event_tracker

mapfile -t releases < <(
  find "$RELEASE_BASE" -mindepth 1 -maxdepth 1 -type d -name '[0-9a-f]*' -printf '%T@ %p\n' \
    | sort -rn \
    | awk '{print $2}'
)
if (( ${#releases[@]} > 5 )); then
  for old_release in "${releases[@]:5}"; do
    case "$old_release" in
      "$RELEASE_BASE"/[0-9a-f][0-9a-f]*) rm -rf -- "$old_release" ;;
      *) echo "Refusing to remove unexpected release path: $old_release" >&2; exit 1 ;;
    esac
  done
fi

mapfile -t retained_tags < <(
  for release in "${releases[@]:0:5}"; do
    basename "$release" | cut -c1-12 | sed 's/^/git-/'
  done
)
while IFS= read -r image; do
  tag="${image##*:}"
  if [[ "$tag" == git-* ]] && [[ ! " ${retained_tags[*]} " =~ " $tag " ]]; then
    podman image rm "$image" >/dev/null 2>&1 || true
  fi
done < <(podman images --format '{{.Repository}}:{{.Tag}}' | grep '^localhost/distro-event-tracker:git-' || true)
podman image prune --force >/dev/null

echo "Deployed $RELEASE_SHA as $IMAGE to both rootless Podman services."
