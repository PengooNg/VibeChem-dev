#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# scripts/uv_sync.sh
# Install the Python workspace from uv.lock (CI, installers, developer setup).
#
#     bash scripts/uv_sync.sh [extra uv sync arguments]
#
# macOS (BUG #84, R67, decision by Quan: A): NumPy/SciPy on Accelerate give bits that depend on
# the thread count and on the data's memory alignment, so bit-identity cannot hold. Targeting
# macOS 13 makes uv install the wheels that bundle OpenBLAS (macosx_10_15_x86_64,
# macosx_11_0/12_0_arm64). A later plain `uv run` may sync back to the Accelerate wheels, so on
# GitHub Actions UV_NO_SYNC=1 is set for the following steps; locally use `uv run --no-sync`.
set -euo pipefail

if [ "$(uname -s)" != Darwin ]; then
  exec uv sync --locked "$@"
fi

arch=$(uname -m)
if [ "$arch" = arm64 ]; then arch=aarch64; fi
MACOSX_DEPLOYMENT_TARGET=13.0 uv sync --locked --python-platform "$arch-apple-darwin" "$@"

# Fail here, not later in a bit-identity test, if Accelerate came back.
uv run --no-sync python -c '
import numpy, scipy
for lib in (numpy, scipy):
    blas = lib.show_config(mode="dicts")["Build Dependencies"]["blas"]["name"]
    assert "openblas" in blas.lower(), f"{lib.__name__} BLAS is {blas}, expected OpenBLAS (BUG #84)"
    print(f"{lib.__name__} {lib.__version__}: BLAS {blas}")
'

if [ -n "${GITHUB_ENV:-}" ]; then
  echo "UV_NO_SYNC=1" >> "$GITHUB_ENV"
fi
