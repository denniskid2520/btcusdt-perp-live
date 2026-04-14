#!/usr/bin/env bash
# One-shot: pull latest snapshot + print health report.
# Usage: bash tools/telemetry/check.sh [candidate]
#   candidate defaults to B_balanced_3x
#
# From anywhere in the repo (or outside it), this script always operates
# relative to its own location, so double-clicking also works.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CANDIDATE="${1:-B_balanced_3x}"

bash "$SCRIPT_DIR/pull.sh" "$CANDIDATE"
echo
echo "============================================================"
echo
python "$SCRIPT_DIR/report.py" --latest
