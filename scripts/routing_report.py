#!/usr/bin/env python3
"""
routing_report.py — /routing Telegram command
Reads logs/routing.log and returns tier distribution stats.
"""
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict

LOG_FILE = Path('/home/ubuntu/.openclaw/workspace/logs/routing.log')


def format_routing_report() -> str:
    if not LOG_FILE.exists():
        return "📊 No routing data yet — shadow monitor not started."

    entries = []
    with open(LOG_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
                if 'router_tier' in e:
                    entries.append(e)
            except Exception:
                continue

    if not entries:
        return "📊 Shadow monitor running but no messages observed yet."

    # Count tiers
    tier_counts = defaultdict(int)
    match_count = 0
    guardrail_count = 0
    total = len(entries)

    # Last 24h entries
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    recent = []

    for e in entries:
        tier_counts[e.get('router_tier', 'unknown')] += 1
        if e.get('match'):
            match_count += 1
        if e.get('trading_guardrail'):
            guardrail_count += 1
        try:
            ts = datetime.fromisoformat(e['ts'])
            if ts >= cutoff:
                recent.append(e)
        except Exception:
            pass

    # Cost savings estimate
    # Assumption: Gemma = $0, Kimi = $0, Sonnet = ~$0.01/msg avg
    sonnet_count = tier_counts.get('high', 0)
    gemma_count = tier_counts.get('simple', 0)
    kimi_count = tier_counts.get('medium', 0)
    # If everything had gone to Sonnet
    hypothetical_cost = total * 0.01
    actual_cost = sonnet_count * 0.01
    saved = hypothetical_cost - actual_cost
    savings_pct = round((saved / hypothetical_cost * 100) if hypothetical_cost > 0 else 0, 1)

    # Build report
    lines = [
        "📊 *Smart Router Report*",
        "",
        f"🔢 Total messages observed: `{total}`",
        f"📅 Last 24h: `{len(recent)}`",
        "",
        "📈 *Tier Distribution:*",
        f"  🟢 Gemma (free):  `{gemma_count}` ({round(gemma_count/total*100) if total else 0}%)",
        f"  🔵 Kimi (free):   `{kimi_count}` ({round(kimi_count/total*100) if total else 0}%)",
        f"  🟡 Sonnet (paid): `{sonnet_count}` ({round(sonnet_count/total*100) if total else 0}%)",
        "",
        f"🛡️ Trading guardrail fired: `{guardrail_count}` times",
        f"✅ Router match rate: `{round(match_count/total*100) if total else 0}%`",
        f"💰 Est. savings vs all-Sonnet: `{savings_pct}%`",
    ]

    # Recent messages sample (last 3)
    if recent:
        lines += ["", "🕐 *Last 3 messages:*"]
        for e in recent[-3:]:
            tier_emoji = {'simple': '🟢', 'medium': '🔵', 'high': '🟡'}.get(e.get('router_tier'), '⚪')
            snippet = e.get('msg_snippet', '')[:35]
            lines.append(f"  {tier_emoji} {e.get('router_tier','?')} | {snippet!r}")

    return "\n".join(lines)


if __name__ == "__main__":
    print(format_routing_report())
