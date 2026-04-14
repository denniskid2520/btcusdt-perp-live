# btcusdt-perp-live

BTC/USDT perpetual futures live trading system.

**Active strategy: B_balanced_3x** - 4h RSI(20) regime gate + 1h hybrid pullback/breakout execution, dual-stop architecture, 3x isolated leverage.

## Backtest Performance (6 years, 2020-2026)

| Metric | Value |
|--------|-------|
| Trades | 150 |
| Win Rate | 69.3% |
| Profit Factor | 4.63 |
| Max Drawdown | 12.7% |
| Simple Return | +565.6% |
| Compound Return | +18,394% |

Validated with walk-forward (8 OOS windows, 24m train / 6m test), 6,427 parameter combinations tested.

## Quick Start

```bash
# Install (dev mode with pytest)
pip install -e .[dev]

# Run tests
pytest

# Dry-run (reads real data, no orders)
PYTHONPATH=src python -m execution.live_service --dry-run

# Live (micro-live with $10K cap)
cp .env.example .env  # add Binance API keys
PYTHONPATH=src python -m execution.live_service --max-cap 10000
```

## Architecture

```
live_service.py          Main service: 10s poll loop, bar-close triggered
  |-- live_executor.py   Binance API: signed requests, order placement, position queries
  |-- paper_runner_v2.py Strategy state machine: regime gate, entry/exit signals, stops
  |-- adapters/base.py   MarketBar dataclass
```

### Execution Flow
1. Poll Binance klines every 10s for completed 1h bars
2. Feed bar to `paper_runner_v2` (strategy state machine)
3. If 4h RSI(20) > 70 -> regime activates, start looking for entries
4. Hybrid entry: pullback -0.75% OR breakout +0.25% from zone high
5. Dual stop: alpha 1.25% (client-side close-check) + catastrophe 2.5% (exchange STOP_MARKET)
6. Hold 24 bars max, exit on stop or time

### Safety System (27+ fixes, 3 review rounds)
- Dual stop: strategy stop + exchange catastrophe STOP_MARKET (reduceOnly)
- Exit protection: catastrophe stop preserved until SELL confirmed FILLED
- Idempotent entry: newClientOrderId + query-on-timeout
- Position verify: 3x retry after exit, HALT if unverifiable
- recvWindow + server-time offset: prevents timestamp rejects
- 68 automated safety tests

## File Manifest

| File | Role |
|------|------|
| `src/execution/live_service.py` | Main live service (bar-close polling loop) |
| `src/execution/live_executor.py` | Binance API helpers, deployment configs, order placement |
| `src/execution/paper_runner_v2.py` | Strategy state machine (CandidateConfig, RSI regime, entries/exits) |
| `src/execution/live_paper_cron.py` | Cron-based paper runner (hourly, for shadow candidates) |
| `src/execution/weekly_reconciliation.py` | Weekly state consistency check |
| `src/adapters/base.py` | MarketBar dataclass |
| `tests/test_live_service_fixes.py` | 58 safety regression tests |
| `tests/test_paper_runner_v2.py` | 10 state machine tests |
| `deploy_lightsail.sh` | AWS Lightsail deployment script |
| `ACTIVE_STRATEGY.md` | Source of truth for live config |

## Deployment (AWS Lightsail)

```bash
# Deploy to Lightsail
bash deploy_lightsail.sh

# Or manually:
scp -i KEY src/execution/*.py ubuntu@HOST:/home/ubuntu/btc-strategy-v2/src/execution/
ssh -i KEY ubuntu@HOST "screen -S live_3x -X quit; cd btc-strategy-v2 && screen -dmS live_3x bash -c 'PYTHONPATH=src python3 -m execution.live_service --max-cap 10000 >> logs/live_3x.log 2>&1'"
```

## Dependencies

**Zero pip dependencies** for production runtime. Pure Python 3.11+ stdlib.

Only `pytest` needed for running tests (dev dependency).

## Research Archive

Full research history (18 phases, 6,427 parameter sweeps, legacy strategies) preserved at:
[btcusdt-research-archive](https://github.com/denniskid2520/btcusdt-research-archive)
