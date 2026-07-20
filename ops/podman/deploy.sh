#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: deploy.sh <full-commit-sha> [--dry-run]" >&2
  exit 2
fi

RELEASE_SHA="$1"
MODE="${2:-apply}"
if [[ ! "$RELEASE_SHA" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Release revision must be a full lowercase Git SHA." >&2
  exit 2
fi
if [[ "$MODE" != "apply" && "$MODE" != "--dry-run" ]]; then
  echo "Second argument must be --dry-run when supplied." >&2
  exit 2
fi

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

for instance in distro ocean; do
  systemctl --user restart "$(service_name "$instance")"
  wait_for_bot "$instance"
  verify_bot_revision "$instance" "$RELEASE_SHA"
done

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

echo "Deployed $RELEASE_SHA as $IMAGE to both rootless Podman services."
