"""
Live telemetry report — parse a snapshot from tools/telemetry/data/<stamp>/
and emit a markdown health report to stdout.

Usage:
    python tools/telemetry/report.py tools/telemetry/data/<stamp>
    python tools/telemetry/report.py --latest
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

TS_RE = re.compile(r"\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+)\]\s*(.*)")
BAR_RE = re.compile(
    r"bar (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"O=([\d.]+) H=([\d.]+) L=([\d.]+) C=([\d.]+)"
)
SERVICE_START_RE = re.compile(r"=== Phase \d+ .* service starting ===")
SERVER_TIME_RE = re.compile(r"Server-time offset: (-?\d+)ms")


def parse_service_log(path: Path):
    """Return list of (ts, message) tuples."""
    events = []
    if not path.exists():
        return events
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = TS_RE.match(line)
        if not m:
            continue
        try:
            ts = datetime.fromisoformat(m.group(1)).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        events.append((ts, m.group(2)))
    return events


def parse_events_jsonl(path: Path):
    out = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def load_state(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def expected_bars(first: datetime, last: datetime) -> int:
    """Hourly bars from floor(first) to floor(last), inclusive."""
    def floor_hour(dt: datetime) -> datetime:
        return dt.replace(minute=0, second=0, microsecond=0)
    hrs = int((floor_hour(last) - floor_hour(first)).total_seconds() // 3600) + 1
    return max(hrs, 0)


def fmt_ts(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%d %H:%M:%SZ")


def build_report(snapshot: Path) -> str:
    meta = {}
    meta_path = snapshot / "meta.txt"
    if meta_path.exists():
        for line in meta_path.read_text(encoding="utf-8").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                meta[k.strip()] = v.strip()

    log_events = parse_service_log(snapshot / "service.log")
    recons = parse_events_jsonl(snapshot / "events.jsonl")
    alerts = parse_events_jsonl(snapshot / "live_alerts.jsonl")
    state = load_state(snapshot / "state.json")

    lines: list[str] = []
    out = lines.append

    out(f"# Live telemetry report — {meta.get('candidate', 'unknown')}")
    out("")
    out(f"- **Snapshot**: `{snapshot.name}` (pulled {meta.get('pulled_at_utc', '?')})")
    out(f"- **Host**: {meta.get('host', '?')}")
    out("")

    # === SECTION: Service health ===
    out("## Service health")
    out("")
    starts = [ts for ts, msg in log_events if SERVICE_START_RE.search(msg)]
    out(f"- **Service-start events**: {len(starts)}")
    if starts:
        out(f"  - First: {fmt_ts(starts[0])}")
        out(f"  - Last:  {fmt_ts(starts[-1])}")
        if len(starts) > 1:
            gaps = [(starts[i] - starts[i-1]).total_seconds() / 3600 for i in range(1, len(starts))]
            out(f"  - Restarts clustered: min gap {min(gaps):.2f}h, max gap {max(gaps):.2f}h")

    offsets = [int(m.group(1)) for _, msg in log_events if (m := SERVER_TIME_RE.search(msg))]
    if offsets:
        out(f"- **Server-time offset (ms)**: last={offsets[-1]}, "
            f"min={min(offsets)}, max={max(offsets)}, samples={len(offsets)}")
        if max(abs(o) for o in offsets) > 500:
            out("  - ⚠ offset > 500ms at some point — investigate clock drift")
    out("")

    # === SECTION: Bar processing ===
    out("## Bar processing (1h polling)")
    out("")
    bars = []
    for ts, msg in log_events:
        m = BAR_RE.search(msg)
        if m:
            bar_ts = datetime.fromisoformat(m.group(1)).replace(tzinfo=timezone.utc)
            bars.append((ts, bar_ts, float(m.group(5))))
    if bars:
        first_bar = bars[0][1]
        last_bar = bars[-1][1]
        processed = len({b[1] for b in bars})  # dedupe
        expected = expected_bars(first_bar, last_bar)
        missed = expected - processed
        out(f"- **Bars processed**: {processed} (expected {expected} between "
            f"{fmt_ts(first_bar)} → {fmt_ts(last_bar)})")
        out(f"- **Missed bars**: {missed} "
            f"{'✅' if missed == 0 else '⚠ investigate catch-up logic'}")
        dup = len(bars) - processed
        out(f"- **Duplicate-bar entries**: {dup} "
            f"{'✅ deduped' if dup == 0 else '(re-logs on restart — OK if matches restarts)'}")
        out(f"- **Last close**: ${bars[-1][2]:,.2f} at bar {fmt_ts(bars[-1][1])}")

        # lag-after-close: bar labeled HH:00 closes at HH+1:00; wall-time log should be seconds after that.
        lags = [(wall - bar).total_seconds() - 3600 for wall, bar, _ in bars]
        lags_sorted = sorted(lags)
        out(f"- **Log lag after bar close**: median {lags_sorted[len(lags)//2]:.1f}s, "
            f"max {max(lags):.1f}s (should be <30s on a healthy 10s poller)")
    else:
        out("- No bar events found in service.log")
    out("")

    # === SECTION: Reconciliation ===
    out("## Reconciliation (hourly position check)")
    out("")
    if recons:
        out(f"- **Total reconciliation events**: {len(recons)}")
        halted = [r for r in recons if r.get("halted")]
        out(f"- **Halted events**: {len(halted)} "
            f"{'✅' if not halted else '⚠ HALT seen — check halt_reason'}")
        divergent = [
            r for r in recons
            if r.get("has_exchange_pos") != r.get("internal_has_pos")
        ]
        out(f"- **Exchange/internal state divergence**: {len(divergent)} "
            f"{'✅' if not divergent else '⚠ divergence — STOP and investigate'}")
        with_pos = sum(1 for r in recons if r.get("has_exchange_pos"))
        out(f"- **Events with live position**: {with_pos}")
        first_rec = recons[0].get("ts", "?")
        last_rec = recons[-1].get("ts", "?")
        out(f"- **Window**: {first_rec} → {last_rec}")
    else:
        out("- No reconciliation events")
    out("")

    # === SECTION: Position state ===
    out("## Current position state")
    out("")
    if state:
        out(f"- position_state: `{state.get('position_state')}`")
        out(f"- regime_active: `{state.get('regime_active')}`")
        out(f"- trade_count: **{state.get('trade_count')}**")
        out(f"- has_live_position: `{state.get('has_live_position')}`")
        out(f"- halted: `{state.get('halted')}` "
            f"{'' if not state.get('halted') else '⚠ halt_reason=' + state.get('halt_reason', '')}")
        out(f"- bars_since_last_exit: {state.get('bars_since_last_exit')}")
    else:
        out("- No state.json snapshot")
    out("")

    # === SECTION: Alerts ===
    out("## Alerts")
    out("")
    if alerts:
        out(f"- **Alerts fired**: {len(alerts)}")
        for a in alerts[-10:]:
            out(f"  - `{a.get('ts', '?')}` {a.get('level', '?')}: {a.get('msg', a)}")
    else:
        out("- ✅ No alerts")
    out("")

    # === SECTION: Verdict ===
    out("## Verdict")
    out("")
    problems = []
    if alerts:
        problems.append(f"{len(alerts)} alerts")
    if recons:
        halted = [r for r in recons if r.get("halted")]
        if halted:
            problems.append(f"{len(halted)} halt events")
        div = [r for r in recons if r.get("has_exchange_pos") != r.get("internal_has_pos")]
        if div:
            problems.append(f"{len(div)} state divergence")
    if bars:
        first_bar = bars[0][1]
        last_bar = bars[-1][1]
        missed = expected_bars(first_bar, last_bar) - len({b[1] for b in bars})
        if missed > 0:
            problems.append(f"{missed} missed bars")
    if state and state.get("halted"):
        problems.append(f"CURRENTLY HALTED: {state.get('halt_reason')}")

    if not problems:
        out("✅ **HEALTHY** — no alerts, no halts, no state divergence, no missed bars.")
    else:
        out("⚠ **ISSUES**: " + "; ".join(problems))
    out("")

    return "\n".join(lines)


def find_latest(data_dir: Path) -> Path | None:
    if not data_dir.exists():
        return None
    snaps = sorted(p for p in data_dir.iterdir() if p.is_dir())
    return snaps[-1] if snaps else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", nargs="?", help="path to snapshot dir")
    parser.add_argument("--latest", action="store_true", help="use latest snapshot in data/")
    parser.add_argument("-o", "--output", help="write report to file instead of stdout")
    args = parser.parse_args()

    if args.latest or not args.snapshot:
        data_dir = Path(__file__).parent / "data"
        snap = find_latest(data_dir)
        if snap is None:
            print(f"no snapshots in {data_dir}")
            return 1
    else:
        snap = Path(args.snapshot)
        if not snap.exists():
            print(f"snapshot not found: {snap}")
            return 1

    report = build_report(snap)
    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"wrote {args.output}")
    else:
        # Windows console often defaults to cp950/cp1252; force utf-8 bytes.
        sys.stdout.buffer.write(report.encode("utf-8"))
        sys.stdout.buffer.write(b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
