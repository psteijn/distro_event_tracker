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

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RELEASE_BASE="/srv/releases/distro-event-tracker"
IMAGE_TAG="git-${RELEASE_SHA:0:12}"
IMAGE="localhost/distro-event-tracker:${IMAGE_TAG}"
RENDER_DIR="$(mktemp -d)"
trap 'rm -rf -- "$RENDER_DIR"' EXIT

command -v podman >/dev/null || { echo "podman is required" >&2; exit 1; }
command -v microk8s >/dev/null || { echo "microk8s is required" >&2; exit 1; }
[[ -f "$ROOT_DIR/.release-revision" ]] || { echo "Missing release metadata." >&2; exit 1; }
[[ "$(tr -d '\r\n' < "$ROOT_DIR/.release-revision")" == "$RELEASE_SHA" ]] || {
  echo "Release metadata does not match requested revision." >&2
  exit 1
}

for instance in distro ocean; do
  secret="distro-event-tracker-${instance}"
  microk8s kubectl -n distro-event-tracker get secret "$secret" >/dev/null 2>&1 || {
    echo "Missing Kubernetes secret ${secret}; synchronize secrets first." >&2
    exit 1
  }
done

cp -R "$ROOT_DIR/ops/k8s/." "$RENDER_DIR/"
sed -i \
  -e "s/RELEASE_TAG/${IMAGE_TAG}/g" \
  -e "s/RELEASE_SHA/${RELEASE_SHA}/g" \
  "$RENDER_DIR/deployments.yaml"

microk8s kubectl apply -k "$RENDER_DIR" --dry-run=server >/dev/null
set +e
microk8s kubectl diff -k "$RENDER_DIR"
diff_status=$?
set -e
if (( diff_status > 1 )); then
  echo "Kubernetes diff failed." >&2
  exit "$diff_status"
fi

if [[ "$MODE" == "--dry-run" ]]; then
  echo "Dry run complete for ${RELEASE_SHA}; no resources changed."
  exit 0
fi

podman build --pull=never --build-arg "VCS_REF=${RELEASE_SHA}" -t "$IMAGE" "$ROOT_DIR"
podman save "$IMAGE" | microk8s ctr image import -
microk8s kubectl apply -k "$RENDER_DIR"
microk8s kubectl -n distro-event-tracker rollout status deployment/distro-event-tracker-distro --timeout=600s
microk8s kubectl -n distro-event-tracker rollout status deployment/distro-event-tracker-ocean --timeout=600s

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

microk8s kubectl -n distro-event-tracker get pods -o wide
echo "Deployed ${RELEASE_SHA} as ${IMAGE}."
