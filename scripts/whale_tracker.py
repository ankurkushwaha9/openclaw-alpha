#!/usr/bin/env python3
"""
whale_tracker.py - Polymarket Whale Signal Detection
Location: ~/.openclaw/workspace/scripts/whale_tracker.py
Last Updated: 2026-03-07 (v5.0 - 3-LLM Consensus Rebuild: Phase 1)

Changes v4 -> v5 (3-LLM Consensus: Claude + Gemini + ChatGPT):
  PARAM CHANGES:
  - WHALE_MIN_SIZE:     $500  -> $400  (sports whales trade smaller)
  - TIER1_DIVERGENCE:   0.15  -> 0.10  (paper phase: collect data aggressively)
  - TIER2_DIVERGENCE:   0.08  -> 0.06  (paper phase: collect data aggressively)
  - MIN_LIQUIDITY:      $5,000 -> $10,000 (volume field broken; liquidity is reliable)
  - Liquidity now used as PRIMARY filter (volume field broken in Gamma API)

  3-STAGE DYNAMIC WINDOW (replaces hard 7-day cap):
  - Stage 1 NORMAL:    1-7d   | whale=$500  | div=10% | default
  - Stage 2 EXPANSION: 1-21d  | whale=$1000 | div=8%  | < 5 markets in Stage 1
  - Stage 3 DEEP SCAN: 1-30d  | whale=$2500 | div=7%  | < 3 markets in Stage 2

  IMPACT RATIO (ChatGPT unique insight):
  - impact_ratio = trade_size / market_liquidity
  - Only flag whale if impact_ratio >= 0.003
  - $500 in $200K market = 0.0025 -> NOT a whale
  - $500 in $10K  market = 0.050  -> YES a whale

  SPORTS MARKETS (Claude was wrong -- lifted exclusion):
  - Sports markets are NOT efficient on Polymarket (retail biases are huge)
  - Sports included but require +2% divergence premium
  - Sports whale min size: $300 (they trade smaller but sharper)

  CATEGORY PRIORITY:
  - Geopolitics > Economics > Entertainment > Sports > Crypto > Other

  PHASE 2 (not yet built -- next session):
  - Whale clustering: 3+ trades in 2h window = bonus signal
  - Alpha scoring: log(liq)*0.4 + log(size)*0.3 + div*0.2 + time_decay*0.1
  - Wallet watchlist: track top profitable addresses

Usage:
    python scripts/whale_tracker.py                  # human-readable
    python scripts/whale_tracker.py --min-size 1000  # custom whale size
    python scripts/whale_tracker.py --json           # bridge mode -> whale_signals.json
    python scripts/whale_tracker.py --json --no-resolution-filter  # skip date filter
    python scripts/whale_tracker.py --stage 2        # force expansion stage
"""

import os
import sys
import json
import requests
import argparse
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# --- CONFIG -------------------------------------------------------------------

GAMMA_API  = "https://gamma-api.polymarket.com"
DATA_API   = "https://data-api.polymarket.com"

# v5: Lowered for paper phase -- collect signals aggressively (all 3 LLMs agree)
WHALE_MIN_SIZE    = 400
MIN_WIN_RATE      = 0.60
MIN_TRADE_HISTORY = 10
TIER1_DIVERGENCE  = 0.10   # was 0.15 -- paper phase
TIER2_DIVERGENCE  = 0.06   # was 0.08 -- paper phase

# v5: Liquidity is now primary filter (Gamma volume field is broken -- shows $100 for all)
MIN_LIQUIDITY     = 10000  # was 5000

# v5: Impact ratio -- ChatGPT insight. $500 in $10K market is a whale; in $200K it's noise.
MIN_IMPACT_RATIO  = 0.003  # trade_size / liquidity >= 0.003

# v5: Sports divergence premium (sports markets have more retail noise)
SPORTS_DIV_PREMIUM = 0.02  # +2% divergence required for sports signals

# v5: Sports whale min size (they trade smaller but sharper)
SPORTS_WHALE_MIN  = 300

# 3-Stage expansion thresholds
STAGE2_TRIGGER    = 5   # expand to Stage 2 if fewer than 5 markets in Stage 1
STAGE3_TRIGGER    = 3   # expand to Stage 3 if fewer than 3 markets in Stage 2

# Stage parameters
STAGE_CONFIG = {
    1: {"min_days": 1, "max_days": 7,  "whale_min": 400,  "tier1_div": 0.10, "tier2_div": 0.06},
    2: {"min_days": 1, "max_days": 21, "whale_min": 1000, "tier1_div": 0.08, "tier2_div": 0.05},
    3: {"min_days": 1, "max_days": 30, "whale_min": 2500, "tier1_div": 0.07, "tier2_div": 0.04},
}

RESOLUTION_MIN_DAYS = 1
RESOLUTION_MAX_DAYS = 7   # overridden by stage logic

TOTAL_MARKETS_TARGET = 500
PAGE_SIZE            = 100

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")

SIGNALS_OUTPUT = os.path.join(os.path.dirname(__file__), "whale_signals.json")

# --- CATEGORY DETECTION -------------------------------------------------------

CATEGORY_KEYWORDS = {
    "geopolitics": [
        "war", "iran", "russia", "ukraine", "israel", "gaza", "nato",
        "sanction", "nuclear", "ceasefire", "conflict", "military", "attack",
        "strike", "invasion", "troops", "missile",
    ],
    "economics": [
        "fed", "interest rate", "inflation", "gdp", "recession", "unemployment",
        "tariff", "trade", "debt", "deficit", "treasury", "cpi", "pce",
        "shutdown", "budget", "federal reserve",
    ],
    "entertainment": [
        "oscar", "academy award", "grammy", "emmy", "golden globe", "box office",
        "film", "movie", "album", "award",
    ],
    "sports": [
        "nba", "nfl", "nhl", "mlb", "tennis", "soccer", "football", "basketball",
        "baseball", "hockey", "mls", "ufc", "f1", "formula", "match", "game",
        "series", "championship", "playoff", "tournament", "wimbledon", "bnp",
        "open", "cup", "league", "warriors", "lakers", "celtics",
    ],
    "crypto": [
        "bitcoin", "btc", "ethereum", "eth", "crypto", "coin", "token",
        "blockchain", "defi", "solana", "base",
    ],
    "politics": [
        "election", "president", "congress", "senate", "vote", "poll",
        "democrat", "republican", "trump", "biden", "harris",
    ],
}

CATEGORY_PRIORITY = {
    "geopolitics":   1,
    "economics":     2,
    "entertainment": 3,
    "sports":        4,
    "politics":      5,
    "crypto":        6,
    "other":         7,
}

def detect_category(question: str) -> str:
    """Classify market question into a category based on keywords."""
    q = question.lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in q for kw in keywords):
            return cat
    return "other"


# --- MARKETS ------------------------------------------------------------------

def get_active_markets(total=TOTAL_MARKETS_TARGET, page_size=PAGE_SIZE):
    markets = []
    offset  = 0
    page    = 1

    while len(markets) < total:
        try:
            resp = requests.get(
                f"{GAMMA_API}/markets",
                params={
                    "active":  "true",
                    "closed":  "false",
                    "limit":   page_size,
                    "offset":  offset,
                },
                timeout=10
            )
            resp.raise_for_status()
            data  = resp.json()
            batch = data if isinstance(data, list) else data.get("data", [])

            if not batch:
                print(f"[+] Pagination stopped at page {page} (empty response)")
                break

            markets.extend(batch)
            print(f"[+] Page {page}: fetched {len(batch)} markets (total: {len(markets)})")

            if len(batch) < page_size:
                break

            offset += page_size
            page   += 1

        except Exception as e:
            print(f"[x] Failed to fetch page {page}: {e}")
            break

    print(f"[+] Total fetched: {len(markets)} active markets")
    return markets[:total]


def filter_liquid_markets(markets):
    """
    v5: Filter by LIQUIDITY only (volume field is broken in Gamma API).
    Also attaches _category to each market.
    """
    liquid = []
    for m in markets:
        try:
            liquidity = float(m.get("liquidity", 0) or 0)
            if liquidity >= MIN_LIQUIDITY:
                m["_category"] = detect_category(m.get("question", ""))
                liquid.append(m)
        except (ValueError, TypeError):
            continue
    print(f"[+] {len(liquid)} markets with >${MIN_LIQUIDITY:,} liquidity")
    return liquid


def filter_by_resolution(markets, min_days=RESOLUTION_MIN_DAYS, max_days=RESOLUTION_MAX_DAYS):
    filtered = []
    now      = datetime.now(timezone.utc)
    skipped_past    = 0
    skipped_too_far = 0
    skipped_no_date = 0

    for m in markets:
        end_str = (m.get("endDateIso") or m.get("end_date_iso") or
                   m.get("endDate")    or m.get("end_date") or "")

        if not end_str:
            skipped_no_date += 1
            continue

        try:
            end_clean = end_str.replace("Z", "+00:00")
            end_dt    = datetime.fromisoformat(end_clean)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
            days_left = (end_dt - now).days

            if days_left < min_days:
                skipped_past += 1
                continue
            if days_left > max_days:
                skipped_too_far += 1
                continue

            m["_days_to_resolve"] = days_left
            m["_end_date_iso"]    = end_str
            filtered.append(m)

        except Exception:
            skipped_no_date += 1
            continue

    print(f"[+] Resolution filter ({min_days}-{max_days} days): "
          f"{len(filtered)} markets pass "
          f"(skipped: {skipped_past} expired, {skipped_too_far} too far, {skipped_no_date} no date)")
    return filtered


def run_stage_expansion(liquid_markets, force_stage=None):
    """
    v5 NEW: 3-Stage Dynamic Window Expansion.
    Stage 1 NORMAL:    1-7d   -- try first always
    Stage 2 EXPANSION: 1-21d  -- if Stage 1 returns < 5 markets
    Stage 3 DEEP SCAN: 1-30d  -- if Stage 2 returns < 3 markets
    Returns (markets, stage_used, stage_cfg)
    """
    if force_stage is not None:
        cfg = STAGE_CONFIG[force_stage]
        print(f"[i] Stage {force_stage} FORCED by --stage flag")
        markets = filter_by_resolution(liquid_markets,
                                       min_days=cfg["min_days"],
                                       max_days=cfg["max_days"])
        return markets, force_stage, cfg

    # Stage 1
    cfg1 = STAGE_CONFIG[1]
    markets = filter_by_resolution(liquid_markets,
                                   min_days=cfg1["min_days"],
                                   max_days=cfg1["max_days"])
    if len(markets) >= STAGE2_TRIGGER:
        print(f"[+] Stage 1 NORMAL: {len(markets)} markets -- sufficient, proceeding")
        return markets, 1, cfg1

    # Stage 2
    print(f"[!] Stage 1 returned {len(markets)} markets (< {STAGE2_TRIGGER}) -- expanding to Stage 2")
    cfg2 = STAGE_CONFIG[2]
    markets = filter_by_resolution(liquid_markets,
                                   min_days=cfg2["min_days"],
                                   max_days=cfg2["max_days"])
    if len(markets) >= STAGE3_TRIGGER:
        print(f"[+] Stage 2 EXPANSION: {len(markets)} markets -- sufficient, proceeding")
        return markets, 2, cfg2

    # Stage 3
    print(f"[!] Stage 2 returned {len(markets)} markets (< {STAGE3_TRIGGER}) -- entering Stage 3 DEEP SCAN")
    cfg3 = STAGE_CONFIG[3]
    markets = filter_by_resolution(liquid_markets,
                                   min_days=cfg3["min_days"],
                                   max_days=cfg3["max_days"])
    print(f"[+] Stage 3 DEEP SCAN: {len(markets)} markets")
    return markets, 3, cfg3


# --- TRADES -------------------------------------------------------------------

def get_recent_trades(condition_id, limit=100):
    try:
        resp = requests.get(
            f"{DATA_API}/trades",
            params={"market": condition_id, "limit": limit, "offset": 0},
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else data.get("data", [])
    except Exception as e:
        print(f"  [x] Trades failed for {condition_id[:12]}...: {e}")
        return []


def find_whale_trades(trades, market_liquidity, is_sports=False):
    """
    v5: Find whale trades with impact ratio filter (ChatGPT insight).
    Sports markets use lower min size ($300 vs $400).
    Impact ratio: trade_size / liquidity >= MIN_IMPACT_RATIO.
    """
    size_threshold = SPORTS_WHALE_MIN if is_sports else WHALE_MIN_SIZE
    whales = []
    for trade in trades:
        try:
            usd = float(trade.get("usdcSize") or trade.get("size", 0) or 0)
            if usd < size_threshold:
                continue

            # v5 NEW: Impact ratio -- $500 in $200K market is NOT a whale
            liq = max(market_liquidity, 1)
            impact_ratio = usd / liq
            if impact_ratio < MIN_IMPACT_RATIO:
                continue

            whales.append({
                "wallet":       trade.get("proxyWallet", "unknown"),
                "direction":    trade.get("side", "BUY").upper(),
                "size_usd":     round(usd, 2),
                "price":        round(float(trade.get("price", 0.5)), 4),
                "impact_ratio": round(impact_ratio, 5),
            })
        except (ValueError, TypeError):
            continue
    return whales


# --- WALLET ANALYSIS ----------------------------------------------------------

def qualify_whale(address):
    if address == "unknown":
        return False, None, 0
    return True, None, 0


# --- SIGNAL -------------------------------------------------------------------

def calculate_signal(whale_trade, yes_price, win_rate, trade_count,
                     stage_cfg, is_sports=False):
    """v5: Calculate signal tier using stage-aware thresholds + sports premium."""
    price       = whale_trade["price"]
    whale_prob  = price
    market_prob = float(yes_price) if yes_price else 0.5
    divergence  = abs(whale_prob - market_prob)

    t1 = stage_cfg["tier1_div"]
    t2 = stage_cfg["tier2_div"]

    if is_sports:
        t1 += SPORTS_DIV_PREMIUM
        t2 += SPORTS_DIV_PREMIUM

    tier = (1 if divergence >= t1 else
            2 if divergence >= t2 else 0)

    return {
        "tier":         tier,
        "divergence":   round(divergence, 4),
        "whale_prob":   round(whale_prob, 4),
        "market_prob":  round(market_prob, 4),
        "win_rate":     win_rate,
        "trade_count":  trade_count,
        "impact_ratio": whale_trade.get("impact_ratio", 0),
        "is_sports":    is_sports,
    }


# --- TELEGRAM (human mode only) -----------------------------------------------

def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[!] Telegram not configured - console only")
        print(message)
        return False
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message},
            timeout=10
        ).raise_for_status()
        print("[+] Telegram alert sent")
        return True
    except Exception as e:
        print(f"[x] Telegram failed: {e}")
        return False


def format_signal(market, wt, signal, stage):
    emoji  = "!! WHALE SIGNAL !!" if signal["tier"] == 1 else "?? WHALE SIGNAL ??"
    label  = "TIER 1 - ACT" if signal["tier"] == 1 else "TIER 2 - MONITOR"
    name   = market.get("question", "Unknown")[:60]
    days   = market.get("_days_to_resolve", "?")
    cat    = market.get("_category", "other").upper()
    sports_note = " [SPORTS +2% premium applied]" if signal["is_sports"] else ""
    stage_label = {1: "Normal", 2: "Expansion", 3: "Deep Scan"}.get(stage, "?")
    return (
        f"{emoji}  [{cat}]\n\n"
        f"Market: {name}\n"
        f"Resolves in: {days} days\n"
        f"Direction: {wt['direction']}  Size: ${wt['size_usd']:,.2f}\n"
        f"Impact ratio: {wt['impact_ratio']:.4f} ({wt['impact_ratio']*100:.2f}% of pool)\n"
        f"Whale price: {wt['price']:.3f}\n\n"
        f"Market YES: {signal['market_prob']:.3f} ({signal['market_prob']*100:.1f}%)\n"
        f"Whale implied: {signal['whale_prob']:.3f} ({signal['whale_prob']*100:.1f}%)\n"
        f"Divergence: +{signal['divergence']*100:.1f}%{sports_note}\n\n"
        f"Signal: {label}\n"
        f"Stage: {stage_label}\n"
        f"Reply PAPER YES to enter trade."
    )


# --- MAIN ---------------------------------------------------------------------

def scan_markets(min_size=None, target_market_id=None,
                 json_output=False, skip_resolution_filter=False,
                 force_stage=None):

    print("\n" + "="*60)
    print(f"WHALE TRACKER v5 - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Thresholds: Tier1={TIER1_DIVERGENCE*100:.0f}% | Tier2={TIER2_DIVERGENCE*100:.0f}% | "
          f"MinLiq=${MIN_LIQUIDITY:,} | WhaleMin=${WHALE_MIN_SIZE} | ImpactRatio={MIN_IMPACT_RATIO}")
    print("="*60)

    if min_size:
        global WHALE_MIN_SIZE
        WHALE_MIN_SIZE = min_size

    signals_found = []
    stage_used    = 1
    stage_cfg     = STAGE_CONFIG[1]

    if target_market_id:
        markets = [{"conditionId": target_market_id}]
        print(f"[i] Single market mode: {target_market_id}")
    else:
        all_markets    = get_active_markets(total=TOTAL_MARKETS_TARGET)
        liquid_markets = filter_liquid_markets(all_markets)

        if skip_resolution_filter:
            markets   = liquid_markets
            stage_cfg = STAGE_CONFIG[1]
            print(f"[i] Resolution filter SKIPPED (--no-resolution-filter flag)")
        else:
            markets, stage_used, stage_cfg = run_stage_expansion(
                liquid_markets, force_stage=force_stage
            )

        print(f"\n[>] Active stage: {stage_used} | "
              f"Window: {stage_cfg['min_days']}-{stage_cfg['max_days']}d | "
              f"WhaleMin: ${stage_cfg['whale_min']} | "
              f"Tier1: {stage_cfg['tier1_div']*100:.0f}%")

    # Sort by category priority before scanning
    if not target_market_id:
        markets.sort(key=lambda m: CATEGORY_PRIORITY.get(m.get("_category", "other"), 99))

    print(f"\n[>] Scanning {len(markets)} markets for whale activity...\n")

    SKIP_THRESHOLD = 0.05

    for market in markets:
        cid = (market.get("conditionId") or market.get("condition_id") or
               market.get("id", ""))
        if not cid:
            continue

        name       = market.get("question", cid[:20])[:40]
        category   = market.get("_category", "other")
        is_sports  = (category == "sports")
        liquidity  = float(market.get("liquidity", 0) or 0)

        trades = get_recent_trades(cid)
        if not trades:
            continue

        whales = find_whale_trades(trades, market_liquidity=liquidity, is_sports=is_sports)
        if not whales:
            continue

        print(f"[!] {len(whales)} whale trade(s) [{category.upper()}]: {name}")

        for wt in whales:
            ok, win_rate, count = qualify_whale(wt["wallet"])
            if not ok:
                continue

            try:
                prices    = market.get("outcomePrices", "")
                yes_price = float(json.loads(prices)[0]) if prices else 0.5
            except Exception:
                yes_price = 0.5

            sig = calculate_signal(wt, yes_price, win_rate, count,
                                   stage_cfg=stage_cfg, is_sports=is_sports)
            if sig["tier"] == 0:
                continue
            if yes_price < SKIP_THRESHOLD or yes_price > (1 - SKIP_THRESHOLD):
                continue

            print(f"  [*] TIER {sig['tier']} [{category.upper()}] - "
                  f"Divergence: {sig['divergence']*100:.1f}% - "
                  f"Size: ${wt['size_usd']:,.0f} - "
                  f"Impact: {wt['impact_ratio']*100:.2f}% - "
                  f"Resolves: {market.get('_days_to_resolve', '?')}d")

            if any(s["market_id"] == cid for s in signals_found):
                continue

            signals_found.append({
                "market_id":       cid,
                "market_name":     market.get("question", "Unknown"),
                "market_slug":     market.get("slug", ""),
                "market_category": category,
                "yes_price":       yes_price,
                "tier":            sig["tier"],
                "divergence":      sig["divergence"],
                "whale_prob":      sig["whale_prob"],
                "market_prob":     sig["market_prob"],
                "direction":       wt["direction"],
                "size_usd":        wt["size_usd"],
                "impact_ratio":    wt["impact_ratio"],
                "wallet":          wt["wallet"],
                "end_date_iso":    market.get("_end_date_iso", ""),
                "days_to_resolve": market.get("_days_to_resolve", 0),
                "stage_used":      stage_used,
                "scanned_at":      datetime.now(timezone.utc).isoformat(),
            })

            if not json_output:
                send_telegram(format_signal(market, wt, sig, stage_used))

    print("\n" + "="*60)
    print(f"SCAN COMPLETE -- Stage {stage_used} -- {len(signals_found)} signal(s) found")
    print("="*60)

    if not signals_found:
        stage_name = {1: "Normal", 2: "Expansion", 3: "Deep Scan"}.get(stage_used, "?")
        print(f"[i] No qualifying signals (Stage {stage_used}: {stage_name}). "
              f"Patience is a position.")
    else:
        for s in signals_found:
            days = s.get("days_to_resolve", "?")
            cat  = s.get("market_category", "?").upper()
            print(f"  Tier {s['tier']} [{cat}]: {s['market_name'][:50]} "
                  f"| +{s['divergence']*100:.1f}% div "
                  f"| impact {s['impact_ratio']*100:.2f}% "
                  f"| resolves {days}d")

    if json_output:
        output = {
            "scanned_at":      datetime.now(timezone.utc).isoformat(),
            "signals_count":   len(signals_found),
            "markets_scanned": len(markets),
            "stage_used":      stage_used,
            "signals":         signals_found,
        }
        with open(SIGNALS_OUTPUT, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\n[+] Signals written to {SIGNALS_OUTPUT}")
        print(f"[+] Bridge will process {len(signals_found)} signal(s)")

    return signals_found


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Polymarket Whale Signal Detection v5")
    parser.add_argument("--min-size", type=float, default=WHALE_MIN_SIZE,
                        help=f"Min whale trade size USD (default: {WHALE_MIN_SIZE})")
    parser.add_argument("--market-id", type=str, default=None,
                        help="Scan a specific market by condition ID")
    parser.add_argument("--json", action="store_true", default=False,
                        help="Output signals as JSON to whale_signals.json (bridge mode)")
    parser.add_argument("--no-resolution-filter", action="store_true", default=False,
                        help="Skip resolution filter (scan all markets)")
    parser.add_argument("--stage", type=int, choices=[1, 2, 3], default=None,
                        help="Force a specific expansion stage (1=Normal, 2=Expansion, 3=DeepScan)")
    args = parser.parse_args()

    scan_markets(
        min_size=args.min_size,
        target_market_id=args.market_id,
        json_output=args.json,
        skip_resolution_filter=args.no_resolution_filter,
        force_stage=args.stage,
    )
    sys.exit(0)
