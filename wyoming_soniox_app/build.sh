#!/bin/sh
# Assemble the app's build context (app files + package source) into wyoming_soniox_app/.build/wyoming_soniox.
# CI builds the published image from it; copied to /local_apps on HA it is a local app that the Supervisor
# builds itself (the staged config.yaml has no "image:", so nothing is pulled from ghcr).
# Usage: wyoming_soniox_app/build.sh   -> prints the staging dir
set -eu
ROOT=$(cd "$(dirname "$0")/.." && pwd)
APP="$ROOT/wyoming_soniox_app"
STAGE="$APP/.build/wyoming_soniox"
rm -rf "$STAGE" && mkdir -p "$STAGE/src/src"
for f in build.yaml Dockerfile run.sh DOCS.md README.md CHANGELOG.md translations icon.png logo.png; do
    cp -R "$APP/$f" "$STAGE/"
done
grep -v '^image:' "$APP/config.yaml" > "$STAGE/config.yaml"
cp "$ROOT/pyproject.toml" "$ROOT/uv.lock" "$ROOT/README.md" "$ROOT/LICENSE" "$STAGE/src/"
tar -C "$ROOT/src" --exclude __pycache__ -cf - wyoming_soniox | tar -C "$STAGE/src/src" -xf -
echo "$STAGE"
