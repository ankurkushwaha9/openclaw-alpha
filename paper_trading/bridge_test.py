#!/usr/bin/env python3
"""
bridge_test.py - Mission 8: End-to-End Pipeline Test
Location: ~/.openclaw/workspace/paper_trading/bridge_test.py
Purpose:  Inject a synthetic Tier 1 whale signal on a real live market,
          run the full bridge pipeline, and send a REAL Telegram proposal
          marked [TEST DO NOT FUND] so the operator knows it's a drill.

What this tests:
  1. whale_signals.json injection (synthetic signal)
  2. paper_signal_bridge.py reads it and runs all 4 guards
  3. Real Telegram proposal delivered to Ankur's phone
  4. Operator runs: BOT_ENV=e2e_test python paper_engine.py buy ...
  5. test_ledger.json updated (production ledger.json untouched)
  6. Full chain confirmed

Run:
  cd /home/ubuntu/.openclaw/workspace
  source skills/polyclaw/.venv/bin/activate
  python paper_trading/bridge_test.py

After Telegram arrives:
  BOT_ENV=e2e_test python paper_trading/paper_engine.py buy <args from proposal>
"""

import json
import sys
import os
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

WORKSPACE    = Path("/home/ubuntu/.openclaw/workspace")
SIGNALS_FILE = WORKSPACE / "scripts" / "whale_signals.json"
SIGNALS_BAK  = WORKSPACE / "scripts" / "whale_signals.json.bak"

# --- Target market: US tariff revenue (Finance, resolves ~Feb 27) -------------
# This market had 13 whale trades confirmed during Mission 7 scan
# We pick this one: "Will the U.S. collect between $500b and $1t in revenue in 2025?"
# Market ID will be fetched live from Gamma API by question keyword match

GAMMA_API    = "https://gamma-api.polymarket.com"
TARGET_KEYWORD = "collect between $500b and $1t"  # unique enough to match one market


def find_target_market():
    """Find the tariff market by keyword in question text."""
    print("[*] Searching Gamma API for target market...")
    try:
        r = requests.get(
            f"{GAMMA_API}/markets",
            params={"active": "true", "closed": "false", "limit": 100},
            timeout=10
        )
        r.raise_for_status()
        markets = r.json()
        for m in markets:
            q = m.get("question", "")
            if TARGET_KEYWORD.lower() in q.lower():
                prices_raw = m.get("outcomePrices", "[0.5,0.5]")
                try:
                    yes_price = float(json.loads(prices_raw)[0])
                except Exception:
                    yes_price = 0.50
                print(f"[+] Found: {q[:65]}")
                print(f"    Market ID: {m.get('conditionId','')[:25]}...")
                print(f"    YES price: {yes_price:.3f}")
                return m, yes_price
    except Exception as e:
        print(f"[x] Gamma API error: {e}")
    return None, 0.50


def inject_synthetic_signal(market, yes_price):
    """
    Write a fake but realistic Tier 1 signal into whale_signals.json.
    Divergence: 16% (comfortably Tier 1 > 15%)
    Whale implied prob: yes_price + 0.16 (whale thinks it's higher)
    """
    now      = datetime.now(timezone.utc)
    end_date = (now + timedelta(days=3)).strftime("%Y-%m-%d")

    whale_prob  = min(0.95, yes_price + 0.16)
    divergence  = round(whale_prob - yes_price, 4)
    market_id   = market.get("conditionId", "test_market_001")
    market_name = market.get("question", "Synthetic Test Market")

    synthetic_signal = {
        "market_id":      market_id,
        "market_name":    f"[TEST] {market_name}",
        "market_slug":    market.get("slug", "test-market"),
        "yes_price":      yes_price,
        "tier":           1,
        "divergence":     divergence,
        "whale_prob":     round(whale_prob, 4),
        "market_prob":    round(yes_price, 4),
        "direction":      "BUY",
        "size_usd":       1500.00,   # realistic whale size
        "wallet":         "0xSYNTHETIC_TEST_WALLET",
        "end_date_iso":   end_date,
        "days_to_resolve": 3,
        "scanned_at":     now.isoformat(),
        "synthetic":      True,      # safety flag — never used in scoring
    }

    output = {
        "scanned_at":      now.isoformat(),
        "signals_count":   1,
        "markets_scanned": 1,
        "synthetic_test":  True,
        "signals":         [synthetic_signal],
    }

    # Backup real signals file first
    if SIGNALS_FILE.exists():
        import shutil
        shutil.copy(SIGNALS_FILE, SIGNALS_BAK)
        print(f"[+] Real whale_signals.json backed up to .bak")

    with open(SIGNALS_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"[+] Synthetic signal injected into whale_signals.json")
    print(f"    Tier: 1 | Divergence: {divergence*100:.1f}% | Market: {market_name[:50]}")
    return synthetic_signal


def patch_bridge_for_test():
    """
    Temporarily set TEST flag in environment so bridge prefixes
    the Telegram message with [TEST DO NOT FUND].
    We do this by setting an env var the bridge reads.
    """
    os.environ["BRIDGE_TEST_MODE"] = "1"


def run_bridge():
    """Run paper_signal_bridge.py normally — it reads whale_signals.json."""
    import subprocess
    venv_python = str(WORKSPACE / "skills/polyclaw/.venv/bin/python")
    bridge_path = str(WORKSPACE / "paper_trading/paper_signal_bridge.py")

    print("\n[*] Running paper_signal_bridge.py...")
    env = os.environ.copy()
    env["BRIDGE_TEST_MODE"] = "1"

    result = subprocess.run(
        [venv_python, bridge_path],
        env=env,
        capture_output=True,
        text=True,
        cwd=str(WORKSPACE)
    )
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr[:500])
    return result.returncode == 0


def restore_real_signals():
    """Restore original whale_signals.json from backup."""
    if SIGNALS_BAK.exists():
        import shutil
        shutil.copy(SIGNALS_BAK, SIGNALS_FILE)
        SIGNALS_BAK.unlink()
        print("[+] Real whale_signals.json restored from backup")


def print_next_steps(signal):
    """Print the exact command Ankur needs to run after approving Telegram."""
    side        = "YES"
    market_id   = signal["market_id"]
    yes_price   = signal["yes_price"]
    divergence  = signal["divergence"]

    print("\n" + "="*60)
    print("TELEGRAM PROPOSAL SENT")
    print("="*60)
    print("Check your Telegram now.")
    print("Message is prefixed: [TEST DO NOT FUND]")
    print("")
    print("When you are ready to test the full chain, run:")
    print("")
    print(f"  cd /home/ubuntu/.openclaw/workspace")
    print(f"  source skills/polyclaw/.venv/bin/activate")
    print(f"  BOT_ENV=e2e_test python paper_trading/paper_engine.py buy \\")
    print(f"    {market_id} {side} 5.00 {yes_price:.2f} 1 \"E2E Test Tariff Market\"")
    print("")
    print("Then verify test ledger updated:")
    print("  cat paper_trading/test_ledger.json")
    print("")
    print("Production ledger.json is UNTOUCHED throughout.")
    print("="*60)


if __name__ == "__main__":
    print("\n" + "="*60)
    print("MISSION 8 - END-TO-END PIPELINE TEST")
    print("="*60)

    # Step 1: Find real market
    market, yes_price = find_target_market()
    if not market:
        # Fallback: use hardcoded placeholder if API search fails
        print("[!] Market not found by keyword — using fallback placeholder")
        market = {
            "conditionId": "test_condition_001",
            "question":    "Will the U.S. collect between $500b and $1t in revenue in 2025?",
            "slug":        "us-revenue-500b-1t-2025",
        }
        yes_price = 0.50

    # Step 2: Inject synthetic signal
    signal = inject_synthetic_signal(market, yes_price)

    # Step 3: Run bridge (sends real Telegram with [TEST] prefix)
    success = run_bridge()

    # Step 4: Restore real signals file
    restore_real_signals()

    if success:
        print_next_steps(signal)
    else:
        print("\n[x] Bridge failed — check bridge.log for details")
        print("    cat paper_trading/bridge.log | tail -20")
        sys.exit(1)
