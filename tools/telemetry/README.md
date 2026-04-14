# Live telemetry tooling

Read-only post-mortem tools. Does NOT touch the live system.

## What's here

- `pull.sh` — SSH into Lightsail and snapshot the four live files (`service.log`, `events.jsonl`, `state.json`, `live_alerts.jsonl`) into `data/<UTC-timestamp>/`.
- `report.py` — parse a snapshot and emit a markdown health report.
- `data/` — snapshots (gitignored).

## Usage

### One-shot (most common)

```bash
bash tools/telemetry/check.sh
```

Pulls a fresh snapshot and prints the report in one go.

### Step-by-step

```bash
# Pull snapshot (B_balanced_3x by default)
bash tools/telemetry/pull.sh

# Report against latest snapshot
python tools/telemetry/report.py --latest

# Or against a specific snapshot
python tools/telemetry/report.py tools/telemetry/data/20260414T064000Z

# Write to file instead of stdout
python tools/telemetry/report.py --latest -o report.md
```

## Environment (optional overrides)

- `LIVE_HOST` — ssh target (default `ubuntu@13.209.14.27`)
- `LIVE_KEY`  — ssh identity file (default research-archive's `.claude/btctrading.pem`)
- `LIVE_ROOT` — remote repo root (default `/home/ubuntu/btc-strategy-v2`)

## What the report covers (Phase 1)

- Service health: restart count, server-time offset drift
- Bar processing: expected vs processed, missed bars, duplicates, polling lag
- Reconciliation: halt events, exchange/internal state divergence
- Current position state snapshot
- Alerts

## What's NOT here yet (Phase 2 — blocked on trade data)

- Slippage vs backtest divergence — needs executed trades
- Funding cost actual vs assumed — needs held positions
- Fill-quality analysis — needs order fills

These will be added once `trade_count > 0`.
