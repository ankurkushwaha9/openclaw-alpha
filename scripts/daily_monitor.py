#!/usr/bin/env python3
"""
Alpha Bot Daily Monitor v5
Runs at 9am MST (4pm UTC) via cron daily.
Sends TWO reports to Telegram:
  1. Real Money — wallet + Oscar positions + alerts
  2. Paper Money — virtual portfolio + open positions + category exposure + scorecard progress

v5 fixes:
  - Oscar positions: query Gamma API directly (polyclaw position IDs don't persist)
  - Wallet: use set -a export trick so private key loads correctly
  - Telegram creds: hardcoded /home/ubuntu path (SSM runs as root, ~ resolves wrong)
"""

import subprocess, requests, json, os, re
from datetime import datetime, timezone

POLYCLAW_DIR = "/home/ubuntu/.openclaw/workspace/skills/polyclaw"
VENV_PYTHON  = "/home/ubuntu/.openclaw/workspace/skills/polyclaw/.venv/bin/python"
ENV_FILE     = "/home/ubuntu/.openclaw/workspace/.env"
LEDGER_FILE      = "/home/ubuntu/.openclaw/workspace/paper_trading/ledger.json"
POSITIONS_FILE   = "/home/ubuntu/.openclaw/polyclaw/positions.json"
BOT_CONFIG   = "/home/ubuntu/.openclaw/openclaw.json"  # hardcoded — SSM runs as root
GAMMA_API    = "https://gamma-api.polymarket.com"

# market_id -> (label, entry_price, invested)
OSCAR_POSITIONS = {
    "613835": ("Best Picture (OBAA)",      0.745, 10.0),
    "614008": ("Best Actor (Chalamet)",     0.790,  8.0),
    "614355": ("Best Supporting (Teyana)", 0.700,  7.0),
}

ALERT_THRESHOLD = 0.15


# ─── ENV ──────────────────────────────────────────────────────────────────────

def load_env():
    if not os.path.exists(ENV_FILE):
        return
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


# ─── POLYCLAW (wallet only) ───────────────────────────────────────────────────

def run_polyclaw(cmd):
    """Use set -a so .env exports properly into subprocess."""
    try:
        full_cmd = (
            f"set -a && source {ENV_FILE} && set +a && "
            f"cd {POLYCLAW_DIR} && {VENV_PYTHON} scripts/polyclaw.py {cmd}"
        )
        result = subprocess.run(
            full_cmd, shell=True, executable="/bin/bash",
            capture_output=True, text=True, timeout=45
        )
        return result.stdout.strip()
    except Exception as e:
        return f"ERROR: {e}"


def parse_wallet(raw):
    usdc, pol = "??", "??"
    try:
        data     = json.loads(raw)
        balances = data.get("balances", {})
        usdc     = str(balances.get("USDC.e", "??")).strip('"')
        pol      = str(balances.get("POL",    "??")).strip('"')
        try: usdc = f"{float(usdc):.2f}"
        except: pass
        try: pol  = f"{float(pol):.4f}"
        except: pass
    except Exception:
        for line in raw.split("\n"):
            m = re.search(r'USDC[^:]*[:\s]+(["\']?)([\d.]+)\1', line)
            if m: usdc = m.group(2)
            m = re.search(r'"POL"[^:]*[:\s]+(["\']?)([\d.]+)\1', line)
            if m: pol = m.group(2)
    return usdc, pol


# ─── TELEGRAM ─────────────────────────────────────────────────────────────────

def get_telegram_creds():
    try:
        with open(BOT_CONFIG) as f:
            cfg = json.load(f)
        token   = cfg.get("channels", {}).get("telegram", {}).get("botToken", "")
        chat_id = cfg.get("channels", {}).get("telegram", {}).get("allowFrom", [""])[0]
        return token, chat_id
    except Exception as e:
        print(f"Creds error: {e}")
        return "", ""


def send_telegram(msg):
    token, chat_id = get_telegram_creds()
    if not token or not chat_id:
        print("TELEGRAM CREDS NOT FOUND\n" + msg)
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg},
            timeout=15
        )
        return r.status_code == 200
    except Exception as e:
        print(f"Telegram error: {e}")
        return False


# ─── GAMMA API ────────────────────────────────────────────────────────────────

def get_gamma_yes_price(market_id):
    """Get current YES price directly from Gamma API."""
    try:
        r = requests.get(f"{GAMMA_API}/markets/{market_id}", timeout=10)
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
                if outcome.strip().upper() == "YES":
                    return float(prices[i])
            return float(prices[0])
    except Exception as e:
        print(f"  Gamma API error for {market_id}: {e}")
    return None


# ─── REAL MONEY ───────────────────────────────────────────────────────────────

def parse_oscar_positions():
    lines       = []
    alerts      = []
    total_value = 0.0

    for market_id, (label, entry, invested) in OSCAR_POSITIONS.items():
        price = get_gamma_yes_price(market_id)

        if price is None:
            lines.append(f"- {label}: price unavailable")
            continue

        # Estimate shares from invested / entry
        shares       = invested / entry
        current_val  = shares * price
        pnl          = current_val - invested
        pnl_str      = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
        price_pct    = int(price * 100)
        entry_pct    = int(entry * 100)
        arrow        = "UP" if price >= entry else "DN"
        chg_pct      = ((price - entry) / entry * 100)
        chg_str      = f"+{chg_pct:.1f}%" if chg_pct >= 0 else f"{chg_pct:.1f}%"

        total_value += current_val

        lines.append(
            f"- {label}\n"
            f"  Entry: {entry_pct}c | Now: {price_pct}c [{arrow} {chg_str}] | P&L: {pnl_str}"
        )

        drop = (entry - price) / entry
        if drop > ALERT_THRESHOLD:
            alerts.append(
                f"ALERT {label}: {entry_pct}c -> {price_pct}c "
                f"(down {drop:.0%}) - check via MetaMask"
            )

    return ("\n".join(lines) if lines else "- No position data",
            "\n".join(alerts) if alerts else "All positions stable",
            total_value)


def build_real_report():
    wallet_raw           = run_polyclaw("wallet status")
    usdc, pol            = parse_wallet(wallet_raw)
    pos_text, alerts, total = parse_oscar_positions()

    invested  = sum(inv for _, (_, _, inv) in OSCAR_POSITIONS.items())
    pnl_total = total - invested
    pnl_str   = f"+${pnl_total:.2f}" if pnl_total >= 0 else f"-${abs(pnl_total):.2f}"

    return (
        f"REAL MONEY REPORT\n"
        f"{datetime.now().strftime('%b %d %Y - %I:%M %p MST')}\n"
        f"\n"
        f"WALLET\n"
        f"- USDC: ${usdc}\n"
        f"- POL: {pol}\n"
        f"\n"
        f"OSCAR POSITIONS (resolve March 15)\n"
        f"{pos_text}\n"
        f"\n"
        f"- Invested: ${invested:.2f} | Now: ${total:.2f} | P&L: {pnl_str}\n"
        f"\n"
        f"ALERTS\n"
        f"{alerts}\n"
        f"\n"
        f"Oscars resolve: March 15, 2026"
    )


# ─── PAPER MONEY ──────────────────────────────────────────────────────────────

def build_paper_report():
    if not os.path.exists(LEDGER_FILE):
        return "PAPER MONEY REPORT\n- Ledger not found"

    with open(LEDGER_FILE) as f:
        ledger = json.load(f)

    meta     = ledger.get("meta", {})
    cash     = float(meta.get("virtual_balance", 66.0))
    starting = float(meta.get("starting_balance", 66.0))
    open_pos = ledger.get("open_positions", [])
    resolved = ledger.get("resolved_positions", [])
    stats    = ledger.get("stats", {})

    open_value   = 0.0
    pos_lines    = []
    cat_invested = {}

    for pos in open_pos:
        live        = get_gamma_yes_price(pos["market_id"])
        shares      = float(pos.get("shares", 0))
        entry_price = float(pos.get("entry_price", 0))
        invested    = float(pos.get("virtual_amount", 0))
        category    = pos.get("category", "other")

        if live is not None:
            market_val = shares * live
            unrealized = market_val - invested
            pnl_str    = f"+${unrealized:.2f}" if unrealized >= 0 else f"-${abs(unrealized):.2f}"
            chg_pct    = ((live - entry_price) / entry_price * 100) if entry_price > 0 else 0
            chg_str    = f"+{chg_pct:.1f}%" if chg_pct >= 0 else f"{chg_pct:.1f}%"
            open_value += market_val
        else:
            market_val = invested
            pnl_str    = "price unavailable"
            chg_str    = "??"
            open_value += invested

        cat_invested[category] = cat_invested.get(category, 0.0) + invested

        pos_lines.append(
            f"- {pos.get('market_name','?')[:40]}\n"
            f"  {pos['side']} | Entry: {int(entry_price*100)}c | "
            f"Live: {int((live or entry_price)*100)}c [{chg_str}] | P&L: {pnl_str}"
        )

    total_portfolio = cash + open_value
    growth          = total_portfolio - starting
    growth_str      = f"+${growth:.2f}" if growth >= 0 else f"-${abs(growth):.2f}"
    growth_pct      = (growth / starting * 100) if starting > 0 else 0
    growth_pct_str  = f"+{growth_pct:.1f}%" if growth_pct >= 0 else f"{growth_pct:.1f}%"

    wins       = stats.get("wins", 0)
    losses     = stats.get("losses", 0)
    win_rate   = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
    total_pnl  = float(stats.get("total_pnl", 0))
    pnl_str    = f"+${total_pnl:.2f}" if total_pnl >= 0 else f"-${abs(total_pnl):.2f}"

    resolved_count = len(resolved)
    sc_trades  = f"{'PASS' if resolved_count >= 10 else 'FAIL'} Trades: {resolved_count}/10"
    sc_wr      = f"{'PASS' if win_rate >= 60 else 'FAIL'} Win rate: {win_rate:.0f}% (need 60%)"

    cat_lines = []
    for cat, amt in sorted(cat_invested.items()):
        pct  = (amt / total_portfolio * 100) if total_portfolio > 0 else 0
        flag = " NEAR CAP" if pct >= 35 else ""
        cat_lines.append(f"- {cat.title()}: ${amt:.2f} ({pct:.0f}%){flag}")

    pos_section = "\n".join(pos_lines) if pos_lines else "- No open positions yet"
    cat_section = "\n".join(cat_lines) if cat_lines else "- No positions yet"

    return (
        f"PAPER MONEY REPORT\n"
        f"{datetime.now().strftime('%b %d %Y - %I:%M %p MST')}\n"
        f"\n"
        f"PORTFOLIO\n"
        f"- Cash: ${cash:.2f} | Positions: ${open_value:.2f}\n"
        f"- Total: ${total_portfolio:.2f} | Growth: {growth_str} ({growth_pct_str})\n"
        f"\n"
        f"OPEN POSITIONS\n"
        f"{pos_section}\n"
        f"\n"
        f"CATEGORY EXPOSURE\n"
        f"{cat_section}\n"
        f"\n"
        f"PERFORMANCE ({resolved_count} resolved | {wins}W {losses}L | {win_rate:.0f}% WR)\n"
        f"- Realized P&L: {pnl_str}\n"
        f"\n"
        f"GO-LIVE SCORECARD\n"
        f"- {sc_trades}\n"
        f"- {sc_wr}\n"
        f"\n"
        f"Full report every Sunday 9am MST"
    )




# --- FIX-4: RESOLUTION CHECKER (added Mar 1 2026) ----------------------------

def get_market_status(market_id):
    """Check if a Gamma market is resolved. Returns (is_resolved, winner, yes_price)."""
    try:
        r = requests.get(f"{GAMMA_API}/markets/{market_id}", timeout=10)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            data = data[0] if data else {}

        closed      = data.get("closed", False)
        active      = data.get("active", True)
        is_resolved = closed or not active

        winner = None
        if is_resolved:
            outcomes_raw = data.get("outcomes", [])
            prices_raw   = data.get("outcomePrices", [])
            outcomes = json.loads(outcomes_raw) if isinstance(outcomes_raw, str) else outcomes_raw
            prices   = json.loads(prices_raw)   if isinstance(prices_raw, str)   else prices_raw
            if outcomes and prices:
                prices_float = [float(p) for p in prices]
                max_idx      = prices_float.index(max(prices_float))
                winner       = outcomes[max_idx].strip().upper()

        yes_price = None
        try:
            prices_raw   = data.get("outcomePrices", [])
            outcomes_raw = data.get("outcomes", [])
            prices   = json.loads(prices_raw)   if isinstance(prices_raw, str)   else prices_raw
            outcomes = json.loads(outcomes_raw) if isinstance(outcomes_raw, str) else outcomes_raw
            for i, o in enumerate(outcomes):
                if o.strip().upper() == "YES":
                    yes_price = float(prices[i])
        except Exception:
            pass

        return is_resolved, winner, yes_price

    except Exception as e:
        print(f"  Resolution check error for {market_id}: {e}")
        return False, None, None


def check_resolutions():
    """
    FIX-4: Check if any open real-money positions have resolved.
    Reads positions.json, queries Gamma API live (not cached),
    sends Telegram alert if resolved. Updates positions.json with result.
    """
    if not os.path.exists(POSITIONS_FILE):
        print("check_resolutions: positions.json not found, skipping.")
        return

    with open(POSITIONS_FILE, "r", encoding="utf-8") as f:
        positions = json.load(f)

    open_positions = [p for p in positions if p.get("status") == "open"]

    if not open_positions:
        print("check_resolutions: no open positions to check.")
        return

    print(f"check_resolutions: checking {len(open_positions)} open position(s)...")

    alerts      = []
    any_updated = False

    for pos in open_positions:
        market_id   = pos.get("market_id")
        question    = pos.get("question", "Unknown market")
        side        = pos.get("position", "YES")
        entry_amt   = float(pos.get("entry_amount", 0))
        entry_price = float(pos.get("entry_price", 0))
        shares      = entry_amt / entry_price if entry_price > 0 else 0

        print(f"  Checking: {question[:50]}...")
        is_resolved, winner, yes_price = get_market_status(market_id)

        if not is_resolved:
            price_str = f"{int(yes_price*100)}c" if yes_price else "??"
            print(f"    Still open. Current YES: {price_str}")
            continue

        # Resolved - calculate result
        won        = (winner == side)
        payout     = round(shares * 1.0, 2) if won else 0.0
        profit     = round(payout - entry_amt, 2)
        result     = "WIN" if won else "LOSS"
        profit_str = f"+${profit:.2f}" if profit >= 0 else f"-${abs(profit):.2f}"

        alert = (
            f"[RESOLUTION ALERT]\n"
            f"Market: {question[:60]}\n"
            f"Your bet: {side} | Winner: {winner}\n"
            f"Result: {result}\n"
            f"Invested: ${entry_amt:.2f} | Payout: ${payout:.2f} | P&L: {profit_str}\n"
            f"Action needed: confirm in polyclaw + update ledger.json"
        )
        alerts.append(alert)
        print(f"    RESOLVED: {result} | {profit_str}")

        # Update positions.json
        for p in positions:
            if p.get("position_id") == pos.get("position_id"):
                p["status"]      = "resolved_win" if won else "resolved_loss"
                p["exit_price"]  = 1.0 if won else 0.0
                p["payout"]      = payout
                p["profit"]      = profit
                p["resolved_at"] = datetime.now(timezone.utc).isoformat()
                any_updated      = True

    if any_updated:
        with open(POSITIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(positions, f, indent=2)
        print("  positions.json updated.")

    if alerts:
        for alert in alerts:
            send_telegram(alert)
        print(f"  {len(alerts)} resolution alert(s) sent via Telegram.")
    else:
        print("  No new resolutions detected.")

def main():
    load_env()

    print("Building real money report...")
    real_report = build_real_report()
    print(real_report)
    ok1 = send_telegram(real_report)
    print("Real report: sent." if ok1 else "Real report: FAILED to send.")

    print("\nChecking for resolutions (Fix-4)...")
    check_resolutions()

    print("\nBuilding paper money report...")
    paper_report = build_paper_report()
    print(paper_report)
    ok2 = send_telegram(paper_report)
    print("Paper report: sent." if ok2 else "Paper report: FAILED to send.")


if __name__ == "__main__":
    main()
