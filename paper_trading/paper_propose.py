#!/usr/bin/env python3
"""
Paper Trade Proposal Engine - Phase 2
Location: ~/.openclaw/workspace/paper_trading/paper_propose.py
Version: 1.0 | Built: 2026-02-22

Sends a paper trade proposal to Ankur via Telegram.
Polls for YES/NO reply. Auto-executes via paper_engine.py if approved.
Logs rejection if denied or timed out.

Usage:
    python paper_propose.py propose <market_id> <YES|NO> <amount> <entry_price> <signal_tier> <whale_pct> <market_name...>

Example:
    python paper_propose.py propose 613835 YES 8.00 0.74 1 22 Best Picture OBAA

Arguments:
    market_id     - Polymarket market ID
    side          - YES or NO
    amount        - Virtual USDC to bet
    entry_price   - Current market price (e.g. 0.74)
    signal_tier   - 1, 2, or 3
    whale_pct     - Whale divergence % (0 if none)
    market_name   - Rest of args become the market name
"""

import json
import sys
import os
import time
import subprocess
import requests
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────
WORKSPACE    = Path("/home/ubuntu/.openclaw/workspace")
PAPER_DIR    = WORKSPACE / "paper_trading"
ENGINE       = PAPER_DIR / "paper_engine.py"
LOG_FILE     = PAPER_DIR / "paper_trades.log"
CONFIG_FILE  = Path("/home/ubuntu/.openclaw/openclaw.json")
VENV_PYTHON  = WORKSPACE / "skills/polyclaw/.venv/bin/python"

# ── Telegram config ────────────────────────────────────────────────────────
def load_telegram_config():
    with open(CONFIG_FILE) as f:
        d = json.load(f)
    tg = d["channels"]["telegram"]
    return {
        "token":   tg["botToken"],
        "chat_id": tg["allowFrom"][0]
    }

TG = load_telegram_config()

# ── Timing ─────────────────────────────────────────────────────────────────
POLL_INTERVAL_SEC = 15     # check for reply every 15 seconds
TIMEOUT_MIN       = 30     # proposal expires after 30 minutes
TIMEOUT_SEC       = TIMEOUT_MIN * 60

# ── Signal tier descriptions ───────────────────────────────────────────────
TIER_LABELS = {
    1: "Tier 1 - Whale >15% + news confirmed",
    2: "Tier 2 - Whale >15%, no news yet",
    3: "Tier 3 - Divergence 8-15%, watch only",
}


# ─────────────────────────────────────────────────────────────────────────
# Telegram API helpers
# ─────────────────────────────────────────────────────────────────────────

def tg_send(message: str) -> dict:
    """Send a message to Ankur's Telegram."""
    url  = f"https://api.telegram.org/bot{TG['token']}/sendMessage"
    resp = requests.post(url, json={
        "chat_id":    TG["chat_id"],
        "text":       message,
        "parse_mode": "HTML"
    }, timeout=10)
    resp.raise_for_status()
    return resp.json()


def tg_get_updates(offset: int = 0, retries: int = 5) -> list:
    """
    Fetch new messages from Telegram using short-poll (timeout=0).
    Uses retries with backoff to avoid 409 conflict with OpenClaw long-poller.
    """
    url = f"https://api.telegram.org/bot{TG['token']}/getUpdates"
    for attempt in range(retries):
        try:
            resp = requests.get(url, params={
                "offset":  offset,
                "timeout": 0   # short-poll: returns immediately, avoids 409 conflict
            }, timeout=10)
            if resp.status_code == 409:
                # OpenClaw long-poll is active — wait and retry
                wait = 3 * (attempt + 1)
                print(f"  [409 conflict with OpenClaw poller — retrying in {wait}s]")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json().get("result", [])
        except requests.exceptions.HTTPError:
            if attempt < retries - 1:
                time.sleep(3)
            else:
                raise
    return []


def get_latest_update_id() -> int:
    """Get current highest update_id so we only watch for NEW replies."""
    try:
        updates = tg_get_updates()
        if updates:
            return updates[-1]["update_id"]
    except Exception as e:
        print(f"  [WARN] Could not get baseline update_id: {e} — starting from 0")
    return 0


def poll_for_reply(after_update_id: int) -> tuple[str | None, int]:
    """
    Poll Telegram for a YES or NO reply from Ankur.
    Returns (decision, last_update_id) where decision is 'YES', 'NO', or None (timeout).
    """
    start     = time.time()
    offset    = after_update_id + 1
    last_seen = after_update_id

    print(f"  Waiting for your Telegram reply (timeout: {TIMEOUT_MIN}min)...")

    while time.time() - start < TIMEOUT_SEC:
        try:
            updates = tg_get_updates(offset=offset)
            for update in updates:
                last_seen = update["update_id"]
                offset    = last_seen + 1

                msg  = update.get("message", {})
                text = msg.get("text", "").strip().upper()
                from_id = str(msg.get("from", {}).get("id", ""))

                # Only accept replies from Ankur
                if from_id != TG["chat_id"]:
                    continue

                # Accept PAPER YES / PAPER NO (preferred - avoids n8n conflict)
                # Also accept plain YES / NO as fallback
                if text in ("PAPER YES", "PAPER Y", "P YES", "YES", "Y"):
                    return "YES", last_seen
                elif text in ("PAPER NO", "PAPER N", "P NO", "NO", "N", "SKIP", "PASS"):
                    return "NO", last_seen
                else:
                    # Not a recognised reply - n8n or other bot may have sent this
                    print(f"  [Ignoring: '{text}'] - waiting for PAPER YES or PAPER NO")

        except Exception as e:
            print(f"  [WARN] Poll error: {e}")

        elapsed = int(time.time() - start)
        remaining = TIMEOUT_SEC - elapsed
        mins_left = remaining // 60
        if elapsed % 60 < POLL_INTERVAL_SEC:  # print countdown every ~minute
            print(f"  ...{mins_left}min remaining")

        time.sleep(POLL_INTERVAL_SEC)

    return None, last_seen


# ─────────────────────────────────────────────────────────────────────────
# Kelly size calculator
# ─────────────────────────────────────────────────────────────────────────

def kelly_check(amount: float, entry_price: float) -> str:
    """Return a quick Kelly context note."""
    implied_prob = entry_price
    if implied_prob <= 0 or implied_prob >= 1:
        return "N/A"
    # Simple edge estimate: assume fair value is 5% better than market
    edge       = 0.05
    kelly_pct  = edge / (1 - implied_prob)
    max_bet    = 10.0
    suggestion = round(min(max_bet, kelly_pct * 66), 2)  # based on $66 virtual bankroll
    return f"${suggestion:.2f} (Kelly suggests)"


# ─────────────────────────────────────────────────────────────────────────
# Run paper_engine.py as subprocess
# ─────────────────────────────────────────────────────────────────────────

def execute_paper_buy(market_id, side, amount, entry_price, signal_tier, market_name):
    cmd = [
        str(VENV_PYTHON),
        str(ENGINE),
        "buy",
        market_id, side, str(amount), str(entry_price), str(signal_tier),
        market_name
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(WORKSPACE))
    return result.stdout, result.returncode


# ─────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────

def _now():
    return datetime.now(timezone.utc).isoformat()


def _log(message, event="INFO"):
    with open(LOG_FILE, "a") as f:
        f.write(f"[{_now()}] [{event}] {message}\n")


# ─────────────────────────────────────────────────────────────────────────
# Main propose command
# ─────────────────────────────────────────────────────────────────────────

def cmd_propose(args):
    """
    Send a paper trade proposal to Telegram and wait for YES/NO.
    """
    if len(args) < 7:
        print("Usage: propose <market_id> <YES|NO> <amount> <entry_price> <signal_tier> <whale_pct> <market_name...>")
        sys.exit(1)

    market_id   = args[0]
    side        = args[1].upper()
    amount      = float(args[2])
    entry_price = float(args[3])
    signal_tier = int(args[4])
    whale_pct   = float(args[5])
    market_name = " ".join(args[6:])

    tier_label  = TIER_LABELS.get(signal_tier, f"Tier {signal_tier}")
    roi_target  = round(((1.0 - entry_price) / entry_price) * 100, 1) if side == "YES" else round((entry_price / (1 - entry_price)) * 100, 1)
    kelly_note  = kelly_check(amount, entry_price)

    # Format Telegram proposal (bullets + emojis, no tables — per CLAUDE.md)
    proposal = (
        f"📄 <b>PAPER TRADE PROPOSAL</b>\n"
        f"\n"
        f"- Market: {market_name}\n"
        f"- Side: {side}\n"
        f"- Entry Price: {entry_price:.2f}c\n"
        f"- Amount: ${amount:.2f} virtual USDC\n"
        f"- Max ROI if correct: +{roi_target:.1f}%\n"
        f"\n"
        f"- Signal: {tier_label}\n"
        f"- Whale Divergence: {whale_pct:.1f}%\n"
        f"- Kelly Sizing: {kelly_note}\n"
        f"\n"
        f"- Market ID: {market_id}\n"
        f"\n"
        f"Reply <b>PAPER YES</b> to execute paper trade\n"
        f"Reply <b>PAPER NO</b> to skip\n"
        f"(expires in {TIMEOUT_MIN} min)\n"
        f"\n"
        f"<i>Use PAPER prefix to avoid conflicts with other bots</i>"
    )

    print(f"\n[SENDING PAPER PROPOSAL TO TELEGRAM]")
    print(f"  Market : {market_name}")
    print(f"  Side   : {side} @ {entry_price}")
    print(f"  Amount : ${amount:.2f} virtual")

    # Get current update_id baseline BEFORE sending (so we only catch new replies)
    baseline_id = get_latest_update_id()

    # Send proposal
    send_result = tg_send(proposal)
    sent_msg_id = send_result.get("result", {}).get("message_id", "?")
    print(f"  Proposal sent (message_id: {sent_msg_id})")
    _log(f"PROPOSAL SENT | {market_name} | {side} | ${amount} @ {entry_price} | Tier {signal_tier}", "PROPOSE")

    # Poll for reply
    decision, last_update_id = poll_for_reply(baseline_id)

    if decision == "YES":
        print(f"\n  [YES received] Executing paper trade...")
        stdout, returncode = execute_paper_buy(market_id, side, amount, entry_price, signal_tier, market_name)
        print(stdout)

        if returncode == 0:
            _log(f"APPROVED + EXECUTED | {market_name} | {side} | ${amount}", "APPROVE")
            tg_send(
                f"- Paper trade executed\n"
                f"- {market_name} {side} ${amount:.2f} @ {entry_price}\n"
                f"- Logged to ledger"
            )
        else:
            _log(f"APPROVED but EXECUTION FAILED | {market_name} | Error: {stdout}", "ERROR")
            tg_send(f"- Paper trade FAILED to execute\n- Check paper_engine.py manually")

    elif decision == "NO":
        print(f"\n  [NO received] Proposal rejected — skipping.")
        _log(f"REJECTED | {market_name} | {side} | ${amount}", "REJECT")
        tg_send(f"- Proposal skipped: {market_name} {side}")

    else:
        print(f"\n  [TIMEOUT] No reply after {TIMEOUT_MIN} minutes — proposal expired.")
        _log(f"TIMEOUT | {market_name} | {side} | ${amount}", "TIMEOUT")
        tg_send(f"- Proposal expired (no reply): {market_name} {side}")


# ─────────────────────────────────────────────────────────────────────────
# Quick test — just sends a ping message
# ─────────────────────────────────────────────────────────────────────────

def cmd_test(args):
    """Send a test message to confirm Telegram is working."""
    print("Sending test message to Telegram...")
    result = tg_send(
        "- Alpha Paper Trading - Phase 2 Online\n"
        "- Telegram proposal loop is working\n"
        "- Ready to send paper trade proposals"
    )
    msg_id = result.get("result", {}).get("message_id", "?")
    print(f"  Sent OK (message_id: {msg_id})")


# ─────────────────────────────────────────────────────────────────────────
# Dispatch
# ─────────────────────────────────────────────────────────────────────────

COMMANDS = {
    "propose": cmd_propose,
    "test":    cmd_test,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("Alpha Paper Propose v1.0")
        print("Usage: paper_propose.py <command> [args]")
        print("Commands:", "  |  ".join(COMMANDS.keys()))
        sys.exit(1)

    COMMANDS[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    main()
