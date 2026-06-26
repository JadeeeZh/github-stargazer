#!/usr/bin/env bash
# Convenience wrapper. Equivalent to `python app.py run ...`.
#   ./run.sh OWNER/REPO [--icp <id>] [--token T] [...]
set -euo pipefail
cd "$(dirname "$0")"
exec python3 app.py run "$@"
