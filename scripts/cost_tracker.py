#!/usr/bin/env python3
"""
cost_tracker.py — Track Anthropic API spend for /cost command
Logs every Claude API call with model, tokens, estimated cost.
Supports daily and weekly rollups.
Hard cap: $5.00/week | Alert at: $4.50 (90%)
"""

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ─── Config ────────────────────────────────────────────────
COST_LOG = Path("/home/ubuntu/.openclaw/workspace/logs/api_costs.jsonl")
WEEKLY_CAP = 5.00
ALERT_THRESHOLD = 4.50

# Anthropic pricing (per 1M tokens, as of March 2026 — update if pricing changes)
PRICING = {
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-opus-4-20250514":   {"input": 15.00, "output": 75.00},
    # fallback for unknown claude models
    "default":                  {"input": 3.00, "output": 15.00},
}

# ─── Log a single API call ─────────────────────────────────
def log_api_call(model: str, input_tokens: int, output_tokens: int, purpose: str = ""):
    """Call this every time the Smart Router hits Anthropic API."""
    COST_LOG.parent.mkdir(parents=True, exist_ok=True)

    pricing = PRICING.get(model, PRICING["default"])
    cost = (input_tokens / 1_000_000 * pricing["input"]) + \
           (output_tokens / 1_000_000 * pricing["output"])

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": round(cost, 6),
        "purpose": purpose
    }

    with open(COST_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")

    # Check caps after every write
    _check_caps()
    return cost

# ─── Read all entries ──────────────────────────────────────
def _read_entries():
    if not COST_LOG.exists():
        return []
    entries = []
    with open(COST_LOG) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except Exception:
                    pass
    return entries

# ─── Rollup helpers ────────────────────────────────────────
def _today_utc():
    return datetime.now(timezone.utc).date()

def get_daily_spend():
    today = _today_utc().isoformat()
    entries = [e for e in _read_entries() if e["ts"].startswith(today)]
    return round(sum(e["cost_usd"] for e in entries), 4)

def get_weekly_spend():
    now = datetime.now(timezone.utc)
    week_start = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    entries = [
        e for e in _read_entries()
        if datetime.fromisoformat(e["ts"]) >= week_start
    ]
    return round(sum(e["cost_usd"] for e in entries), 4)

def get_model_breakdown(period="weekly"):
    now = datetime.now(timezone.utc)
    if period == "weekly":
        week_start = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        entries = [
            e for e in _read_entries()
            if datetime.fromisoformat(e["ts"]) >= week_start
        ]
    else:
        today = _today_utc().isoformat()
        entries = [e for e in _read_entries() if e["ts"].startswith(today)]

    breakdown = {}
    for e in entries:
        m = e["model"]
        if m not in breakdown:
            breakdown[m] = {"calls": 0, "cost": 0.0}
        breakdown[m]["calls"] += 1
        breakdown[m]["cost"] += e["cost_usd"]

    return {m: {"calls": v["calls"], "cost": round(v["cost"], 4)}
            for m, v in breakdown.items()}

# ─── Cap checking ──────────────────────────────────────────
def _check_caps():
    """Returns alert string if over threshold, None if safe."""
    weekly = get_weekly_spend()
    if weekly >= WEEKLY_CAP:
        return "HARD_CAP"
    if weekly >= ALERT_THRESHOLD:
        return "ALERT"
    return None

def is_over_cap():
    """True if weekly spend >= hard cap. Router uses this to fallback to Kimi."""
    return get_weekly_spend() >= WEEKLY_CAP

# ─── /cost Telegram response ───────────────────────────────
def format_cost_report():
    """Returns the Telegram message for /cost command."""
    daily = get_daily_spend()
    weekly = get_weekly_spend()
    pct = round((weekly / WEEKLY_CAP) * 100, 1)
    breakdown = get_model_breakdown("weekly")

    # Bar indicator
    filled = int(pct / 10)
    bar = "█" * filled + "░" * (10 - filled)

    status = "✅ Safe"
    if weekly >= WEEKLY_CAP:
        status = "🚨 HARD CAP HIT — Kimi-only mode"
    elif weekly >= ALERT_THRESHOLD:
        status = "⚠️ Alert threshold crossed"

    lines = [
        "💰 *API Cost Report*",
        "",
        f"📅 Today: `${daily:.4f}`",
        f"📆 This week: `${weekly:.4f}` / `${WEEKLY_CAP:.2f}`",
        f"[{bar}] {pct}%",
        f"Status: {status}",
        "",
        "📊 *Weekly by model:*"
    ]

    if breakdown:
        for model, data in sorted(breakdown.items(), key=lambda x: -x[1]["cost"]):
            short = model.split("/")[-1]
            lines.append(f"  • {short}: {data['calls']} calls → `${data['cost']:.4f}`")
    else:
        lines.append("  No Claude API calls this week")

    lines += [
        "",
        f"Cap: ${WEEKLY_CAP}/wk | Alert: ${ALERT_THRESHOLD}/wk"
    ]

    return "\n".join(lines)

# ─── CLI / manual test ─────────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Log some dummy calls for testing
        log_api_call("claude-sonnet-4-20250514", 500, 300, "whale_signal_test")
        log_api_call("claude-sonnet-4-20250514", 800, 400, "market_analysis_test")
        log_api_call("claude-opus-4-20250514", 200, 100, "critical_edge_case_test")
        print("Logged 3 test entries")

    print(format_cost_report())
    print(f"\nOver cap: {is_over_cap()}")
