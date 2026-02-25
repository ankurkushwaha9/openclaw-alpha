#!/usr/bin/env python3
"""
Paper Trading Engine for Alpha Bot
Location: ~/.openclaw/workspace/paper_trading/paper_engine.py
Version: 1.0 | Built: 2026-02-22
Purpose: Simulate full trading workflow without risking real USDC.
         Same pipeline as real trades: scan -> signal -> propose -> execute -> log.

Commands:
    init                                                  - Initialize ledger
    buy <market_id> <YES|NO> <amount> <entry_price> <signal_tier> <market_name...>
    status                                                - Open positions + live P&L
    resolve <position_id> <WIN|LOSS> <exit_price>        - Settle a resolved market
    report                                                - Performance + go-live scorecard
"""

import json
import sys
import os
import uuid
import requests
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
WORKSPACE  = Path("/home/ubuntu/.openclaw/workspace")
PAPER_DIR  = WORKSPACE / "paper_trading"
ENV        = os.getenv("BOT_ENV", "paper").lower()
LEDGER     = PAPER_DIR / ("test_ledger.json" if ENV == "e2e_test" else "ledger.json")
if ENV == "e2e_test":
    print("⚠️  E2E TEST MODE — writing to test_ledger.json (production ledger untouched)")
LOG_FILE   = PAPER_DIR / "paper_trades.log"

# ── Kelly / risk constants (mirrors CLAUDE.md rules) ─────────────────────────
MAX_BET          = 10.00   # max single bet until account reaches $500
MAX_EXPOSURE_PCT = 0.40    # 40% of virtual balance max at any time
STARTING_BALANCE = 66.00

# ── Go-live thresholds ────────────────────────────────────────────────────────
GO_LIVE = {
    "min_resolved":   10,
    "min_win_rate":   60.0,   # %
    "min_avg_roi":    10.0,   # %
    "min_yes_rate":   50.0,   # % of proposals Ankur said YES to
}


# ─────────────────────────────────────────────────────────────────────────────
# Ledger helpers
# ─────────────────────────────────────────────────────────────────────────────

def load_ledger():
    if not LEDGER.exists():
        print("No ledger found. Run: paper_engine.py init")
        sys.exit(1)
    with open(LEDGER) as f:
        return json.load(f)


def save_ledger(data):
    data["meta"]["last_updated"] = _now()
    with open(LEDGER, "w") as f:
        json.dump(data, f, indent=2)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _log(message, event="INFO"):
    with open(LOG_FILE, "a") as f:
        f.write(f"[{_now()}] [{event}] {message}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Price fetcher (Gamma API — same source as PolyClaw)
# ─────────────────────────────────────────────────────────────────────────────

def get_market_price(market_id: str, side: str = "YES") -> float | None:
    """
    Fetch live token price from Polymarket Gamma API.
    Gamma returns outcomePrices (list of strings) paired with outcomes (list of strings).
    e.g. outcomes: ["Yes","No"]  outcomePrices: ["0.725","0.275"]
    """
    try:
        base = "https://gamma-api.polymarket.com/markets"
        if market_id.startswith("0x"):
            # conditionId hex market: scan active then closed, match exactly
            data = {}
            for closed_val in ["false", "true"]:
                r2 = requests.get(base, params={"closed": closed_val, "limit": 500}, timeout=15)
                r2.raise_for_status()
                matched = [m for m in r2.json() if m.get("conditionId","").lower() == market_id.lower()]
                if matched:
                    data = matched[0]
                    break
        else:
            resp = requests.get(f"{base}/{market_id}", timeout=10)
            resp.raise_for_status()
            data = resp.json()

        if isinstance(data, list):
            data = data[0] if data else {}

        import json as _json
        outcomes_raw = data.get("outcomes", [])
        prices_raw   = data.get("outcomePrices", [])

        # Gamma API returns these as JSON strings OR actual lists
        outcomes = _json.loads(outcomes_raw) if isinstance(outcomes_raw, str) else outcomes_raw
        prices   = _json.loads(prices_raw)   if isinstance(prices_raw,   str) else prices_raw

        if outcomes and prices:
            for i, outcome in enumerate(outcomes):
                if outcome.strip().upper() == side.upper():
                    return float(prices[i])
            # fallback: YES is index 0 on binary markets
            return float(prices[0])

        # last resort
        ltp = data.get("lastTradePrice")
        if ltp is not None:
            return float(ltp)

    except Exception as e:
        print(f"  [WARN] Live price unavailable for {market_id}: {e}")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Commands
# ─────────────────────────────────────────────────────────────────────────────

def cmd_init(args):
    """Initialize (or reset) the paper trading ledger."""
    if LEDGER.exists():
        print("Ledger already exists. Type 'reset' to wipe and restart, or anything else to cancel: ", end="")
        answer = input().strip().lower()
        if answer != "reset":
            print("Aborted.")
            return

    PAPER_DIR.mkdir(parents=True, exist_ok=True)

    ledger = {
        "meta": {
            "virtual_balance":  STARTING_BALANCE,
            "starting_balance": STARTING_BALANCE,
            "created":          _now(),
            "last_updated":     _now(),
            "version":          "1.0"
        },
        "open_positions":     [],
        "resolved_positions": [],
        "proposals": {
            "total":    0,
            "approved": 0
        },
        "stats": {
            "total_trades": 0,
            "wins":         0,
            "losses":       0,
            "total_pnl":    0.0,
            "win_rate":     0.0,
            "avg_roi":      0.0
        }
    }

    with open(LEDGER, "w") as f:
        json.dump(ledger, f, indent=2)

    _log("Ledger initialized", "INIT")
    print(f"[OK] Paper trading ledger initialized")
    print(f"     Virtual balance : ${STARTING_BALANCE:.2f}")
    print(f"     Location        : {LEDGER}")


# ─────────────────────────────────────────────────────────────────────────────

CATEGORY_KEYWORDS = {
    "politics":      ["election", "president", "congress", "senate", "vote",
                      "trump", "governor", "primary", "democrat", "republican"],
    "entertainment": ["oscar", "emmy", "grammy", "award", "actor", "actress",
                      "film", "movie", "singer", "celebrity", "music", "album"],
    "sports":        ["nba", "nfl", "mlb", "nhl", "playoff", "championship",
                      "tournament", "super bowl", "finals", "mvp", "basketball"],
    "finance":       ["fed", "rate", "bitcoin", "crypto", "inflation", "gdp",
                      "recession", "stock", "market", "btc", "eth", "earnings"],
}

def _detect_category(market_name: str) -> str:
    name_lower = market_name.lower()
    scores = {cat: 0 for cat in CATEGORY_KEYWORDS}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in name_lower:
                scores[cat] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "other"


def cmd_buy(args):
    """
    Execute a paper trade (after Ankur has approved via Telegram).

    Usage:
        paper_engine.py buy <market_id> <YES|NO> <amount> <entry_price> <signal_tier> <market_name...> [category]

    Example:
        paper_engine.py buy 614008 YES 8.00 0.79 1 Best Actor Chalamet entertainment
        paper_engine.py buy 614008 YES 8.00 0.79 1 Best Actor Chalamet  (category auto-detected)

    signal_tier: 1 = Tier1 (whale >15% + news), 2 = Tier2, 3 = Tier3
    """
    if len(args) < 6:
        print("Usage: buy <market_id> <YES|NO> <amount> <entry_price> <signal_tier> <market_name...>")
        sys.exit(1)

    market_id    = args[0]
    side         = args[1].upper()
    amount       = float(args[2])
    entry_price  = float(args[3])
    signal_tier  = int(args[4])

    # Category is optional last arg — if last word is a known category, extract it
    KNOWN_CATEGORIES = {"politics", "entertainment", "sports", "finance", "other"}
    name_args = args[5:]
    if name_args and name_args[-1].lower() in KNOWN_CATEGORIES:
        category    = name_args[-1].lower()
        market_name = " ".join(name_args[:-1])
    else:
        # Auto-detect category from market name via keyword matching
        market_name = " ".join(name_args)
        category    = _detect_category(market_name)

    if side not in ("YES", "NO"):
        print("Side must be YES or NO")
        sys.exit(1)

    ledger = load_ledger()

    # Kelly guard
    if amount > MAX_BET:
        print(f"[WARN] ${amount} exceeds ${MAX_BET} max bet (Kelly rule). Continuing anyway — log it.")

    # Exposure guard
    total_invested = sum(p["virtual_amount"] for p in ledger["open_positions"])
    balance        = ledger["meta"]["virtual_balance"]
    new_exposure   = (total_invested + amount) / (balance + total_invested)
    if new_exposure > MAX_EXPOSURE_PCT:
        print(f"[WARN] This trade pushes exposure to {new_exposure*100:.1f}% (max {MAX_EXPOSURE_PCT*100:.0f}%).")

    if amount > balance:
        print(f"[ERROR] Insufficient virtual balance: ${balance:.2f} available, need ${amount:.2f}")
        sys.exit(1)

    # Duplicate protection: block same market_id + side within 60 seconds
    for existing in ledger["open_positions"]:
        if existing["market_id"] == market_id and existing["side"] == side:
            from datetime import datetime, timezone, timedelta
            executed_at = datetime.fromisoformat(existing["executed_at"])
            age_seconds = (datetime.now(timezone.utc) - executed_at).total_seconds()
            if age_seconds < 60:
                print(f"[BLOCKED] Duplicate trade detected: {market_name} {side} already open (ID {existing['id']}, {age_seconds:.0f}s ago). Skipping.")
                sys.exit(0)

    shares      = round(amount / entry_price, 6)
    position_id = str(uuid.uuid4())[:8]

    position = {
        "id":               position_id,
        "market_id":        market_id,
        "market_name":      market_name,
        "category":         category,
        "side":             side,
        "virtual_amount":   amount,
        "entry_price":      entry_price,
        "shares":           shares,
        "signal_tier":      signal_tier,
        "whale_divergence": None,   # set manually if applicable
        "executed_at":      _now(),
        "paper":            True
    }

    ledger["open_positions"].append(position)
    ledger["meta"]["virtual_balance"] = round(balance - amount, 6)
    ledger["stats"]["total_trades"]  += 1
    ledger["proposals"]["total"]     += 1
    ledger["proposals"]["approved"]  += 1   # already approved by Ankur before reaching here

    save_ledger(ledger)
    _log(
        f"BUY | {market_name} | {side} | ${amount} @ {entry_price} | Tier {signal_tier} | ID {position_id}",
        "BUY"
    )

    print(f"\n[PAPER TRADE EXECUTED]")
    print(f"  ID           : {position_id}")
    print(f"  Market       : {market_name} ({market_id})")
    print(f"  Side         : {side}")
    print(f"  Amount       : ${amount:.2f} virtual")
    print(f"  Entry Price  : {entry_price:.4f}")
    print(f"  Shares       : {shares}")
    print(f"  Signal Tier  : {signal_tier}")
    print(f"  Category     : {category}")
    print(f"  Balance Left : ${ledger['meta']['virtual_balance']:.2f}")


# ─────────────────────────────────────────────────────────────────────────────

def cmd_status(args):
    """Show all open paper positions with live P&L."""
    ledger = load_ledger()
    open_pos = ledger["open_positions"]

    print(f"\n[PAPER TRADING STATUS]")
    print(f"  Virtual Balance  : ${ledger['meta']['virtual_balance']:.2f}")
    print(f"  Starting Balance : ${ledger['meta']['starting_balance']:.2f}")
    print(f"  Open Positions   : {len(open_pos)}")
    print(f"  Total Trades     : {ledger['stats']['total_trades']}")
    print()

    if not open_pos:
        print("  No open positions.")
        return

    total_invested     = 0.0
    total_current_val  = 0.0

    for pos in open_pos:
        invested      = pos["virtual_amount"]
        current_price = get_market_price(pos["market_id"], pos["side"])

        if current_price is not None:
            current_value = round(pos["shares"] * current_price, 4)
            pnl           = round(current_value - invested, 4)
            pnl_pct       = round((pnl / invested) * 100, 2) if invested else 0
            price_str     = f"{current_price:.4f}"
            pnl_str       = f"${pnl:+.2f} ({pnl_pct:+.1f}%)"
        else:
            current_value = invested
            price_str     = "N/A"
            pnl_str       = "N/A"

        total_invested    += invested
        total_current_val += current_value

        print(f"  [{pos['id']}] {pos['market_name']}")
        print(f"       Side      : {pos['side']}  |  Invested: ${invested:.2f}  |  Entry: {pos['entry_price']:.4f}")
        print(f"       Live Price: {price_str}  |  P&L: {pnl_str}  |  Tier: {pos['signal_tier']}")
        print()

    portfolio_pnl     = total_current_val - total_invested
    portfolio_pnl_pct = (portfolio_pnl / total_invested * 100) if total_invested > 0 else 0
    print(f"  Portfolio P&L : ${portfolio_pnl:+.2f} ({portfolio_pnl_pct:+.1f}%)")


# ─────────────────────────────────────────────────────────────────────────────

def cmd_resolve(args):
    """
    Close a paper position when the real market resolves.

    Usage:
        paper_engine.py resolve <position_id> <WIN|LOSS> <exit_price>

    Example (market resolved YES, full payout):
        paper_engine.py resolve 4fbe8869 WIN 1.00

    Example (position resolved as worthless):
        paper_engine.py resolve 4fbe8869 LOSS 0.00
    """
    if len(args) < 3:
        print("Usage: resolve <position_id> <WIN|LOSS> <exit_price>")
        sys.exit(1)

    pos_id     = args[0]
    outcome    = args[1].upper()
    exit_price = float(args[2])

    if outcome not in ("WIN", "LOSS"):
        print("Outcome must be WIN or LOSS")
        sys.exit(1)

    ledger = load_ledger()

    match = None
    for p in ledger["open_positions"]:
        if p["id"] == pos_id:
            match = p
            break

    if not match:
        print(f"[ERROR] Position {pos_id} not found in open positions.")
        available = [p["id"] for p in ledger["open_positions"]]
        print(f"  Open IDs: {available}")
        sys.exit(1)

    exit_value   = round(match["shares"] * exit_price, 6)
    realized_pnl = round(exit_value - match["virtual_amount"], 6)
    roi_pct      = round((realized_pnl / match["virtual_amount"]) * 100, 2) if match["virtual_amount"] else 0

    resolved = {
        **match,
        "exit_price":   exit_price,
        "exit_value":   exit_value,
        "realized_pnl": realized_pnl,
        "roi_pct":      roi_pct,
        "outcome":      outcome,
        "resolved_at":  _now()
    }

    ledger["open_positions"]     = [p for p in ledger["open_positions"] if p["id"] != pos_id]
    ledger["resolved_positions"].append(resolved)
    ledger["meta"]["virtual_balance"] = round(ledger["meta"]["virtual_balance"] + exit_value, 6)
    ledger["stats"]["total_pnl"]      = round(ledger["stats"]["total_pnl"] + realized_pnl, 6)

    if outcome == "WIN":
        ledger["stats"]["wins"]   += 1
    else:
        ledger["stats"]["losses"] += 1

    total_resolved = ledger["stats"]["wins"] + ledger["stats"]["losses"]
    ledger["stats"]["win_rate"] = round(
        ledger["stats"]["wins"] / total_resolved * 100, 1
    ) if total_resolved else 0.0

    all_rois = [p["roi_pct"] for p in ledger["resolved_positions"]]
    ledger["stats"]["avg_roi"] = round(sum(all_rois) / len(all_rois), 2) if all_rois else 0.0

    save_ledger(ledger)
    _log(
        f"RESOLVE | {match['market_name']} | {outcome} | exit {exit_price} | P&L ${realized_pnl:+.2f} ({roi_pct:+.1f}%) | ID {pos_id}",
        "RESOLVE"
    )

    print(f"\n[PAPER POSITION RESOLVED]")
    print(f"  Market       : {match['market_name']}")
    print(f"  Outcome      : {outcome}")
    print(f"  Exit Price   : {exit_price:.4f}")
    print(f"  Exit Value   : ${exit_value:.2f}")
    print(f"  Realized P&L : ${realized_pnl:+.2f} ({roi_pct:+.1f}%)")
    print(f"  New Balance  : ${ledger['meta']['virtual_balance']:.2f}")
    print(f"  Win Rate     : {ledger['stats']['win_rate']}%")


# ─────────────────────────────────────────────────────────────────────────────

def cmd_report(args):
    """Full performance report + go-live scorecard."""
    ledger = load_ledger()
    stats  = ledger["stats"]
    meta   = ledger["meta"]
    props  = ledger["proposals"]

    growth     = meta["virtual_balance"] - meta["starting_balance"]
    growth_pct = (growth / meta["starting_balance"] * 100) if meta["starting_balance"] else 0
    resolved   = stats["wins"] + stats["losses"]
    yes_rate   = (props["approved"] / props["total"] * 100) if props["total"] else 0

    print(f"\n[ALPHA PAPER TRADING REPORT]")
    print(f"  =========================================")
    print(f"  Starting Balance  : ${meta['starting_balance']:.2f}")
    print(f"  Current Balance   : ${meta['virtual_balance']:.2f}")
    print(f"  Total Growth      : ${growth:+.2f} ({growth_pct:+.1f}%)")
    print(f"  -----------------------------------------")
    print(f"  Total Trades      : {stats['total_trades']}")
    print(f"  Resolved          : {resolved}  (Win: {stats['wins']}  Loss: {stats['losses']})")
    print(f"  Win Rate          : {stats['win_rate']}%")
    print(f"  Avg ROI / Trade   : {stats['avg_roi']}%")
    print(f"  Total P&L         : ${stats['total_pnl']:+.2f}")
    print(f"  Proposals (YES %) : {props['approved']}/{props['total']}  ({yes_rate:.1f}%)")
    print(f"  =========================================")

    # Per-tier breakdown
    tier_stats = {}
    for p in ledger["resolved_positions"]:
        t = p.get("signal_tier", "?")
        if t not in tier_stats:
            tier_stats[t] = {"wins": 0, "losses": 0, "pnl": 0.0}
        if p["outcome"] == "WIN":
            tier_stats[t]["wins"]   += 1
        else:
            tier_stats[t]["losses"] += 1
        tier_stats[t]["pnl"] += p["realized_pnl"]

    if tier_stats:
        print(f"\n  [Signal Tier Breakdown]")
        for tier in sorted(tier_stats.keys()):
            d   = tier_stats[tier]
            tot = d["wins"] + d["losses"]
            wr  = round(d["wins"] / tot * 100, 1) if tot else 0
            print(f"  Tier {tier}: {tot} trades | Win {wr}% | P&L ${d['pnl']:+.2f}")

    # Go-live scorecard
    print(f"\n  [GO-LIVE SCORECARD]")
    checks = [
        ("Trades resolved >= 10",  resolved  >= GO_LIVE["min_resolved"],  f"{resolved}/10"),
        ("Win rate >= 60%",         stats["win_rate"] >= GO_LIVE["min_win_rate"],  f"{stats['win_rate']}%"),
        ("Avg ROI >= 10%",          stats["avg_roi"]  >= GO_LIVE["min_avg_roi"],   f"{stats['avg_roi']}%"),
        ("Proposal YES rate >= 50%", yes_rate >= GO_LIVE["min_yes_rate"],          f"{yes_rate:.1f}%"),
    ]

    all_green = True
    for label, passed, value in checks:
        icon = "[PASS]" if passed else "[FAIL]"
        if not passed:
            all_green = False
        print(f"  {icon} {label}: {value}")

    verdict = "ALPHA IS READY FOR BIGGER REAL BETS" if all_green else "Keep paper trading — not ready yet"
    print(f"\n  => {verdict}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Dispatch
# ─────────────────────────────────────────────────────────────────────────────

COMMANDS = {
    "init":    cmd_init,
    "buy":     cmd_buy,
    "status":  cmd_status,
    "resolve": cmd_resolve,
    "report":  cmd_report,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("Alpha Paper Trading Engine v1.0")
        print("Usage: paper_engine.py <command> [args]")
        print("Commands:", "  |  ".join(COMMANDS.keys()))
        sys.exit(1)

    COMMANDS[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    main()
