#!/usr/bin/env python3
"""
whale_tracker.py - Polymarket Whale Signal Detection
Last Updated: 2026-03-10 (v6.3 - Phase 4: informed wallet detection + smart/elite tiers)

Changes v5.2 -> v6.0:
  BUG-021 FIX: Now fetches BOTH /markets AND /events endpoints in parallel.
    /markets: flat list (standalone markets) -- was the ONLY source before v6.0
    /events:  themed event containers with nested markets[] arrays
    Merge by conditionId -- /markets wins on price/liquidity conflicts.
    Adds all Iran/geopolitics/Hormuz markets previously invisible to scanner.

  NEW GUARDS (3-LLM consensus: Claude + Gemini + ChatGPT):
    Guard 1: negRisk=True          -> skip (multi-outcome pricing unreliable)
    Guard 2: acceptingOrders=False -> skip (phantom/untradeable market)
    Guard 3: outcomePrices=null    -> skip (no price data)

  NULL DATE HANDLING:
    endDate=null -> _days_to_resolve=999, _null_date=True (Open Horizon tier)
    Null-date markets: min_liq=$25,000 (raised bar), whale_min=$5,000
    Always scanned alongside regular stage markets.

  ENRICHMENT:
    _parent_event_title attached to event sub-markets (shown in logs + signals)

Changes v5.1 -> v5.2:
  BUG-015 FIX: Whale price now direction-adjusted.

Changes v5.0 -> v5.1:
  4-STAGE SYSTEM, DYNAMIC DIVERGENCE, MANIPULATION GUARDRAIL, WHALE_MIN SCALES
"""
import os, sys, json, requests, argparse
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

GAMMA_API = "https://gamma-api.polymarket.com"
DATA_API  = "https://data-api.polymarket.com"

WHALE_MIN_SIZE      = 400
MIN_WIN_RATE        = 0.60
MIN_TRADE_HISTORY   = 10
MIN_LIQUIDITY       = 10000
NULL_DATE_MIN_LIQ   = 25000
NULL_DATE_WHALE_MIN = 5000
MIN_IMPACT_RATIO    = 0.003
SPORTS_DIV_PREMIUM  = 0.02
SPORTS_WHALE_MIN    = 300
MAX_HORIZON_DAYS    = 75
STAGE2_TRIGGER = 5
STAGE3_TRIGGER = 1
STAGE4_TRIGGER = 3

# Phase 2 -- Accumulation Clustering
CLUSTER_WINDOW        = 1800   # 30 minutes in seconds
MIN_TRADES_IN_CLUSTER = 3
MIN_CLUSTER_TOTAL     = 900    # USDC

# Phase 3 -- Liquidity Shock Detection
LIQUIDITY_SHOCK_PCT    = 0.20  # 20% drop from last scan triggers shock flag
LIQUIDITY_HISTORY_FILE = os.path.join(os.path.dirname(__file__), '..', 'paper_trading', 'liquidity_history.json')

# Phase 4 -- Informed Wallet Detection
EVAL_DELAY_HOURS      = 6      # hours after trade to evaluate price movement
MIN_TRADES_SCORING    = 5      # minimum trades before wallet gets a reputation score
SMART_WALLET_SCORE    = 0.65   # score threshold for Smart Wallet tier
ELITE_WALLET_SCORE    = 0.80   # score threshold for Elite Wallet tier
MIN_PRICE_MOVE        = 0.04   # minimum price move to count as meaningful win
MM_MIN_TRADES         = 50     # market maker detection: trade count threshold
MM_MAX_ACCURACY       = 0.55   # market maker detection: accuracy ceiling
WALLET_STATS_FILE     = os.path.join(os.path.dirname(__file__), '..', 'paper_trading', 'wallet_stats.json')
PENDING_EVALS_FILE    = os.path.join(os.path.dirname(__file__), '..', 'paper_trading', 'pending_wallet_evals.json')

STAGE_CONFIG = {
    1: {"min_days": 1,  "max_days": 7,  "whale_min": 400,  "label": "TACTICAL"},
    2: {"min_days": 8,  "max_days": 21, "whale_min": 1500, "label": "STRATEGIC"},
    3: {"min_days": 22, "max_days": 45, "whale_min": 3500, "label": "MACRO"},
    4: {"min_days": 46, "max_days": 75, "whale_min": 7000, "label": "EXTREME"},
}

TOTAL_MARKETS_TARGET = 500
TOTAL_EVENTS_TARGET  = 1000
PAGE_SIZE            = 100
TELEGRAM_BOT_TOKEN   = os.getenv("TEMEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID     = os.getenv("TELEGRAM_CHAT_ID")
SIGNALS_OUTPUT       = os.path.join(os.path.dirname(__file__), "whale_signals.json")

def get_divergence_threshold(days, is_sports=False):
    if days <= 7:    base = 0.08
    elif days <= 21: base = 0.06
    elif days <= 45: base = 0.09
    else:            base = 0.11
    return base + (SPORTS_DIV_PREMIUM if is_sports else 0)

def get_whale_min_for_days(days, is_sports=False):
    if is_sports:    return SPORTS_WHALE_MIN
    if days == 999:  return NULL_DATE_WHALE_MIN
    if days <= 14:   return 400
    elif days <= 30: return 1500
    elif days <= 60: return 3500
    else:            return 7000

CATEGORY_KEYWORDS = {
    "geopolitics":   ["war","iran","russia","ukraine","israel","gaza","nato","sanction","nuclear","ceasefire","conflict","military","attack","strike","invasion","troops","missile","hormuz","regime","forces enter"],
    "economics":     ["fed","interest rate","inflation","gdp","recession","unemployment","tariff","trade","debt","deficit","treasury","cpi","pce","shutdown","budget","federal reserve"],
    "entertainment": ["oscar","academy award","grammy","emmy","golden globe","box office","film","movie","album","award"],
    "sports":        ["nba","nfl","nhl","mlb","tennis","soccer","football","basketball","baseball","hockey","mls","ufc","f1","formula","match","game","series","championship","playoff","tournament","wimbledon","bnp","open","cup","league","warriors","lakers","celtics","masters","pga"],
    "crypto":        ["bitcoin","btc","ethereum","eth","crypto","coin","token","blockchain","defi","solana","base"],
    "politics":      ["election","president","congress","senate","vote","poll","democrat","republican","trump","biden","harris"],
}
CATEGORY_PRIORITY = {"geopolitics":1,"economics":2,"entertainment":3,"sports":4,"politics":5,"crypto":6,"other":7}

def detect_category(q):
    q = q.lower()
    for cat, kws in CATEGORY_KEYWORDS.items():
        if any(kw in q for kw in kws): return cat
    return "other"

# --- DATA FETCHING (v6.0: TWOsources) ---

def fetch_markets(total=TOTAL_MARKETS_TARGET, page_size=PAGE_SIZE):
    """Original /markets endpoint fetch."""
    markets, offset, page = [], 0, 1
    while len(markets) < total:
        try:
            resp  = requests.get(f"{GAMMA_API}/markets", params={"active":"true","closed":"false","limit":page_size,"offset":offset}, timeout=10)
            resp.raise_for_status()
            data  = resp.json()
            batch = data if isinstance(data, list) else data.get("data", [])
            if not batch: print(f"[+] /markets stopped page {page}"); break
            markets.extend(batch)
            print(f"[+] Page {page}: {len(batch)} markets (total: {len(markets)})")
            if len(batch) < page_size: break
            offset += page_size; page += 1
        except Exception as e:
            print(f"[x] /markets page {page} failed: {e}"); break
    print(f"[+] /markets total: {len(markets)}")
    return markets[:total]

def fetch_events(total=TOTAL_EVENTS_TARGET, page_size=PAGE_SIZE):
    """NEW v6.0: /events endpoint -- source for Iran, Hormuz, ceasefire, geopolitics markets."""
    all_events, offset, page = [], 0, 1
    while len(all_events) < total:
        try:
            resp  = requests.get(f"{GAMMA_API}/events", params={"active":"true","closed":"false","limit":page_size,"offset":offset}, timeout=10)
            resp.raise_for_status()
            data  = resp.json()
            batch = data if isinstance(data, list) else data.get("data", [])
            if not batch: print(f"[+] /events stopped page {page}"); break
            all_events.extend(batch)
            if len(batch) < page_size: break
            offset += page_size; page += 1
        except Exception as e:
            print(f"[x] /events page {page} failed: {e}"); break

    flat = []
    for event in all_events:
        event_title = event.get("title", "")
        for m in event.get("markets", []):
            m["_parent_event_title"] = event_title
            m["_from_events_api"]    = True
            flat.append(m)

    print(f"[+] /events total: {len(all_events)} events -> {len(flat)} sub-markets flattened")
    return flat

def merge_market_sources(markets_flat, events_flat):
    """Merge /markets + /events by conditionId. /markets canonical for price/liquidity."""
    merged = {}

    for m in markets_flat:
        cid = m.get("conditionId") or m.get("condition_id") or m.get("id","")
        if cid: merged[cid] = m

    events_added = events_enriched = 0
    for m in events_flat:
        cid = m.get("conditionId") or m.get("condition_id") or m.get("id","")
        if not cid: continue
        if cid not in merged:
            merged[cid] = m
            events_added += 1
        else:
            existing     = merged[cid]
            existing_liq = float(existing.get("liquidityNum") or existing.get("liquidity") or 0)
            events_liq   = float(m.get("liquidityNum") or m.get("liquidity") or 0)
            if events_liq > existing_liq:
                existing["liquidity"]    = str(events_liq)
                existing["liquidityNum"] = events_liq
            if not existing.get("_parent_event_title") and m.get("_parent_event_title"):
                existing["_parent_event_title"] = m["_parent_event_title"]
            events_enriched += 1

    result = list(merged.values())
    print(f"[+] Merge: {len(markets_flat)} /markets + {events_added} new from /events ({events_enriched} enriched) = {len(result)} unique")
    return result

# --- FILTERING ---

def filter_liquid_markets(markets):
    """Filter + 3 new guards (v6.0): negRisk, acceptingOrders, outcomePrices."""
    liquid = []
    sk_negrisk = sk_notaccept = sk_nullprice = sk_liq = 0
    for m in markets:
        try:
            if m.get("negRisk") is True:         sk_negrisk   += 1; continue
            if m.get("acceptingOrders") is False: sk_notaccept += 1; continue
            if not m.get("outcomePrices"):        sk_nullprice += 1; continue
            liq     = float(m.get("liquidityNum") or m.get("liquidity") or 0)
            end_str = m.get("endDateIso") or m.get("endDate") or ""
            min_liq = NULL_DATE_MIN_LIQ if not end_str else MIN_LIQUIDITY
            if liq < min_liq: sk_liq += 1; continue
            m["_category"] = detect_category(m.get("question",""))
            liquid.append(m)
        except: continue
    print(f"[+] {len(liquid)} markets passed filters (skipped: {sk_negrisk} negRisk | {sk_notaccept} not accepting | {sk_nullprice} null price | {sk_liq} low liq)")
    return liquid

def filter_by_resolution(markets, min_days, max_days):
    """Filter by resolution window. Returns (dated_markets, null_date_markets)."""
    filtered = []
    null_date = []
    now = datetime.now(timezone.utc)
    sp = sf = sn = 0
    for m in markets:
        end_str = m.get("endDateIso") or m.get("end_date_iso") or m.get("endDate") or m.get("end_date") or ""
        if not end_str:
            m["_days_to_resolve"] = 999
            m["_end_date_iso"]    = ""
            m["_null_date"]       = True
            null_date.append(m)
            sn += 1
            continue
        try:
            end_dt = datetime.fromisoformat(end_str.replace("Z","+00:00"))
            if end_dt.tzinfo is None: end_dt = end_dt.replace(tzinfo=timezone.utc)
            d = (end_dt - now).days
            if d < min_days: sp += 1; continue
            if d > max_days: sf += 1; continue
            m["_days_to_resolve"] = d
            m["_end_date_iso"]    = end_str
            m["_null_date"]       = False
            filtered.append(m)
        except: sn += 1
    print(f"[+] Resolution ({min_days}-{max_days}d): {len(filtered)} pass (skip: {sp} expired, {sf} too far, {sn} no date -> {len(null_date)} Open Horizon)")
    return filtered, null_date

def run_stage_expansion(liquid_markets, force_stage=None):
    """Stage expansion. Null-date Open Horizon markets always appended to scan list."""
    _, all_null_date = filter_by_resolution(liquid_markets, -9999, 9999)

    if force_stage is not None:
        cfg = STAGE_CONFIG[force_stage]
        dated, _ = filter_by_resolution(liquid_markets, cfg["min_days"], cfg["max_days"])
        print(f"[i] Stage {force_stage} ({cfg['label']}) FORCED | +{len(all_null_date)} Open Horizon")
        return dated + all_null_date, force_stage

    for sn in [1,2,3,4]:
        cfg     = STAGE_CONFIG[sn]
        dated,_ = filter_by_resolution(liquid_markets, cfg["min_days"], cfg["max_days"])
        trigger = {1:STAGE2_TRIGGER, 2:STAGE3_TRIGGER, 3:STAGE4_TRIGGER, 4:0}[sn]
        if len(dated) >= trigger or sn == 4:
            print(f"[+] Stage {sn} {cfg['label']}: {len(dated)} markets | +{len(all_null_date)} Open Horizon")
            return dated + all_null_date, sn
        print(f"[!] Stage {sn}: only {len(dated)} (< {trigger}) -- escalating")
    return all_null_date, 4

# --- SIGNAL DETECTION (unchanged from v5.2) ---

def get_recent_trades(cid, limit=100):
    try:
        resp = requests.get(f"{DATA_API}/trades", params={"market":cid,"limit":limit,"offset":0}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else data.get("data",[])
    except Exception as e:
        print(f"  [x] Trades failed {cid[:12]}: {e}"); return []

def find_whale_trades(trades, market_liquidity, days_to_resolve, is_sports=False):
    size_threshold = get_whale_min_for_days(days_to_resolve, is_sports)
    whales = []
    for trade in trades:
        try:
            usd = float(trade.get("usdcSize") or trade.get("size",0) or 0)
            if usd < size_threshold: continue
            liq    = max(market_liquidity, 1)
            impact = usd / liq
            if impact < MIN_IMPACT_RATIO: continue
            if usd > liq * 0.5:
                print(f"  [!] Manipulation guard: ${usd:,.0f} vs ${liq:,.0f} liq ({impact*100:.1f}%) -- skip")
                continue
            whales.append({
                "wallet":       trade.get("proxyWallet","unknown"),
                "direction":    trade.get("side","BUY").upper(),
                "size_usd":     round(usd, 2),
                "price":        round(float(trade.get("price",0.5)), 4),
                "outcome":      trade.get("outcome","Yes"),
                "impact_ratio": round(impact, 5),
            })
        except: continue
    return whales

def find_whale_clusters(trades, market_liquidity, days_to_resolve, is_sports=False):
    """
    Phase 2: Accumulation clustering.
    Groups trades by proxyWallet within CLUSTER_WINDOW seconds.
    Fires when a wallet makes >= MIN_TRADES_IN_CLUSTER trades totalling >= MIN_CLUSTER_TOTAL
    in the same direction within 30 minutes.
    """
    from collections import defaultdict
    wallet_trades = defaultdict(list)
    for trade in trades:
        try:
            wallet = trade.get("proxyWallet", "unknown")
            if wallet == "unknown": continue
            ts  = int(trade.get("timestamp", 0))
            usd = float(trade.get("usdcSize") or trade.get("size", 0) or 0)
            if usd <= 0 or ts <= 0: continue
            wallet_trades[wallet].append({
                "ts":      ts,
                "usd":     usd,
                "outcome": trade.get("outcome", "Yes"),
                "price":   float(trade.get("price", 0.5)),
            })
        except: continue

    clusters = []
    liq = max(market_liquidity, 1)

    for wallet, wtrades in wallet_trades.items():
        if len(wtrades) < MIN_TRADES_IN_CLUSTER: continue
        wtrades.sort(key=lambda t: t["ts"])
        n = len(wtrades)
        for start in range(n):
            window = [wtrades[start]]
            for end in range(start + 1, n):
                if wtrades[end]["ts"] - wtrades[start]["ts"] <= CLUSTER_WINDOW:
                    window.append(wtrades[end])
                else:
                    break
            if len(window) < MIN_TRADES_IN_CLUSTER: continue
            outcomes = set(t["outcome"] for t in window)
            if len(outcomes) > 1: continue  # mixed direction -- not coordinated
            total_usd = sum(t["usd"] for t in window)
            if total_usd < MIN_CLUSTER_TOTAL: continue
            impact = total_usd / liq
            if total_usd > liq * 0.5:
                print(f"  [!] Cluster manip guard: ${total_usd:,.0f} vs ${liq:,.0f} liq ({impact*100:.1f}%) -- skip")
                continue
            if impact < MIN_IMPACT_RATIO: continue
            outcome   = window[0]["outcome"]
            avg_price = sum(t["price"] for t in window) / len(window)
            span_mins = (window[-1]["ts"] - window[0]["ts"]) / 60
            clusters.append({
                "wallet":       wallet,
                "direction":    "BUY",
                "size_usd":     round(total_usd, 2),
                "price":        round(avg_price, 4),
                "outcome":      outcome,
                "impact_ratio": round(impact, 5),
                "trade_count":  len(window),
                "span_mins":    round(span_mins, 1),
                "signal_type":  "Whale Accumulation",
            })
            break  # one cluster per wallet per market
    return clusters

def load_liquidity_history():
    """Phase 3: Load persisted liquidity snapshots from previous scan."""
    try:
        with open(LIQUIDITY_HISTORY_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}  # safe first-run -- no history yet

def save_liquidity_history(history):
    """Phase 3: Persist liquidity snapshots for next scan comparison."""
    try:
        import tempfile, os as _os
        tmp = LIQUIDITY_HISTORY_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(history, f, indent=2)
        _os.replace(tmp, LIQUIDITY_HISTORY_FILE)  # atomic write
    except Exception as e:
        print(f"  [x] Liq history save failed: {e}")

def check_liquidity_shock(cid, current_liq, history):
    """
    Phase 3: Compare current liquidity vs stored snapshot.
    Returns (shock_detected, prev_liq, drop_pct).
    shock_detected=False on first run (no history) or if drop < threshold.
    """
    if cid not in history:
        return False, 0.0, 0.0
    prev = float(history[cid].get("liq", 0))
    if prev <= 0 or current_liq <= 0:
        return False, prev, 0.0
    drop_pct = (prev - current_liq) / prev
    if drop_pct >= LIQUIDITY_SHOCK_PCT:
        return True, prev, drop_pct
    return False, prev, drop_pct


# ── Phase 4: Wallet Intelligence ─────────────────────────────────────────────

def load_wallet_stats():
    """Load persistent wallet reputation database."""
    try:
        with open(WALLET_STATS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_wallet_stats(stats):
    """Atomically persist wallet reputation database."""
    try:
        tmp = WALLET_STATS_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(stats, f, indent=2)
        import os as _os; _os.replace(tmp, WALLET_STATS_FILE)
    except Exception as e:
        print(f"  [x] Wallet stats save failed: {e}")

def load_pending_evals():
    """Load queue of trades awaiting 6h price-movement evaluation."""
    try:
        with open(PENDING_EVALS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_pending_evals(evals):
    """Atomically persist pending evaluation queue."""
    try:
        tmp = PENDING_EVALS_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(evals, f, indent=2)
        import os as _os; _os.replace(tmp, PENDING_EVALS_FILE)
    except Exception as e:
        print(f"  [x] Pending evals save failed: {e}")

def fetch_current_yes_price(cid):
    """Fetch current YES price for a market conditionId (used by eval engine)."""
    try:
        resp = requests.get(f"{GAMMA_API}/markets", params={"conditionIds": cid}, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list) and data:
            prices = data[0].get("outcomePrices", "")
            return float(json.loads(prices)[0]) if prices else None
        elif isinstance(data, dict):
            prices = data.get("outcomePrices", "")
            return float(json.loads(prices)[0]) if prices else None
    except Exception:
        pass
    return None

def process_pending_evals(pending, wallet_stats, now):
    """
    Phase 4: Evaluate trades whose eval_at time has passed.
    Updates wallet_stats in place. Returns remaining (not yet due) evals.
    """
    from datetime import datetime, timezone
    still_pending = []
    evaluated = 0
    for ev in pending:
        try:
            eval_at = datetime.fromisoformat(ev["eval_at"])
            if eval_at.tzinfo is None:
                eval_at = eval_at.replace(tzinfo=timezone.utc)
            if now < eval_at:
                still_pending.append(ev); continue
            # Due for evaluation
            cid          = ev["market_id"]
            wallet       = ev["wallet"]
            entry_price  = float(ev["entry_price"])
            outcome      = ev["outcome"]      # "Yes" or "No"
            current_price = fetch_current_yes_price(cid)
            if current_price is None:
                still_pending.append(ev); continue  # can't fetch price, retry next scan
            move = current_price - entry_price
            if outcome == "No": move = -move   # for NO buys, down is good
            is_win = move >= MIN_PRICE_MOVE
            # Update wallet stats
            ws = wallet_stats.get(wallet, {
                "trades": 0, "wins": 0, "losses": 0, "accuracy": 0.0,
                "total_move": 0.0, "avg_move_after_trade": 0.0,
                "score": 0.0, "tier": "unknown", "last_seen": ev["recorded_at"]
            })
            ws["trades"]     += 1
            ws["wins"]       += 1 if is_win else 0
            ws["losses"]     += 0 if is_win else 1
            ws["total_move"] = ws.get("total_move", 0.0) + abs(move)
            ws["accuracy"]   = ws["wins"] / ws["trades"]
            ws["avg_move_after_trade"] = ws["total_move"] / ws["trades"]
            # Score: accuracy(60%) + avg_move(30%) + sample_weight(10%)
            if ws["trades"] >= MIN_TRADES_SCORING:
                score = (
                    ws["accuracy"] * 0.6 +
                    min(ws["avg_move_after_trade"] / 0.15, 1.0) * 0.3 +
                    min(ws["trades"] / 20, 1.0) * 0.1
                )
                ws["score"] = round(score, 4)
                # Market maker filter
                if ws["trades"] >= MM_MIN_TRADES and ws["accuracy"] < MM_MAX_ACCURACY:
                    ws["tier"] = "market_maker"
                elif score >= ELITE_WALLET_SCORE:
                    ws["tier"] = "elite"
                elif score >= SMART_WALLET_SCORE:
                    ws["tier"] = "smart"
                else:
                    ws["tier"] = "known"
            else:
                ws["tier"] = "unknown"
            ws["last_seen"] = now.isoformat()
            wallet_stats[wallet] = ws
            evaluated += 1
        except Exception as ex:
            still_pending.append(ev)  # keep on error, retry next scan
    if evaluated:
        print(f"[+] Wallet evals: {evaluated} evaluated, {len(still_pending)} pending")
    return still_pending

def get_wallet_info(wallet, wallet_stats):
    """Return wallet intelligence dict for a given address."""
    ws = wallet_stats.get(wallet)
    if not ws or ws.get("trades", 0) < MIN_TRADES_SCORING:
        return {"tier": "unknown", "trades": 0, "accuracy": 0.0, "score": 0.0,
                "avg_move": 0.0, "wallet": wallet}
    return {
        "tier":     ws.get("tier", "unknown"),
        "trades":   ws.get("trades", 0),
        "accuracy": ws.get("accuracy", 0.0),
        "score":    ws.get("score", 0.0),
        "avg_move": ws.get("avg_move_after_trade", 0.0),
        "wallet":   wallet,
    }

def record_wallet_trade(pending, wallet, cid, market_name, entry_price, outcome, now):
    """Queue a trade for 6h price-movement evaluation. Dedup: one eval per wallet+market per scan."""
    if wallet == "unknown": return
    # Skip if already have a recent pending eval for this wallet+market
    for ev in pending:
        if ev["wallet"] == wallet and ev["market_id"] == cid:
            return
    from datetime import timedelta
    eval_at = (now + timedelta(hours=EVAL_DELAY_HOURS)).isoformat()
    pending.append({
        "eval_id":    f"{wallet[:10]}_{cid[:10]}_{int(now.timestamp())}",
        "wallet":     wallet,
        "market_id":  cid,
        "market_name": market_name[:50],
        "entry_price": round(entry_price, 4),
        "outcome":    outcome,
        "eval_at":    eval_at,
        "recorded_at": now.isoformat(),
    })

def boost_signal_tier(base_tier, wallet_tier):
    """
    Apply wallet reputation boost to signal tier.
    Returns: ("EXTREME++", "EXTREME", 1, 2, None)
    None means suppress (market_maker).
    """
    if wallet_tier == "market_maker": return None   # suppress
    if wallet_tier == "elite":
        if base_tier == 0: return 1                  # upgrade dead signal to T1
        return "EXTREME++"
    if wallet_tier == "smart":
        if base_tier == 2: return 1                  # T2 -> T1
        if base_tier == 1: return "EXTREME"          # T1 -> EXTREME
    return base_tier  # unknown/known: no change


def qualify_whale(address):
    if address == "unknown": return False, None, 0
    return True, None, 0

def calculate_signal(wt, yes_price, win_rate, count, days_to_resolve, is_sports=False):
    raw_price   = wt["price"]
    outcome     = wt.get("outcome","Yes")
    whale_prob  = (1.0 - raw_price) if outcome == "No" else raw_price
    market_prob = float(yes_price) if yes_price else 0.5
    divergence  = abs(whale_prob - market_prob)
    t1   = get_divergence_threshold(days_to_resolve, is_sports)
    t2   = t1 * 0.65
    tier = 1 if divergence >= t1 else (2 if divergence >= t2 else 0)
    return {"tier":tier,"divergence":round(divergence,4),"whale_prob":round(whale_prob,4),"market_prob":round(market_prob,4),"threshold_t1":round(t1,4),"threshold_t2":round(t2,4),"win_rate":win_rate,"trade_count":count,"impact_ratio":wt.get("impact_ratio",0),"is_sports":is_sports}

def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[!] Telegram not configured"); print(message); return False
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", json={"chat_id":TELEGRAM_CHAT_ID,"text":message}, timeout=10).raise_for_status()
        print("[+] Telegram sent"); return True
    except Exception as e:
        print(f"[x] Telegram failed: {e}"); return False

def format_signal(market, wt, signal, stage, signal_type="Whale Single Trade", liq_shock_info=None, wallet_info=None):
    wtier = wallet_info.get("tier", "unknown") if wallet_info else "unknown"
    boosted = boost_signal_tier(signal["tier"], wtier) if wtier in ("elite","smart","market_maker") else signal["tier"]
    is_extreme_pp = (boosted == "EXTREME++")
    is_extreme    = is_extreme_pp or (boosted == "EXTREME") or ((liq_shock_info is not None) and (signal_type == "Whale Accumulation") and (signal["tier"] == 1))
    if wtier == "elite":
        emoji = "\u2b50 ELITE WALLET DETECTED"
        label = "EXTREME++ - HIGHEST CONVICTION"
    elif wtier == "smart":
        emoji = "\U0001f50d SMART WALLET DETECTED"
        label = "EXTREME - HIGH CONVICTION" if is_extreme else "TIER 1 - ACT"
    elif is_extreme:
        emoji = "\u26a0\ufe0f PRE-WHALE SETUP DETECTED"
        label = "EXTREME - HIGH CONVICTION"
    elif signal["tier"] == 1:
        emoji = "!! WHALE SIGNAL !!"
        label = "TIER 1 - ACT"
    else:
        emoji = "?? WHALE SIGNAL ??"
        label = "TIER 2 - MONITOR"
    cluster_line = ""
    if signal_type == "Whale Accumulation":
        cluster_line = f"Cluster: {wt.get('trade_count','?')} trades in {wt.get('span_mins','?'):.1f}min\n"
    shock_line = ""
    if liq_shock_info is not None:
        prev_l, drop_p = liq_shock_info
        shock_line = f"Liquidity Change: ${prev_l:,.0f} -> ${wt.get('_current_liq', prev_l*(1-drop_p)):,.0f} (-{drop_p*100:.1f}%)\n"
    wallet_line = ""
    if wallet_info and wallet_info.get("trades", 0) >= MIN_TRADES_SCORING:
        wa = wallet_info["accuracy"]*100
        wt_label = wallet_info["tier"].upper()
        wallet_line = (f"Wallet: {wallet_info['wallet'][:10]}...\n"
                       f"  Tier: {wt_label} | Accuracy: {wa:.0f}% | Trades: {wallet_info['trades']} | Avg Move: {wallet_info['avg_move']*100:.1f}%\n")
    name   = market.get("question","Unknown")[:60]
    days   = market.get("_days_to_resolve","?")
    days_str = "Open Horizon (no end date)" if days == 999 else f"{days} days"
    cat    = market.get("_category","other").upper()
    slabel = STAGE_CONFIG.get(stage,{}).get("label","?")
    sports = " [SPORTS +2% premium]" if signal["is_sports"] else ""
    outcome_note = f" (NO-side buy, adj. YES={signal['whale_prob']:.3f})" if wt.get("outcome") == "No" else ""
    event_line   = f"Event: {market['_parent_event_title'][:55]}\n" if market.get("_parent_event_title") else ""
    return (f"{emoji}  [{cat}] [{signal_type.upper()}]\n\nMarket: {name}\n{event_line}Resolves in: {days_str}\n"
            f"{wallet_line}"
            f"Direction: {wt['direction']} {wt.get('outcome','Yes')}{outcome_note}  Size: ${wt['size_usd']:,.2f}\n"
            f"{shock_line}"
            f"{cluster_line}"
            f"Impact: {wt['impact_ratio']*100:.2f}% of pool\nWhale price: {wt['price']:.3f}\n\n"
            f"Market YES: {signal['market_prob']:.3f} ({signal['market_prob']*100:.1f}%)\n"
            f"Whale implied YES: {signal['whale_prob']:.3f} ({signal['whale_prob']*100:.1f}%)\n"
            f"Divergence: +{signal['divergence']*100:.1f}% (threshold: {signal['threshold_t1']*100:.1f}%{sports})\n\n"
            f"Signal: {label}\nStage: {stage} {slabel}\nReply PAPER YES to enter trade.")

# --- MAIN SCAN ---

def scan_markets(min_size=None, target_market_id=None, json_output=False, skip_resolution_filter=False, force_stage=None):
    global WHALE_MIN_SIZE
    print("\n" + "="*62)
    print(f"WHALE TRACKER v6.3 - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"MinLiq=${MIN_LIQUIDITY:,} | NullDateMinLiq=${NULL_DATE_MIN_LIQ:,} | ImpactRatio={MIN_IMPACT_RATIO} | MaxHorizon={MAX_HORIZON_DAYS}d | Div=dynamic")
    print("="*62)
    if min_size: WHALE_MIN_SIZE = min_size
    signals_found    = []
    stage_used       = 1
    liq_history      = load_liquidity_history()
    liq_history_upd  = {}  # collected this scan, written at end
    now              = datetime.now(timezone.utc)
    wallet_stats     = load_wallet_stats()
    pending_evals    = load_pending_evals()
    # Phase 4: process any evals that are due
    pending_evals    = process_pending_evals(pending_evals, wallet_stats, now)

    if target_market_id:
        markets = [{"conditionId": target_market_id}]; stage_used = 1
        print(f"[i] Single market mode: {target_market_id}")
    else:
        markets_flat = fetch_markets()
        events_flat  = fetch_events()
        all_markets  = merge_market_sources(markets_flat, events_flat)
        liquid_markets = filter_liquid_markets(all_markets)
        if skip_resolution_filter:
            markets = liquid_markets; stage_used = 1
            print("[i] Resolution filter SKIPPED")
        else:
            markets, stage_used = run_stage_expansion(liquid_markets, force_stage)
        cfg = STAGE_CONFIG.get(stage_used, STAGE_CONFIG[1])
        null_count = sum(1 for m in markets if m.get("_null_date"))
        print(f"\n[>] Stage {stage_used} {cfg['label']} | {cfg['min_days']}-{cfg['max_days']}d + {null_count} Open Horizon | WhaleMin: dynamic | Div: V-shape")

    if not target_market_id:
        markets.sort(key=lambda m: CATEGORY_PRIORITY.get(m.get("_category","other"), 99))

    print(f"\n[>] Scanning {len(markets)} markets...\n")
    SKIP_THRESHOLD = 0.05

    for market in markets:
        cid = market.get("conditionId") or market.get("condition_id") or market.get("id","")
        if not cid: continue
        name        = market.get("question", cid[:20])[:40]
        category    = market.get("_category","other")
        is_sports   = (category == "sports")
        liquidity   = float(market.get("liquidityNum") or market.get("liquidity") or 0)
        days_to_res = market.get("_days_to_resolve", 7)
        # Phase 3: shock check + snapshot accumulation
        shock, prev_liq, drop_pct = check_liquidity_shock(cid, liquidity, liq_history)
        liq_history_upd[cid] = {"liq": liquidity, "ts": datetime.now(timezone.utc).isoformat()}
        if shock:
            print(f"  [~] Liq SHOCK [{category.upper()}]: ${prev_liq:,.0f} -> ${liquidity:,.0f} (-{drop_pct*100:.1f}%) {name}")
        trades = get_recent_trades(cid)
        if not trades: continue
        whales   = find_whale_trades(trades, liquidity, days_to_res, is_sports)
        clusters = find_whale_clusters(trades, liquidity, days_to_res, is_sports)
        if not whales and not clusters: continue
        event_ctx = f" [{market.get('_parent_event_title','')[:25]}]" if market.get("_parent_event_title") else ""
        if clusters:
            print(f"[!] {len(clusters)} cluster(s) [{category.upper()}]{event_ctx}: {name}")
        if whales:
            print(f"[!] {len(whales)} whale(s) [{category.upper()}]{event_ctx}: {name}")
        # Process clusters first (higher confidence), then singles
        for wt in (clusters + whales):
            ok, wr, cnt = qualify_whale(wt["wallet"])
            if not ok: continue
            try:
                prices = market.get("outcomePrices","")
                yes_price = float(json.loads(prices)[0]) if prices else 0.5
            except: yes_price = 0.5
            sig = calculate_signal(wt, yes_price, wr, cnt, days_to_res, is_sports)
            if sig["tier"] == 0: continue
            if yes_price < SKIP_THRESHOLD or yes_price > (1 - SKIP_THRESHOLD): continue
            days_label = "Open" if days_to_res == 999 else f"{days_to_res}d"
            stype_short = "ACCUM" if wt.get("signal_type") == "Whale Accumulation" else "SINGLE"
            cluster_info = f" {wt['trade_count']}tx/{wt['span_mins']:.0f}min" if wt.get("signal_type") == "Whale Accumulation" else ""
            wtag = f" [W:{wt['wallet'][:8]}]" if wt.get("wallet","unknown") != "unknown" else ""
            print(f"  [*] TIER {sig['tier']} [{stype_short}] [{category.upper()}] outcome={wt.get('outcome','?')} whale_YES={sig['whale_prob']:.3f} mkt_YES={sig['market_prob']:.3f} div={sig['divergence']*100:.1f}% (need {sig['threshold_t1']*100:.1f}%) ${wt['size_usd']:,.0f} impact={wt['impact_ratio']*100:.2f}% {days_label}{cluster_info}{wtag}")
            if any(s["market_id"]==cid for s in signals_found): continue
            stype = wt.get("signal_type", "Whale Single Trade")
            # Phase 4: wallet intelligence
            winfo = get_wallet_info(wt["wallet"], wallet_stats)
            boosted_tier = boost_signal_tier(sig["tier"], winfo["tier"])
            if boosted_tier is None:  # market_maker suppressed
                print(f"  [--] Market maker suppressed: {wt['wallet'][:10]}")
                continue
            record_wallet_trade(pending_evals, wt["wallet"], cid,
                                market.get("question",""), wt["price"],
                                wt.get("outcome","Yes"), now)
            signals_found.append({"market_id":cid,"market_name":market.get("question","Unknown"),"market_slug":market.get("slug",""),"parent_event":market.get("_parent_event_title",""),"market_category":category,"yes_price":yes_price,"tier":sig["tier"],"boosted_tier":str(boosted_tier),"divergence":sig["divergence"],"threshold_t1":sig["threshold_t1"],"whale_prob":sig["whale_prob"],"market_prob":sig["market_prob"],"direction":wt["direction"],"outcome":wt.get("outcome","Yes"),"size_usd":wt["size_usd"],"impact_ratio":wt["impact_ratio"],"wallet":wt["wallet"],"wallet_tier":winfo["tier"],"end_date_iso":market.get("_end_date_iso",""),"days_to_resolve":days_to_res,"null_date":market.get("_null_date",False),"stage_used":stage_used,"liq_shock":shock,"prev_liq":round(prev_liq,2),"liq_drop_pct":round(drop_pct,4),"signal_type":stype,"scanned_at":now.isoformat()})
            shock_info = (prev_liq, drop_pct) if shock else None
            if shock and stype == "Whale Accumulation" and sig["tier"] == 1:
                print(f"  [!!!] EXTREME signal: liq shock + accumulation + Tier 1")
            if winfo["tier"] in ("elite","smart"):
                print(f"  [W:{winfo['tier'].upper()}] acc={winfo['accuracy']*100:.0f}% trades={winfo['trades']} score={winfo['score']:.2f} -> tier {sig['tier']} boosted to {boosted_tier}")
            if not json_output: send_telegram(format_signal(market, wt, sig, stage_used, stype, shock_info, winfo))

    # Phase 3: persist liquidity snapshots for next scan
    liq_history.update(liq_history_upd)
    save_liquidity_history(liq_history)
    print(f"[+] Liq history: {len(liq_history_upd)} markets snapshotted -> {LIQUIDITY_HISTORY_FILE.split(chr(47))[-1]}")
    # Phase 4: persist wallet intelligence
    save_wallet_stats(wallet_stats)
    save_pending_evals(pending_evals)
    print(f"[+] Wallet DB: {len(wallet_stats)} wallets | Pending evals: {len(pending_evals)}")

    print("\n" + "="*62)
    print(f"SCAN COMPLETE -- Stage {stage_used} -- {len(signals_found)} signal(s)")
    print("="*62)
    if not signals_found:
        print(f"[i] No signals (Stage {stage_used}: {STAGE_CONFIG.get(stage_used,{}).get('label','?')}). Patience is a position.")
    else:
        for s in signals_found:
            null_tag = " [OPEN HORIZON]" if s.get("null_date") else ""
            print(f"  Tier {s['tier']} [{s.get('market_category','?').upper()}]: {s['market_name'][:50]} | div {s['divergence']*100:.1f}% vs {s['threshold_t1']*100:.1f}% | {s['days_to_resolve']}d{null_tag}")
    if json_output:
        out = {"scanned_at":datetime.now(timezone.utc).isoformat(),"signals_count":len(signals_found),"markets_scanned":len(markets),"stage_used":stage_used,"signals":signals_found}
        with open(SIGNALS_OUTPUT,"w") as f: json.dump(out, f, indent=2)
        print(f"\n[+] Written to {SIGNALS_OUTPUT}")
    return signals_found

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Polymarket Whale Signal Detection v6.3")
    parser.add_argument("--min-size",             type=float, default=None)
    parser.add_argument("--market-id",            type=str,   default=None)
    parser.add_argument("--json",                 action="store_true", default=False)
    parser.add_argument("--no-resolution-filter", action="store_true", default=False)
    parser.add_argument("--stage",                type=int, choices=[1,2,3,4], default=None)
    args = parser.parse_args()
    scan_markets(min_size=args.min_size, target_market_id=args.market_id, json_output=args.json, skip_resolution_filter=args.no_resolution_filter, force_stage=args.stage)
    sys.exit(0)
