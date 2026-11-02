#!/bin/sh
# Assemble a local build context (app files + package source) into wyoming_soniox_app/.build/wyoming_soniox.
# With the package source present the Dockerfile installs it instead of the published git tag.
# Usage: wyoming_soniox_app/build.sh   -> prints the staging dir
set -eu
ROOT=$(cd "$(dirname "$0")/.." && pwd)
STAGE="$ROOT/wyoming_soniox_app/.build/wyoming_soniox"
rm -rf "$STAGE" && mkdir -p "$STAGE/src"
for f in config.yaml build.yaml Dockerfile run.sh DOCS.md translations; do
    cp -R "$ROOT/wyoming_soniox_app/$f" "$STAGE/"
done
cp "$ROOT/pyproject.toml" "$ROOT/README.md" "$ROOT/LICENSE" "$STAGE/src/"
mkdir -p "$STAGE/src/src"
tar -C "$ROOT/src" --exclude __pycache__ -cf - wyoming_soniox | tar -C "$STAGE/src/src" -xf -
echo "$STAGE"
