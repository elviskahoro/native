#!/usr/bin/env bash
# Run a CI check locally or in RWX: ci/run.sh {pyright|pyrefly|all} [paths...]
# Needs Docker and the dagger CLI (0.21.8) on PATH, plus uv.
set -euo pipefail
cd "$(dirname "$0")/.."
exec dagger run uv run --project ci python ci/main.py "$@"
