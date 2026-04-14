#!/usr/bin/env bash
# Pull live telemetry snapshot from Lightsail into tools/telemetry/data/<UTC-timestamp>/
# Usage: bash tools/telemetry/pull.sh [candidate]
#   candidate defaults to B_balanced_3x

set -euo pipefail

CANDIDATE="${1:-B_balanced_3x}"
HOST="${LIVE_HOST:-ubuntu@13.209.14.27}"
KEY="${LIVE_KEY:-C:/Users/User/Documents/btcusdt-research-archive/.claude/btctrading.pem}"
REMOTE_ROOT="${LIVE_ROOT:-/home/ubuntu/btc-strategy-v2}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$SCRIPT_DIR/data/$STAMP"
mkdir -p "$OUT"

echo "[pull] candidate=$CANDIDATE host=$HOST"
echo "[pull] snapshot → $OUT"

scp -i "$KEY" -o StrictHostKeyChecking=no \
  "$HOST:$REMOTE_ROOT/data/live_state/$CANDIDATE/service.log" \
  "$HOST:$REMOTE_ROOT/data/live_state/$CANDIDATE/events.jsonl" \
  "$HOST:$REMOTE_ROOT/data/live_state/$CANDIDATE/state.json" \
  "$OUT/" 2>/dev/null || echo "[pull] warn: one or more live_state files missing"

# alerts may not exist yet
scp -i "$KEY" -o StrictHostKeyChecking=no \
  "$HOST:$REMOTE_ROOT/logs/live_alerts.jsonl" \
  "$OUT/" 2>/dev/null || echo "[pull] note: no live_alerts.jsonl (expected if no alerts fired)"

# metadata
{
  echo "pulled_at_utc=$STAMP"
  echo "candidate=$CANDIDATE"
  echo "host=$HOST"
} > "$OUT/meta.txt"

echo "[pull] done"
echo "$OUT"
