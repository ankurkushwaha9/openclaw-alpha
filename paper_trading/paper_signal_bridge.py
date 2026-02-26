#!/usr/bin/env python3
"""
paper_signal_bridge.py - Whale Tracker to Paper Trading Bridge
Location: ~/.openclaw/workspace/paper_trading/paper_signal_bridge.py
Version: 2.0 | Updated: 2026-02-24 (Mission 7 - Active Paper Trading)

Changes v1 → v2:
  - Variable trade sizing: fractional Kelly criterion (25% Kelly, $3 min, $10 max)
  - Daily proposal cap: max 5 proposals per calendar day (UTC)
  - Resolution date shown in every Telegram proposal
  - Sizing rationale shown in proposal (transparency for YES/NO decision)
  - daily_stats block added to pending_proposals.json (resets each UTC day)
  - All 4 guards and category detection unchanged

Run: python paper_trading/paper_signal_bridge.py
     python paper_trading/paper_signal_bridge.py --dry-run
"""

import json
import sys
import os
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

# --- Paths --------------------------------------------------------------------
WORKSPACE    = Path("/home/ubuntu/.openclaw/workspace")
SIGNALS_FILE = WORKSPACE / "scripts"       / "whale_signals.json"
LEDGER_FILE  = WORKSPACE / "paper_trading" / "ledger.json"
PENDING_FILE = WORKSPACE / "paper_trading" / "pending_proposals.json"
BOT_CONFIG   = Path("/home/ubuntu/.openclaw/openclaw.json")
BRIDGE_LOG   = WORKSPACE / "paper_trading" / "bridge.log"

# --- Risk constants -----------------------------------------------------------
MAX_EXPOSURE_PCT  = 0.40   # 40% of portfolio max deployed at any time
MAX_CATEGORY_PCT  = 0.40   # 40% in any single category
MAX_BET           = 10.00  # hard cap per trade
MIN_BET           = 3.00   # floor per trade
KELLY_FRACTION    = 0.25   # conservative: use 25% of full Kelly
PROPOSAL_TTL_MINS = 30     # proposals expire after 30 min
MAX_PROPOSALS_DAY = 5      # daily cap — max Telegram proposals per UTC day

# --- Category keyword map (unchanged from v1) ---------------------------------
CATEGORY_KEYWORDS = {
    "politics":      ["election", "president", "congress", "senate", "vote",
                      "trump", "governor", "primary", "democrat", "republican",
                      "ballot", "poll", "candidate", "federal", "white house"],
    "entertainment": ["oscar", "emmy", "grammy", "award", "actor", "actress",
                      "film", "movie", "singer", "celebrity", "music", "album",
                      "box office", "director", "netflix", "hollywood"],
    "sports":        ["nba", "nfl", "mlb", "nhl", "playoff", "championship",
                      "tournament", "super bowl", "world cup", "league",
                      "finals", "mvp", "season", "match", "game", "team",
                      "basketball", "football", "baseball", "soccer"],
    "finance":       ["fed", "rate", "bitcoin", "crypto", "inflation", "gdp",
                      "recession", "stock", "market", "economy", "interest",
                      "dollar", "btc", "eth", "ethereum", "nasdaq", "s&p",
                      "earnings", "ipo", "debt", "treasury"],
}


# --- Logging ------------------------------------------------------------------

def log(msg, level="INFO"):
    line = f"[{datetime.now(timezone.utc).isoformat()}] [{level}] {msg}"
    print(line)
    with open(BRIDGE_LOG, "a") as f:
        f.write(line + "\n")


# --- Telegram -----------------------------------------------------------------

def get_telegram_creds():
    try:
        with open(BOT_CONFIG) as f:
            cfg = json.load(f)
        token   = cfg.get("channels", {}).get("telegram", {}).get("botToken", "")
        chat_id = cfg.get("channels", {}).get("telegram", {}).get("allowFrom", [""])[0]
        return token, chat_id
    except Exception as e:
        log(f"Could not read Telegram creds: {e}", "WARN")
        return "", ""


def send_telegram(msg, dry_run=False):
    if dry_run:
        log("DRY RUN - Telegram not sent", "DRY")
        print("\n--- TELEGRAM PROPOSAL (dry run) ---")
        print(msg)
        print("-----------------------------------\n")
        return True
    token, chat_id = get_telegram_creds()
    if not token or not chat_id:
        log("Telegram creds missing", "WARN")
        print(msg)
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg},
            timeout=10
        )
        r.raise_for_status()
        log("Telegram sent OK", "INFO")
        return True
    except Exception as e:
        log(f"Telegram failed: {e}", "ERROR")
        return False


# --- Ledger helpers -----------------------------------------------------------

def load_ledger():
    if not LEDGER_FILE.exists():
        log("Ledger not found", "ERROR")
        sys.exit(1)
    with open(LEDGER_FILE) as f:
        return json.load(f)


def load_pending():
    if not PENDING_FILE.exists():
        return {"proposals": [], "daily_stats": {}}
    with open(PENDING_FILE) as f:
        data = json.load(f)
    # Handle legacy list format from Phase 2
    if isinstance(data, list):
        return {"proposals": data, "daily_stats": {}}
    # Ensure daily_stats key exists
    data.setdefault("daily_stats", {})
    return data


def save_pending(data):
    with open(PENDING_FILE, "w") as f:
        json.dump(data, f, indent=2)


# --- Daily cap ----------------------------------------------------------------

def check_daily_cap(pending: dict) -> tuple[bool, int]:
    """
    Returns (can_send_more: bool, sent_today: int).
    Resets automatically each UTC calendar day.
    """
    today     = datetime.now(timezone.utc).date().isoformat()
    daily     = pending.get("daily_stats", {})
    if daily.get("date") != today:
        # New day — treat as zero sent
        return True, 0
    sent_today = daily.get("proposals_sent", 0)
    return sent_today < MAX_PROPOSALS_DAY, sent_today


def increment_daily_cap(pending: dict) -> dict:
    """Increment today's proposal counter. Resets if date has changed."""
    today = datetime.now(timezone.utc).date().isoformat()
    daily = pending.get("daily_stats", {})
    if daily.get("date") != today:
        pending["daily_stats"] = {"date": today, "proposals_sent": 0}
    pending["daily_stats"]["proposals_sent"] = pending["daily_stats"].get("proposals_sent", 0) + 1
    return pending


# --- Category detection -------------------------------------------------------

def detect_category(market_name: str) -> str:
    name_lower = market_name.lower()
    scores     = {cat: 0 for cat in CATEGORY_KEYWORDS}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in name_lower:
                scores[cat] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "other"


# --- Kelly sizing -------------------------------------------------------------

def calculate_trade_size(signal: dict, total_portfolio: float) -> tuple[float, str]:
    """
    Fractional Kelly criterion: size each paper trade based on signal strength.

    Formula: f* = divergence / (1 - market_prob)
    We use KELLY_FRACTION (25%) of f* to stay conservative.
    Size = total_portfolio * (f* * KELLY_FRACTION)
    Capped between MIN_BET ($3) and MAX_BET ($10).

    Returns (size: float, rationale: str) — rationale shown in Telegram proposal.

    Examples at $66 portfolio:
      Tier 1: 20% div, 50% market → Kelly 0.40, 25%=0.10 → $6.60
      Tier 1: 20% div, 30% market → Kelly 0.29, 25%=0.07 → $4.69
      Tier 2: 10% div, 50% market → Kelly 0.20, 25%=0.05 → $3.30
      Tier 2:  8% div, 70% market → Kelly 0.27, 25%=0.07 → $4.40
    """
    divergence  = signal.get("divergence",  0.10)
    market_prob = signal.get("market_prob", 0.50)

    denominator = 1.0 - market_prob
    if denominator <= 0.01:
        # Market near 99%+ — Kelly undefined, use floor
        kelly_f = 0.10
    else:
        kelly_f = divergence / denominator

    fraction = kelly_f * KELLY_FRACTION
    raw_size = total_portfolio * fraction

    # Apply bounds
    size = max(MIN_BET, min(MAX_BET, raw_size))
    size = round(size, 2)

    rationale = (
        f"Kelly={kelly_f*100:.0f}% × {int(KELLY_FRACTION*100)}% = "
        f"{fraction*100:.1f}% of ${total_portfolio:.0f} "
        f"= ${raw_size:.2f} → ${size:.2f}"
    )
    return size, rationale


# --- Portfolio calculations ---------------------------------------------------

def get_live_price(market_id: str, side: str = "YES"):
    try:
        r = requests.get(
            f"https://gamma-api.polymarket.com/markets/{market_id}",
            timeout=10
        )
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            data = data[0] if data else {}
        outcomes_raw = data.get("outcomes", [])
        prices_raw   = data.get("outcomePrices", [])
        outcomes = json.loads(outcomes_raw) if isinstance(outcomes_raw, str) else outcomes_raw
        prices   = json.loads(prices_raw)   if isinstance(prices_raw,   str) else prices_raw
        if outcomes and prices:
            for i, outcome in enumerate(outcomes):
                if outcome.strip().upper() == side.upper():
                    return float(prices[i])
            return float(prices[0])
    except Exception:
        pass
    return None


def calc_portfolio_value(ledger: dict) -> tuple[float, float, float]:
    """Returns (cash, open_value, total_portfolio)."""
    cash       = ledger["meta"]["virtual_balance"]
    open_value = 0.0
    for pos in ledger["open_positions"]:
        live = get_live_price(pos["market_id"], pos["side"])
        open_value += (pos["shares"] * live) if live is not None else pos["virtual_amount"]
    return cash, open_value, cash + open_value


def calc_category_exposure(ledger: dict, total_portfolio: float) -> dict:
    """Returns {category: pct_of_total_portfolio} for all open positions."""
    cat_invested = {}
    for pos in ledger["open_positions"]:
        cat = pos.get("category", "other")
        cat_invested[cat] = cat_invested.get(cat, 0.0) + pos["virtual_amount"]
    if total_portfolio <= 0:
        return {}
    return {cat: round(amt / total_portfolio, 4) for cat, amt in cat_invested.items()}


# --- Guards (unchanged from v1) -----------------------------------------------

def guard_tier(signal: dict) -> tuple[bool, str]:
    tier = signal.get("tier", 0)
    if tier in (1, 2):
        return True, f"Tier {tier} — passes"
    return False, f"Tier {tier} — below threshold (need Tier 1 or 2)"


def guard_exposure(ledger: dict, amount: float, total_portfolio: float) -> tuple[bool, str]:
    total_invested = sum(p["virtual_amount"] for p in ledger["open_positions"])
    new_exposure   = (total_invested + amount) / total_portfolio if total_portfolio > 0 else 1
    if new_exposure <= MAX_EXPOSURE_PCT:
        return True, f"Exposure after: {new_exposure*100:.1f}% (max {MAX_EXPOSURE_PCT*100:.0f}%)"
    return False, f"Exposure {new_exposure*100:.1f}% exceeds {MAX_EXPOSURE_PCT*100:.0f}% max"


def guard_duplicate(ledger: dict, pending: dict, market_id: str) -> tuple[bool, str]:
    for pos in ledger["open_positions"]:
        if pos["market_id"] == market_id:
            return False, f"Already open in {market_id[:16]}..."
    now = datetime.now(timezone.utc)
    for prop in pending.get("proposals", []):
        if prop.get("market_id") == market_id and prop.get("status") in ("sent", "blocked"):
            age_mins = (now - datetime.fromisoformat(prop["sent_at"])).total_seconds() / 60
            ttl = PROPOSAL_TTL_MINS if prop.get("status") == "sent" else 2880
            if age_mins < ttl:
                return False, f"Proposal blocked {age_mins:.0f}min ago (TTL {ttl}min)"
    return True, "Market is fresh — no duplicate"


def guard_category(cat_exposure: dict, category: str,
                   amount: float, total_portfolio: float) -> tuple[bool, str]:
    current_pct = cat_exposure.get(category, 0.0)
    new_pct     = current_pct + (amount / total_portfolio if total_portfolio > 0 else 1)
    if new_pct < MAX_CATEGORY_PCT:
        return True, f"{category.title()} → {new_pct*100:.1f}% after trade (max {MAX_CATEGORY_PCT*100:.0f}%)"
    return False, f"{category.title()} at {current_pct*100:.1f}% — would hit {new_pct*100:.1f}%"


# --- Proposal builder ---------------------------------------------------------

def build_proposal(signal: dict, category: str, amount: float, sizing_rationale: str,
                   exposure_after: float, cat_exposure: dict,
                   total_portfolio: float) -> str:

    tier_label  = ("Tier 1 — Whale >15% divergence" if signal["tier"] == 1
                   else "Tier 2 — Whale 8-15% divergence")
    side        = "YES" if signal["direction"] in ("BUY", "YES") else "NO"
    entry_price = signal["yes_price"]

    # Resolution line
    days = signal.get("days_to_resolve", 0)
    end  = signal.get("end_date_iso", "")
    if days and end:
        try:
            end_dt      = datetime.fromisoformat(end.replace("Z", "+00:00"))
            resolve_str = f"{end_dt.strftime('%b %d')} ({days} days)"
        except Exception:
            resolve_str = f"{days} days"
    else:
        resolve_str = "Date unknown"

    # Max ROI
    max_roi = round(((1.0 - entry_price) / entry_price) * 100, 1) if entry_price > 0 else 0

    # Category split after this trade
    cat_after = dict(cat_exposure)
    cat_after[category] = cat_after.get(category, 0.0) + (
        amount / total_portfolio if total_portfolio > 0 else 0)
    all_cats  = ["politics", "entertainment", "sports", "finance", "other"]
    cat_lines = " / ".join(
        f"{c.title()} {cat_after.get(c, 0)*100:.0f}%"
        for c in all_cats if cat_after.get(c, 0) > 0
    )
    if not cat_lines:
        cat_lines = "First trade"

    test_mode = os.getenv("BRIDGE_TEST_MODE", "0") == "1"
    header    = "[TEST DO NOT FUND] PAPER TRADE PROPOSAL" if test_mode else "PAPER TRADE PROPOSAL"
    return (
        f"{header}\n"
        f"- Market: {signal['market_name'][:55]}\n"
        f"- Resolves: {resolve_str}\n"
        f"- Category: {category.title()}\n"
        f"- Side: {side} | Entry: {entry_price:.3f} | Amount: ${amount:.2f} virtual\n"
        f"- Sizing: {sizing_rationale}\n"
        f"- Max ROI if correct: +{max_roi:.1f}%\n"
        f"- Signal: {tier_label}\n"
        f"- Whale divergence: {signal['divergence']*100:.1f}% | Size: ${signal['size_usd']:,.0f}\n"
        f"- Exposure after trade: {exposure_after*100:.1f}% (max 40%)\n"
        f"- Category split: {cat_lines}\n"
        f"- Market ID: {signal['market_id'][:20]}...\n"
        f"\n"
        f"Reply YES to execute paper trade\n"
        f"Reply NO to skip\n"
        f"(expires in {PROPOSAL_TTL_MINS} min)"
    )


# --- Main bridge logic --------------------------------------------------------

def run_bridge(dry_run=False):
    log("="*50, "START")
    log(f"Bridge v2 started — daily cap {MAX_PROPOSALS_DAY}/day | Kelly {int(KELLY_FRACTION*100)}%")

    # Load signals
    if not SIGNALS_FILE.exists():
        log("whale_signals.json not found — run whale_tracker.py --json first", "ERROR")
        sys.exit(1)

    with open(SIGNALS_FILE) as f:
        whale_data = json.load(f)

    signals    = whale_data.get("signals", [])
    scanned_at = whale_data.get("scanned_at", "unknown")
    n_markets  = whale_data.get("markets_scanned", "?")
    log(f"Loaded {len(signals)} signal(s) from {n_markets} markets scanned at {scanned_at}")

    if not signals:
        log("No signals to process — exiting cleanly")
        return

    # Load state
    ledger  = load_ledger()
    pending = load_pending()

    # Check daily cap BEFORE processing any signals
    can_send, sent_today = check_daily_cap(pending)
    log(f"Daily cap: {sent_today}/{MAX_PROPOSALS_DAY} proposals sent today (UTC)")

    if not can_send:
        log(f"Daily cap of {MAX_PROPOSALS_DAY} reached — no more proposals today. "
            f"Resets at midnight UTC.", "CAP")
        return

    # Portfolio metrics
    cash, open_val, total_portfolio = calc_portfolio_value(ledger)
    cat_exposure = calc_category_exposure(ledger, total_portfolio)
    log(f"Portfolio: cash=${cash:.2f} | open=${open_val:.2f} | total=${total_portfolio:.2f}")

    proposals_sent = 0
    remaining_cap  = MAX_PROPOSALS_DAY - sent_today

    for signal in signals:
        # Respect daily cap mid-loop
        if proposals_sent >= remaining_cap:
            log(f"Daily cap reached mid-loop ({MAX_PROPOSALS_DAY}/day) — stopping", "CAP")
            break

        market_id   = signal["market_id"]
        market_name = signal["market_name"]
        tier        = signal["tier"]
        category    = detect_category(market_name)
        days_left   = signal.get("days_to_resolve", 0)

        log(f"Processing: {market_name[:50]} | Tier {tier} | "
            f"Category: {category} | Resolves: {days_left}d")

        # --- Guard 1: Tier ---
        ok, reason = guard_tier(signal)
        log(f"  Guard 1 (tier):      {'PASS' if ok else 'BLOCK'} — {reason}")
        if not ok:
            continue

        # --- Variable sizing (Kelly) ---
        amount, sizing_rationale = calculate_trade_size(signal, total_portfolio)
        log(f"  Kelly sizing: {sizing_rationale}")

        # --- Guard 2: Duplicate (before exposure to stop spam) ---
        ok, reason = guard_duplicate(ledger, pending, market_id)
        log(f"  Guard 2 (duplicate): {'PASS' if ok else 'BLOCK'} — {reason}")
        if not ok:
            continue

        # --- Guard 3: Exposure ---
        total_invested = sum(p["virtual_amount"] for p in ledger["open_positions"])
        # Trim bet to fit within remaining exposure headroom (avoid hard block when close to cap)
        if total_portfolio > 0:
            headroom = (MAX_EXPOSURE_PCT * total_portfolio) - total_invested
            if headroom < amount and headroom >= MIN_BET:
                log(f"  Exposure headroom ${headroom:.2f} < requested ${amount:.2f} - trimming bet to fit cap")
                amount = round(headroom, 2)
        exposure_after = (total_invested + amount) / total_portfolio if total_portfolio > 0 else 1
        ok, reason = guard_exposure(ledger, amount, total_portfolio)
        log(f"  Guard 3 (exposure):  {'PASS' if ok else 'BLOCK'} — {reason}")
        if not ok:
            # Only alert once - don't spam if already blocked before
            already_blocked = any(
                p.get("market_id") == market_id and p.get("status") == "blocked"
                for p in pending["proposals"]
            )
            if not already_blocked:
                send_telegram(
                    f"PAPER BRIDGE ALERT\n"
                    f"Signal BLOCKED by exposure guard\n"
                    f"- Market: {market_name[:50]}\n"
                    f"- Reason: {reason}\n"
                    f"- Post-trade exposure would be: {exposure_after*100:.1f}%\n"
                    f"- Portfolio currently at {(total_invested/total_portfolio*100):.1f}% deployed",
                    dry_run
                )
            # Record blocked proposal so duplicate guard suppresses future spam
            blocked_record = {
                "market_id":    market_id,
                "market_name":  market_name,
                "status":       "blocked",
                "block_reason": "exposure_guard",
                "sent_at":      datetime.now(timezone.utc).isoformat(),
            }
            pending["proposals"].append(blocked_record)
            if not dry_run:
                save_pending(pending)
                log(f"Blocked proposal recorded — future spam suppressed")
            continue

        # --- Guard 4: Category cap ---
        ok, reason = guard_category(cat_exposure, category, amount, total_portfolio)
        log(f"  Guard 4 (category):  {'PASS' if ok else 'BLOCK'} — {reason}")
        if not ok:
            send_telegram(
                f"PAPER BRIDGE ALERT\n"
                f"Signal BLOCKED by category cap\n"
                f"- Market: {market_name[:50]}\n"
                f"- Category: {category.title()}\n"
                f"- Reason: {reason}",
                dry_run
            )
            continue

        # --- All 4 guards passed — build and send proposal ---
        proposal_msg = build_proposal(
            signal, category, amount, sizing_rationale,
            exposure_after, cat_exposure, total_portfolio
        )

        sent = send_telegram(proposal_msg, dry_run)

        if sent:
            # CRITICAL: Mark sent IMMEDIATELY (Phase 2 loop bug lesson applied)
            proposal_record = {
                "market_id":      market_id,
                "market_name":    market_name,
                "category":       category,
                "tier":           tier,
                "side":           "YES" if signal["direction"] in ("BUY", "YES") else "NO",
                "entry_price":    signal["yes_price"],
                "amount":         amount,
                "divergence":     signal["divergence"],
                "days_to_resolve": days_left,
                "end_date_iso":   signal.get("end_date_iso", ""),
                "status":         "sent",
                "sent_at":        datetime.now(timezone.utc).isoformat(),
            }
            pending["proposals"].append(proposal_record)
            pending = increment_daily_cap(pending)

            if not dry_run:
                save_pending(pending)
                log(f"Proposal + daily cap written to pending_proposals.json")

            proposals_sent += 1
            _, sent_today_now = check_daily_cap(pending)
            log(f"Proposal sent ({sent_today_now}/{MAX_PROPOSALS_DAY} today): {market_name[:50]}", "PROPOSAL")

    log(f"Bridge complete — {proposals_sent} new proposal(s) sent this run")

    # Cleanup: remove expired proposals from pending (keep file lean)
    if not dry_run:
        now    = datetime.now(timezone.utc)
        before = len(pending["proposals"])
        def _age_mins(p):
            ts = datetime.fromisoformat(p["sent_at"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return (now - ts).total_seconds() / 60

        pending["proposals"] = [
            p for p in pending["proposals"]
            if _age_mins(p) < (2880 if p.get("status") == "blocked" else PROPOSAL_TTL_MINS * 2)
        ]
        after = len(pending["proposals"])
        if before != after:
            save_pending(pending)
            log(f"Cleaned {before - after} expired proposal(s)")


# --- Entry point --------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Whale-to-Paper Bridge v2")
    parser.add_argument("--dry-run", action="store_true", default=False,
                        help="Console only — no Telegram, no writes")
    args = parser.parse_args()
    run_bridge(dry_run=args.dry_run)
