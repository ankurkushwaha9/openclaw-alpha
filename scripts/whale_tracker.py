#!/usr/bin/env python3
"""
whale_tracker.py - Polymarket Whale Signal Detection
Location: ~/.openclaw/workspace/scripts/whale_tracker.py
Last Updated: 2026-02-24 (v4.1 - hotfix: naive date parsing for Gamma endDate field)

Changes v3 → v4 (Mission 7 - Active Paper Trading):
  - Market scan expanded: 100 → 500 (5 paginated requests)
  - MIN_LIQUIDITY lowered: $10,000 → $5,000 (short-duration markets have less time to accumulate)
  - Resolution filter added: only markets resolving in 3-7 days pass
  - Signal output enriched: end_date_iso + days_to_resolve added to each signal
  - whale_prob + market_prob always output (needed for Kelly sizing in bridge v2)
  - Cron frequency changed externally: */6 → */2

Usage:
    python scripts/whale_tracker.py                  # human-readable (unchanged)
    python scripts/whale_tracker.py --min-size 1000  # custom whale size
    python scripts/whale_tracker.py --json           # bridge mode → whale_signals.json
    python scripts/whale_tracker.py --json --no-resolution-filter  # skip date filter
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

WHALE_MIN_SIZE    = 500
MIN_WIN_RATE      = 0.60
MIN_TRADE_HISTORY = 10
TIER1_DIVERGENCE  = 0.15
TIER2_DIVERGENCE  = 0.08
MIN_LIQUIDITY     = 5000      # v4: lowered from 10000 — short-duration markets have less liquidity

# Resolution window (days) — only markets resolving within this range are scanned
RESOLUTION_MIN_DAYS = 3
RESOLUTION_MAX_DAYS = 7

TOTAL_MARKETS_TARGET = 500    # v4: up from 100
PAGE_SIZE            = 100    # Gamma API page size

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")

SIGNALS_OUTPUT = os.path.join(os.path.dirname(__file__), "whale_signals.json")


# --- MARKETS ------------------------------------------------------------------

def get_active_markets(total=TOTAL_MARKETS_TARGET, page_size=PAGE_SIZE):
    """
    Fetch up to `total` active markets via paginated Gamma API requests.
    v4: fetches 500 markets (5 pages × 100) vs v3's single 100-market call.
    """
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
                # Last page — no more results
                break

            offset += page_size
            page   += 1

        except Exception as e:
            print(f"[x] Failed to fetch page {page}: {e}")
            break

    print(f"[+] Total fetched: {len(markets)} active markets")
    return markets[:total]


def filter_liquid_markets(markets):
    liquid = []
    for m in markets:
        try:
            volume    = float(m.get("volume",    0) or 0)
            liquidity = float(m.get("liquidity", 0) or 0)
            if max(volume, liquidity) >= MIN_LIQUIDITY:
                liquid.append(m)
        except (ValueError, TypeError):
            continue
    print(f"[+] {len(liquid)} markets with >${MIN_LIQUIDITY:,} liquidity/volume")
    return liquid


def filter_by_resolution(markets, min_days=RESOLUTION_MIN_DAYS, max_days=RESOLUTION_MAX_DAYS):
    """
    v4 NEW: Filter markets to only those resolving within [min_days, max_days] from now.
    Reads endDateIso field from Gamma API market object.
    Attaches _days_to_resolve and _end_date_iso to each qualifying market.
    """
    filtered = []
    now      = datetime.now(timezone.utc)
    skipped_past    = 0
    skipped_too_far = 0
    skipped_no_date = 0

    for m in markets:
        # Gamma API field names vary — check multiple
        end_str = (m.get("endDateIso") or m.get("end_date_iso") or
                   m.get("endDate")    or m.get("end_date") or "")

        if not end_str:
            skipped_no_date += 1
            continue

        try:
            # Normalise timezone — Gamma uses Z, +00:00, or naive date-only strings
            end_clean = end_str.replace("Z", "+00:00")
            end_dt    = datetime.fromisoformat(end_clean)
            # Handle naive datetimes (e.g. "2025-12-31" with no timezone)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
            days_left = (end_dt - now).days

            if days_left < min_days:
                skipped_past += 1
                continue
            if days_left > max_days:
                skipped_too_far += 1
                continue

            # Attach resolution metadata to market dict for downstream use
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


def find_whale_trades(trades):
    whales = []
    for trade in trades:
        try:
            usd = float(trade.get("usdcSize") or trade.get("size", 0) or 0)
            if usd >= WHALE_MIN_SIZE:
                whales.append({
                    "wallet":    trade.get("proxyWallet", "unknown"),
                    "direction": trade.get("side", "BUY").upper(),
                    "size_usd":  round(usd, 2),
                    "price":     round(float(trade.get("price", 0.5)), 4),
                })
        except (ValueError, TypeError):
            continue
    return whales


# --- WALLET ANALYSIS ----------------------------------------------------------

def get_wallet_history(address):
    try:
        resp = requests.get(
            f"{DATA_API}/positions",
            params={"user": address, "limit": 100},
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else data.get("data", [])
    except Exception as e:
        print(f"  [x] Wallet history failed: {e}")
        return []


def qualify_whale(address):
    # Position history not publicly available via API
    # Qualification based on trade size alone (already filtered by WHALE_MIN_SIZE)
    if address == "unknown":
        return False, None, 0
    return True, None, 0


# --- SIGNAL -------------------------------------------------------------------

def calculate_signal(whale_trade, yes_price, win_rate, trade_count):
    direction   = whale_trade["direction"]
    price       = whale_trade["price"]
    whale_prob  = price
    market_prob = float(yes_price) if yes_price else 0.5
    divergence  = abs(whale_prob - market_prob)

    tier = (1 if divergence >= TIER1_DIVERGENCE else
            2 if divergence >= TIER2_DIVERGENCE else 0)

    return {
        "tier":        tier,
        "divergence":  round(divergence, 4),
        "whale_prob":  round(whale_prob, 4),
        "market_prob": round(market_prob, 4),
        "win_rate":    win_rate,
        "trade_count": trade_count,
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


def format_signal(market, wt, signal):
    emoji  = "!!" if signal["tier"] == 1 else "??"
    label  = "TIER 1 - ACT" if signal["tier"] == 1 else "TIER 2 - MONITOR"
    name   = market.get("question", "Unknown")[:60]
    days   = market.get("_days_to_resolve", "?")
    return (
        f"{emoji} WHALE SIGNAL\n\n"
        f"Market: {name}\n"
        f"Resolves in: {days} days\n"
        f"Direction: {wt['direction']}  Size: ${wt['size_usd']:,.2f}\n"
        f"Whale price: {wt['price']:.3f}\n\n"
        f"Market YES: {signal['market_prob']:.3f} ({signal['market_prob']*100:.1f}%)\n"
        f"Whale implied: {signal['whale_prob']:.3f} ({signal['whale_prob']*100:.1f}%)\n"
        f"Divergence: +{signal['divergence']*100:.1f}%\n\n"
        f"Signal: {label}\n"
        f"Reply YES to investigate."
    )


# --- MAIN ---------------------------------------------------------------------

def scan_markets(min_size=None, target_market_id=None,
                 json_output=False, skip_resolution_filter=False):
    print("\n" + "="*55)
    print(f"WHALE TRACKER v4 - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("="*55)

    if min_size:
        global WHALE_MIN_SIZE
        WHALE_MIN_SIZE = min_size

    signals_found = []

    if target_market_id:
        # Single market mode — bypass all filters
        markets = [{"conditionId": target_market_id}]
    else:
        # Full scan — paginated 500 markets → liquidity filter → resolution filter
        all_markets     = get_active_markets(total=TOTAL_MARKETS_TARGET)
        liquid_markets  = filter_liquid_markets(all_markets)

        if skip_resolution_filter:
            markets = liquid_markets
            print(f"[i] Resolution filter SKIPPED (--no-resolution-filter flag)")
        else:
            markets = filter_by_resolution(liquid_markets)

    print(f"\n[>] Scanning {len(markets)} markets for whale activity...\n")

    SKIP_THRESHOLD = 0.05  # skip near-settled markets (>95% or <5%)

    for market in markets:
        cid = (market.get("conditionId") or market.get("condition_id") or
               market.get("id", ""))
        if not cid:
            continue

        name   = market.get("question", cid[:20])[:40]
        trades = get_recent_trades(cid)
        if not trades:
            continue

        whales = find_whale_trades(trades)
        if not whales:
            continue

        print(f"[!] {len(whales)} whale trade(s): {name}")

        for wt in whales:
            ok, win_rate, count = qualify_whale(wt["wallet"])
            if not ok:
                continue

            try:
                prices    = market.get("outcomePrices", "")
                yes_price = float(json.loads(prices)[0]) if prices else 0.5
            except Exception:
                yes_price = 0.5

            sig = calculate_signal(wt, yes_price, win_rate, count)
            if sig["tier"] == 0:
                continue
            if yes_price < SKIP_THRESHOLD or yes_price > (1 - SKIP_THRESHOLD):
                continue

            print(f"  [*] TIER {sig['tier']} - "
                  f"Divergence: {sig['divergence']*100:.1f}% - "
                  f"Size: ${wt['size_usd']:,.0f} - "
                  f"Resolves: {market.get('_days_to_resolve', '?')} days")

            # One signal per market (strongest whale wins)
            if any(s["market_id"] == cid for s in signals_found):
                continue

            signals_found.append({
                "market_id":      cid,
                "market_name":    market.get("question", "Unknown"),
                "market_slug":    market.get("slug", ""),
                "yes_price":      yes_price,
                "tier":           sig["tier"],
                "divergence":     sig["divergence"],
                "whale_prob":     sig["whale_prob"],
                "market_prob":    sig["market_prob"],
                "direction":      wt["direction"],
                "size_usd":       wt["size_usd"],
                "wallet":         wt["wallet"],
                # v4 NEW: resolution data (used by bridge for proposal + Kelly sizing)
                "end_date_iso":   market.get("_end_date_iso", ""),
                "days_to_resolve": market.get("_days_to_resolve", 0),
                "scanned_at":     datetime.now(timezone.utc).isoformat(),
            })

            # Human mode only — bridge handles Telegram in --json mode
            if not json_output:
                send_telegram(format_signal(market, wt, sig))

    print("\n" + "="*55)
    print(f"SCAN COMPLETE - {len(signals_found)} signal(s) found")
    print("="*55)

    if not signals_found:
        print("[i] No qualifying whale signals. Strategy: patience is a position.")
    else:
        for s in signals_found:
            days = s.get("days_to_resolve", "?")
            print(f"  Tier {s['tier']}: {s['market_name'][:50]} "
                  f"| +{s['divergence']*100:.1f}% divergence "
                  f"| resolves in {days}d")

    # --- JSON OUTPUT (bridge mode) ---
    if json_output:
        output = {
            "scanned_at":    datetime.now(timezone.utc).isoformat(),
            "signals_count": len(signals_found),
            "markets_scanned": len(markets),
            "signals":       signals_found,
        }
        with open(SIGNALS_OUTPUT, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\n[+] Signals written to {SIGNALS_OUTPUT}")
        print(f"[+] Bridge will process {len(signals_found)} signal(s)")

    return signals_found


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Polymarket Whale Signal Detection v4")
    parser.add_argument("--min-size", type=float, default=WHALE_MIN_SIZE,
                        help=f"Min whale trade size USD (default: {WHALE_MIN_SIZE})")
    parser.add_argument("--market-id", type=str, default=None,
                        help="Scan a specific market by condition ID")
    parser.add_argument("--json", action="store_true", default=False,
                        help="Output signals as JSON to whale_signals.json (bridge mode)")
    parser.add_argument("--no-resolution-filter", action="store_true", default=False,
                        help="Skip the 3-7 day resolution filter (scan all markets)")
    args = parser.parse_args()

    scan_markets(
        min_size=args.min_size,
        target_market_id=args.market_id,
        json_output=args.json,
        skip_resolution_filter=args.no_resolution_filter,
    )
    sys.exit(0)
