#!/usr/bin/env bash
set -euo pipefail

# Exercise the exact directory HACS installs, with no pre-existing HA state.
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
config_dir="$(mktemp -d)"
container_name="neolight-hacs-smoke-$$"

cleanup() {
  docker rm -f "$container_name" >/dev/null 2>&1 || true
  # HA writes some files as root inside the mounted temporary config.
  docker run --rm -v "$config_dir:/config" --entrypoint chown \
    ghcr.io/home-assistant/home-assistant:stable \
    -R "$(id -u):$(id -g)" /config >/dev/null 2>&1 || true
  rm -rf "$config_dir"
}
trap cleanup EXIT

mkdir -p "$config_dir/custom_components"
cp -R "$repo_root/custom_components/neolight" "$config_dir/custom_components/"

docker run -d --name "$container_name" \
  -v "$config_dir:/config" \
  ghcr.io/home-assistant/home-assistant:stable >/dev/null

for attempt in $(seq 1 90); do
  if ! docker inspect -f '{{.State.Running}}' "$container_name" | grep -qx true; then
    docker logs "$container_name"
    echo "Home Assistant stopped during clean HACS installation" >&2
    exit 1
  fi
  if docker exec "$container_name" test -f /config/.HA_VERSION && \
     docker exec "$container_name" python -c \
       'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8123/", timeout=2)' \
       >/dev/null 2>&1; then
    break
  fi
  if [ "$attempt" -eq 90 ]; then
    docker logs "$container_name"
    echo "Home Assistant did not start within 180 seconds" >&2
    exit 1
  fi
  sleep 2
done

if docker logs "$container_name" 2>&1 | grep -Eiq \
  'Error setting up.*neolight|Unable to import component neolight|Failed to load integration: neolight'; then
  docker logs "$container_name"
  echo "NeoLight failed during clean HACS installation" >&2
  exit 1
fi

echo "Clean HACS install started on Home Assistant $(docker exec "$container_name" cat /config/.HA_VERSION)"
