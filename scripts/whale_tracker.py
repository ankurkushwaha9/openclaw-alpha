#!/usr/bin/env python3
"""
whale_tracker.py - Polymarket Whale Signal Detection
Last Updated: 2026-03-07 (v5.2 - BUG-015: outcome direction fix)

Changes v5.1 -> v5.2:
  BUG-015 FIX: Whale price now direction-adjusted.
    If whale buys NO at 0.81, implied YES prob = 1 - 0.81 = 0.19 (not 0.81).
    Eliminates spurious signals from NO-side whale buys.

Changes v5.0 -> v5.1:
  4-STAGE SYSTEM: Tactical(1-7d) / Strategic(8-21d) / Macro(22-45d) / Extreme(46-75d)
  DYNAMIC DIVERGENCE (ChatGPT V-shape): 8% / 6% / 9% / 11% by days_to_resolve
  LIQUIDITY MANIPULATION GUARDRAIL (Gemini): skip if trade > 50% of pool
  WHALE_MIN SCALES WITH HORIZON: $400 / $1500 / $3500 / $7000
  HARD CEILING: 75 days (>90d = macro noise per all 3 LLMs)
  PHASE 2 TODO: clustering, alpha scoring, wallet watchlist
"""
import os, sys, json, requests, argparse
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

GAMMA_API = "https://gamma-api.polymarket.com"
DATA_API  = "https://data-api.polymarket.com"

WHALE_MIN_SIZE    = 400
MIN_WIN_RATE      = 0.60
MIN_TRADE_HISTORY = 10
MIN_LIQUIDITY     = 10000
MIN_IMPACT_RATIO  = 0.003
SPORTS_DIV_PREMIUM = 0.02
SPORTS_WHALE_MIN   = 300
MAX_HORIZON_DAYS   = 75
STAGE2_TRIGGER = 5
STAGE3_TRIGGER = 1
STAGE4_TRIGGER = 3

STAGE_CONFIG = {
    1: {"min_days": 1,  "max_days": 7,  "whale_min": 400,  "label": "TACTICAL"},
    2: {"min_days": 8,  "max_days": 21, "whale_min": 1500, "label": "STRATEGIC"},
    3: {"min_days": 22, "max_days": 45, "whale_min": 3500, "label": "MACRO"},
    4: {"min_days": 46, "max_days": 75, "whale_min": 7000, "label": "EXTREME"},
}

TOTAL_MARKETS_TARGET = 500
PAGE_SIZE            = 100
TELEGRAM_BOT_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID     = os.getenv("TELEGRAM_CHAT_ID")
SIGNALS_OUTPUT       = os.path.join(os.path.dirname(__file__), "whale_signals.json")

def get_divergence_threshold(days, is_sports=False):
    if days <= 7:   base = 0.08
    elif days <= 21: base = 0.06
    elif days <= 45: base = 0.09
    else:            base = 0.11
    return base + (SPORTS_DIV_PREMIUM if is_sports else 0)

def get_whale_min_for_days(days, is_sports=False):
    if is_sports: return SPORTS_WHALE_MIN
    if days <= 14:  return 400
    elif days <= 30: return 1500
    elif days <= 60: return 3500
    else:            return 7000

CATEGORY_KEYWORDS = {
    "geopolitics": ["war","iran","russia","ukraine","israel","gaza","nato","sanction","nuclear","ceasefire","conflict","military","attack","strike","invasion","troops","missile"],
    "economics":   ["fed","interest rate","inflation","gdp","recession","unemployment","tariff","trade","debt","deficit","treasury","cpi","pce","shutdown","budget","federal reserve"],
    "entertainment":["oscar","academy award","grammy","emmy","golden globe","box office","film","movie","album","award"],
    "sports":      ["nba","nfl","nhl","mlb","tennis","soccer","football","basketball","baseball","hockey","mls","ufc","f1","formula","match","game","series","championship","playoff","tournament","wimbledon","bnp","open","cup","league","warriors","lakers","celtics"],
    "crypto":      ["bitcoin","btc","ethereum","eth","crypto","coin","token","blockchain","defi","solana","base"],
    "politics":    ["election","president","congress","senate","vote","poll","democrat","republican","trump","biden","harris"],
}
CATEGORY_PRIORITY = {"geopolitics":1,"economics":2,"entertainment":3,"sports":4,"politics":5,"crypto":6,"other":7}

def detect_category(q):
    q = q.lower()
    for cat, kws in CATEGORY_KEYWORDS.items():
        if any(kw in q for kw in kws): return cat
    return "other"

def get_active_markets(total=TOTAL_MARKETS_TARGET, page_size=PAGE_SIZE):
    markets, offset, page = [], 0, 1
    while len(markets) < total:
        try:
            resp  = requests.get(f"{GAMMA_API}/markets", params={"active":"true","closed":"false","limit":page_size,"offset":offset}, timeout=10)
            resp.raise_for_status()
            data  = resp.json()
            batch = data if isinstance(data, list) else data.get("data", [])
            if not batch: print(f"[+] Pagination stopped at page {page}"); break
            markets.extend(batch)
            print(f"[+] Page {page}: {len(batch)} markets (total: {len(markets)})")
            if len(batch) < page_size: break
            offset += page_size; page += 1
        except Exception as e:
            print(f"[x] Page {page} failed: {e}"); break
    print(f"[+] Total fetched: {len(markets)} markets")
    return markets[:total]

def filter_liquid_markets(markets):
    liquid = []
    for m in markets:
        try:
            if float(m.get("liquidity",0) or 0) >= MIN_LIQUIDITY:
                m["_category"] = detect_category(m.get("question",""))
                liquid.append(m)
        except: continue
    print(f"[+] {len(liquid)} markets with >${MIN_LIQUIDITY:,} liquidity")
    return liquid

def filter_by_resolution(markets, min_days, max_days):
    filtered, now = [], datetime.now(timezone.utc)
    sp, sf, sn = 0, 0, 0
    for m in markets:
        end_str = m.get("endDateIso") or m.get("end_date_iso") or m.get("endDate") or m.get("end_date") or ""
        if not end_str: sn += 1; continue
        try:
            end_dt = datetime.fromisoformat(end_str.replace("Z","+00:00"))
            if end_dt.tzinfo is None: end_dt = end_dt.replace(tzinfo=timezone.utc)
            d = (end_dt - now).days
            if d < min_days: sp += 1; continue
            if d > max_days: sf += 1; continue
            m["_days_to_resolve"] = d; m["_end_date_iso"] = end_str
            filtered.append(m)
        except: sn += 1
    print(f"[+] Resolution ({min_days}-{max_days}d): {len(filtered)} pass (skip: {sp} expired, {sf} too far, {sn} no date)")
    return filtered

def run_stage_expansion(liquid_markets, force_stage=None):
    if force_stage is not None:
        cfg = STAGE_CONFIG[force_stage]
        print(f"[i] Stage {force_stage} ({cfg['label']}) FORCED")
        return filter_by_resolution(liquid_markets, cfg["min_days"], cfg["max_days"]), force_stage
    for sn in [1,2,3,4]:
        cfg = STAGE_CONFIG[sn]
        mkts = filter_by_resolution(liquid_markets, cfg["min_days"], cfg["max_days"])
        trigger = {1:STAGE2_TRIGGER,2:STAGE3_TRIGGER,3:STAGE4_TRIGGER,4:0}[sn]
        if len(mkts) >= trigger or sn == 4:
            print(f"[+] Stage {sn} {cfg['label']}: {len(mkts)} markets")
            return mkts, sn
        print(f"[!] Stage {sn}: only {len(mkts)} (< {trigger}) -- escalating")
    return [], 4

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
            liq = max(market_liquidity, 1)
            impact = usd / liq
            if impact < MIN_IMPACT_RATIO: continue
            if usd > liq * 0.5:
                print(f"  [!] Manipulation guard: ${usd:,.0f} trade vs ${liq:,.0f} liq ({impact*100:.1f}%) -- skip")
                continue
            # BUG-015 FIX: store outcome so calculate_signal can direction-adjust the price
            outcome = trade.get("outcome", "Yes")
            whales.append({"wallet":trade.get("proxyWallet","unknown"),"direction":trade.get("side","BUY").upper(),"size_usd":round(usd,2),"price":round(float(trade.get("price",0.5)),4),"outcome":outcome,"impact_ratio":round(impact,5)})
        except: continue
    return whales

def qualify_whale(address):
    if address == "unknown": return False, None, 0
    return True, None, 0

def calculate_signal(wt, yes_price, win_rate, count, days_to_resolve, is_sports=False):
    # BUG-015 FIX: if whale bought NO at price P, their implied YES prob = 1 - P
    raw_price  = wt["price"]
    outcome    = wt.get("outcome", "Yes")
    whale_prob = (1.0 - raw_price) if outcome == "No" else raw_price
    market_prob = float(yes_price) if yes_price else 0.5
    divergence  = abs(whale_prob - market_prob)
    t1 = get_divergence_threshold(days_to_resolve, is_sports)
    t2 = t1 * 0.65
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

def format_signal(market, wt, signal, stage):
    emoji  = "!! WHALE SIGNAL !!" if signal["tier"]==1 else "?? WHALE SIGNAL ??"
    label  = "TIER 1 - ACT" if signal["tier"]==1 else "TIER 2 - MONITOR"
    name   = market.get("question","Unknown")[:60]
    days   = market.get("_days_to_resolve","?")
    cat    = market.get("_category","other").upper()
    slabel = STAGE_CONFIG.get(stage,{}).get("label","?")
    sports = " [SPORTS +2% premium]" if signal["is_sports"] else ""
    outcome_note = f" (NO-side buy, adj. YES={signal['whale_prob']:.3f})" if wt.get("outcome") == "No" else ""
    return (f"{emoji}  [{cat}]\n\nMarket: {name}\nResolves in: {days} days\n"
            f"Direction: {wt['direction']} {wt.get('outcome','Yes')}{outcome_note}  Size: ${wt['size_usd']:,.2f}\n"
            f"Impact: {wt['impact_ratio']*100:.2f}% of pool\nWhale price: {wt['price']:.3f}\n\n"
            f"Market YES: {signal['market_prob']:.3f} ({signal['market_prob']*100:.1f}%)\n"
            f"Whale implied YES: {signal['whale_prob']:.3f} ({signal['whale_prob']*100:.1f}%)\n"
            f"Divergence: +{signal['divergence']*100:.1f}% (threshold: {signal['threshold_t1']*100:.1f}%{sports})\n\n"
            f"Signal: {label}\nStage: {stage} {slabel}\nReply PAPER YES to enter trade.")

def scan_markets(min_size=None, target_market_id=None, json_output=False, skip_resolution_filter=False, force_stage=None):
    global WHALE_MIN_SIZE
    print("\n" + "="*62)
    print(f"WHALE TRACKER v5.2 - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"MinLiq=${MIN_LIQUIDITY:,} | ImpactRatio={MIN_IMPACT_RATIO} | MaxHorizon={MAX_HORIZON_DAYS}d | Div=dynamic")
    print("="*62)
    if min_size: WHALE_MIN_SIZE = min_size
    signals_found = []; stage_used = 1

    if target_market_id:
        markets = [{"conditionId": target_market_id}]; stage_used = 1
        print(f"[i] Single market mode: {target_market_id}")
    else:
        all_markets    = get_active_markets()
        liquid_markets = filter_liquid_markets(all_markets)
        if skip_resolution_filter:
            markets = liquid_markets; stage_used = 1
            print("[i] Resolution filter SKIPPED")
        else:
            markets, stage_used = run_stage_expansion(liquid_markets, force_stage)
        cfg = STAGE_CONFIG.get(stage_used, STAGE_CONFIG[1])
        print(f"\n[>] Stage {stage_used} {cfg['label']} | {cfg['min_days']}-{cfg['max_days']}d | WhaleMin: dynamic | Div: V-shape")

    if not target_market_id:
        markets.sort(key=lambda m: CATEGORY_PRIORITY.get(m.get("_category","other"), 99))

    print(f"\n[>] Scanning {len(markets)} markets...\n")
    SKIP_THRESHOLD = 0.05

    for market in markets:
        cid = market.get("conditionId") or market.get("condition_id") or market.get("id","")
        if not cid: continue
        name       = market.get("question", cid[:20])[:40]
        category   = market.get("_category","other")
        is_sports  = (category == "sports")
        liquidity  = float(market.get("liquidity",0) or 0)
        days_to_res = market.get("_days_to_resolve", 7)
        trades = get_recent_trades(cid)
        if not trades: continue
        whales = find_whale_trades(trades, liquidity, days_to_res, is_sports)
        if not whales: continue
        print(f"[!] {len(whales)} whale(s) [{category.upper()}]: {name}")
        for wt in whales:
            ok, wr, cnt = qualify_whale(wt["wallet"])
            if not ok: continue
            try:
                prices = market.get("outcomePrices","")
                yes_price = float(json.loads(prices)[0]) if prices else 0.5
            except: yes_price = 0.5
            sig = calculate_signal(wt, yes_price, wr, cnt, days_to_res, is_sports)
            if sig["tier"] == 0: continue
            if yes_price < SKIP_THRESHOLD or yes_price > (1 - SKIP_THRESHOLD): continue
            print(f"  [*] TIER {sig['tier']} [{category.upper()}] outcome={wt.get('outcome','?')} whale_YES={sig['whale_prob']:.3f} mkt_YES={sig['market_prob']:.3f} div={sig['divergence']*100:.1f}% (need {sig['threshold_t1']*100:.1f}%) ${wt['size_usd']:,.0f} impact={wt['impact_ratio']*100:.2f}% {days_to_res}d")
            if any(s["market_id"]==cid for s in signals_found): continue
            signals_found.append({"market_id":cid,"market_name":market.get("question","Unknown"),"market_slug":market.get("slug",""),"market_category":category,"yes_price":yes_price,"tier":sig["tier"],"divergence":sig["divergence"],"threshold_t1":sig["threshold_t1"],"whale_prob":sig["whale_prob"],"market_prob":sig["market_prob"],"direction":wt["direction"],"outcome":wt.get("outcome","Yes"),"size_usd":wt["size_usd"],"impact_ratio":wt["impact_ratio"],"wallet":wt["wallet"],"end_date_iso":market.get("_end_date_iso",""),"days_to_resolve":days_to_res,"stage_used":stage_used,"scanned_at":datetime.now(timezone.utc).isoformat()})
            if not json_output: send_telegram(format_signal(market, wt, sig, stage_used))

    print("\n" + "="*62)
    print(f"SCAN COMPLETE -- Stage {stage_used} -- {len(signals_found)} signal(s)")
    print("="*62)
    if not signals_found:
        print(f"[i] No signals (Stage {stage_used}: {STAGE_CONFIG.get(stage_used,{}).get('label','?')}). Patience is a position.")
    else:
        for s in signals_found:
            print(f"  Tier {s['tier']} [{s.get('market_category','?').upper()}]: {s['market_name'][:50]} | div {s['divergence']*100:.1f}% vs {s['threshold_t1']*100:.1f}% | {s['days_to_resolve']}d")
    if json_output:
        out = {"scanned_at":datetime.now(timezone.utc).isoformat(),"signals_count":len(signals_found),"markets_scanned":len(markets),"stage_used":stage_used,"signals":signals_found}
        with open(SIGNALS_OUTPUT,"w") as f: json.dump(out, f, indent=2)
        print(f"\n[+] Written to {SIGNALS_OUTPUT}")
    return signals_found

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Polymarket Whale Signal Detection v5.2")
    parser.add_argument("--min-size",  type=float, default=None)
    parser.add_argument("--market-id", type=str,   default=None)
    parser.add_argument("--json",      action="store_true", default=False)
    parser.add_argument("--no-resolution-filter", action="store_true", default=False)
    parser.add_argument("--stage",     type=int, choices=[1,2,3,4], default=None)
    args = parser.parse_args()
    scan_markets(min_size=args.min_size, target_market_id=args.market_id, json_output=args.json, skip_resolution_filter=args.no_resolution_filter, force_stage=args.stage)
    sys.exit(0)
