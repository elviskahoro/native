#!/usr/bin/env bash
# Vercel installCommand: the build image's uv can't fetch the Python we need,
# so install a checksum-pinned uv and sync with Python 3.12 (what CI tests).
set -euo pipefail

installer="$(mktemp)"
trap 'rm -f "${installer}"' EXIT
curl -LsSf https://astral.sh/uv/0.11.29/install.sh -o "${installer}"
echo "504a79fd2ed0dcd47e7f04f0792cfd0871f62e24a7fe40fa8ae0f563a369f2bd  ${installer}" | sha256sum -c -
UV_INSTALL_DIR="${PWD}/.uvbin" UV_NO_MODIFY_PATH=1 sh "${installer}"

export UV_PYTHON_DOWNLOADS=automatic UV_PYTHON=3.12
.uvbin/uv python install 3.12
.uvbin/uv sync
