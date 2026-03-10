# Phase 6 — Swarm Detection (Multi-Wallet Coordinated Entry)
**Status: DRAFT — DO NOT BUILD YET**
**Gate: Build only after paper trading hits 50-60% win rate consistently**
**Created: 2026-03-10 | Author: Ankur + Claude + Gemini (3-LLM brainstorm)**

---

## Why This Exists

Idea originated from a brainstorming session between Ankur, Claude, and Gemini on 2026-03-10.

Gemini's core observation (validated as correct):
> "Real smart money rarely drops $100k in one transaction because it causes
> slippage. Instead, they split that $100k into twenty $5k trades across
> multiple wallets. If your whale_tracker only looks for single $500+ trades,
> you might miss a $20,000 stealth move broken into $400 chunks."

This is a well-documented institutional trading pattern. Phase 6 closes this gap.

---

## The Gap in Current System

| Detection Layer | What It Catches | What It Misses |
|---|---|---|
| Phase 1 - Single Trade | One wallet, one big trade | Stealth split trades |
| Phase 2 - Accumulation | One wallet, many small trades | DIFFERENT wallets coordinating |
| Phase 3 - Liq Shock | Pool liquidity drop | Source of drain |
| Phase 4 - Wallet Intel | Known smart wallets | Unknown coordinated group |
| Phase 5 - Order Book | Ask-side thinning pre-whale | (not built yet) |
| **Phase 6 - Swarm** | **Multiple wallets, same direction, short window** | (fills the gap) |

Phase 2 groups by SAME wallet. Phase 6 groups by SAME MARKET across DIFFERENT wallets.
They are complementary signals, not duplicates.

---

## Signal Logic

### Name: COORDINATED ENTRY

### Core Algorithm

```
find_swarm_activity(trades, market_id, window_minutes=10):

  1. Filter trades to last SWARM_WINDOW seconds
  2. Group by proxyWallet (unique wallets only)
  3. Check conditions:
     - unique_wallet_count >= SWARM_MIN_WALLETS (3)
     - total_usd_combined >= SWARM_MIN_TOTAL ($2,500)
     - all trades same direction (all YES or all NO)
     - no single wallet > SWARM_DOMINANCE_PCT (60%) of total volume
       (above 60% = Phase 2 territory, skip swarm label to avoid double-fire)
  4. If all conditions met -> SWARM DETECTED

Returns:
  {
    "type": "swarm",
    "wallet_count": 4,
    "total_usd": 3200.00,
    "direction": "YES",
    "window_seconds": 480,
    "dominant_wallet_pct": 28.5,
    "wallets": ["0xabc...", "0xdef...", ...]
  }
```

### Parameters (to tune after Phase 5 is stable)

```python
SWARM_WINDOW        = 600    # 10 minutes in seconds
SWARM_MIN_WALLETS   = 3      # minimum unique wallets
SWARM_MIN_TOTAL     = 2500   # combined USDC across all wallets
SWARM_DOMINANCE_PCT = 0.60   # single wallet cap (above = Phase 2 territory)
```

### Signal Tier Mapping

```
Swarm alone (no Phase 1/2 backing)     -> TIER 2 (COORDINATED ENTRY)
Swarm + Phase 1 or Phase 2             -> TIER 1 (SMART MONEY CONVERGENCE)
Swarm + Phase 1 + Phase 3 shock        -> EXTREME (FULL CONFLUENCE)
Swarm + Phase 5 thinning (pre-signal)  -> EXTREME++ (maximum conviction)
```

### Telegram Output Format

```
COORDINATED ENTRY DETECTED
Market: [name]
Direction: YES / NO
Wallets: 4 unique addresses
Combined: $3,200 in 8 minutes
Largest single wallet: 28.5% of total

Signal: TIER 1 -- SMART MONEY CONVERGENCE
[YES - Execute Trade] [NO - Skip]
```

---

## Implementation Notes

### Where It Lives
New function in: scripts/whale_tracker.py (alongside find_whale_clusters)
Called after: find_whale_clusters() in the per-market scan loop
New persistent file: paper_trading/swarm_history.json
Pattern: same atomic-write pattern as liquidity_history.json

### What NOT to Build (Gemini suggested, we decided against)
- Funding source tracking via Polygonscan/Arkham API
  Reason: External API dependency, rate limits, added latency, overkill
  Temporal clustering alone is sufficient without on-chain tracing
- Redis buffer
  Reason: JSON-based persistent state pattern already proven, no new infra needed

### Deduplication Guard (Critical)
Swarm and Phase 2 must not double-fire on the same event.
Guard: if swarm dominant_wallet_pct > 60%, classify as Phase 2 cluster only.
This prevents inflated signal tier from counting same activity twice.

### Performance
Swarm detection runs on the same trades[] array already fetched per market.
Zero additional API calls required. Negligible compute overhead.

---

## Gate Conditions Before Building (ALL must be true)

1. Paper trading win rate >= 50% over minimum 10 resolved trades
2. Phase 5 (order book thinning) is built, tested, and stable for 2+ weeks
3. Whale tracker cron upgraded from 2hr to 30min intervals
4. At least one real-money profitable trade logged

Rationale: Adding signal complexity to an unproven stack creates noise not edge.
Prove the foundation delivers alpha first. Then layer in swarm detection.

---

## Decision Log

- 2026-03-10: Brainstorm session — Ankur + Claude + Gemini
- Gemini introduced the "stealth whale" / "school of piranhas" framing
- Claude validated the gap vs Phase 2, added dominance guard, recommended JSON over Redis
- Decision: DRAFT and HOLD. Do not build until 50-60% success rate gate is cleared.
- Placed in: docs/PHASE6_SWARM_DETECTION_DRAFT.md
