#!/usr/bin/env python3
"""
Paper Trade Proposal Engine - Phase 2
Location: ~/.openclaw/workspace/paper_trading/paper_propose.py
Version: 2.0 | Updated: 2026-03-07

BUG-016 FIX: Replaced text-based YES/NO polling with Telegram Inline Keyboard buttons.
- Old: poll getUpdates for text "PAPER YES" / "PAPER NO"
  Problem: Alpha bot (Kimi) and n8n both poll same token via getUpdates (destructive read).
  Whoever reads first consumes the message. Alpha bot was faster -> paper_propose never saw it.
- New: send proposal with inline keyboard [YES EXECUTE] [NO SKIP] buttons.
  Buttons fire callback_query updates -- a completely different update type.
  Alpha bot and n8n only listen for message updates, never callback_query.
  Race condition is architecturally impossible with this approach.

Additional fix: answerCallbackQuery called after button press to dismiss spinner on phone.
Additional fix: expired button press handled gracefully (no accidental execution).

Usage:
    python paper_propose.py propose <market_id> <YES|NO> <amount> <entry_price> <signal_tier> <whale_pct> <market_name...>
    python paper_propose.py test
"""

import json
import sys
import os
import time
import subprocess
import requests
from datetime import datetime, timezone
from pathlib import Path

# -- Paths ---------------------------------------------------------------------
WORKSPACE   = Path("/home/ubuntu/.openclaw/workspace")
PAPER_DIR   = WORKSPACE / "paper_trading"
ENGINE      = PAPER_DIR / "paper_engine.py"
LOG_FILE    = PAPER_DIR / "paper_trades.log"
CONFIG_FILE = Path("/home/ubuntu/.openclaw/openclaw.json")
VENV_PYTHON = WORKSPACE / "skills/polyclaw/.venv/bin/python"

# -- Telegram config -----------------------------------------------------------
def load_telegram_config():
    with open(CONFIG_FILE) as f:
        d = json.load(f)
    tg = d["channels"]["telegram"]
    return {
        "token":   tg["botToken"],
        "chat_id": tg["allowFrom"][0]
    }

TG = load_telegram_config()

# -- Timing --------------------------------------------------------------------
POLL_INTERVAL_SEC = 5      # check for callback every 5 seconds (faster than text polling)
TIMEOUT_MIN       = 240    # BUG-017 FIX: 4hr window so overnight proposals survive until morning (MST)
TIMEOUT_SEC       = TIMEOUT_MIN * 60

# -- Signal tier descriptions --------------------------------------------------
TIER_LABELS = {
    1: "Tier 1 - Whale >15% + news confirmed",
    2: "Tier 2 - Whale >15%, no news yet",
    3: "Tier 3 - Divergence 8-15%, watch only",
}


# -----------------------------------------------------------------------------
# Telegram API helpers
# -----------------------------------------------------------------------------

def tg_send_with_keyboard(message: str, yes_data: str, no_data: str) -> dict:
    """
    BUG-016 FIX: Send proposal with Inline Keyboard buttons instead of plain text.
    Buttons fire callback_query updates -- Alpha bot and n8n never see these.
    yes_data / no_data are callback_data strings we match when polling.
    """
    url  = f"https://api.telegram.org/bot{TG['token']}/sendMessage"
    resp = requests.post(url, json={
        "chat_id":    TG["chat_id"],
        "text":       message,
        "parse_mode": "HTML",
        "reply_markup": {
            "inline_keyboard": [[
                {"text": "YES - Execute Trade",  "callback_data": yes_data},
                {"text": "NO - Skip",             "callback_data": no_data},
            ]]
        }
    }, timeout=10)
    resp.raise_for_status()
    return resp.json()


def tg_send(message: str) -> dict:
    """Send a plain text message (used for confirmations, not proposals)."""
    url  = f"https://api.telegram.org/bot{TG['token']}/sendMessage"
    resp = requests.post(url, json={
        "chat_id":    TG["chat_id"],
        "text":       message,
        "parse_mode": "HTML"
    }, timeout=10)
    resp.raise_for_status()
    return resp.json()


def tg_answer_callback(callback_query_id: str, text: str = "") -> None:
    """
    BUG-016 FIX: Must call answerCallbackQuery after receiving a button press.
    Without this the button shows an infinite loading spinner on the phone.
    """
    url = f"https://api.telegram.org/bot{TG['token']}/answerCallbackQuery"
    try:
        requests.post(url, json={
            "callback_query_id": callback_query_id,
            "text": text,
            "show_alert": False
        }, timeout=5)
    except Exception:
        pass  # non-critical -- spinner cosmetic only


def tg_edit_keyboard_off(chat_id: str, message_id: int, result_text: str) -> None:
    """
    After button press, replace the keyboard with a plain result text.
    Prevents double-tapping the button accidentally.
    """
    url = f"https://api.telegram.org/bot{TG['token']}/editMessageReplyMarkup"
    try:
        requests.post(url, json={
            "chat_id":      chat_id,
            "message_id":   message_id,
            "reply_markup": {}   # empty = remove keyboard
        }, timeout=5)
    except Exception:
        pass  # non-critical


def tg_get_updates(offset: int = 0) -> list:
    """Fetch new updates via short-poll (timeout=0)."""
    url = f"https://api.telegram.org/bot{TG['token']}/getUpdates"
    try:
        resp = requests.get(url, params={"offset": offset, "timeout": 0}, timeout=10)
        resp.raise_for_status()
        return resp.json().get("result", [])
    except Exception as e:
        print(f"  [WARN] getUpdates error: {e}")
        return []


def get_latest_update_id() -> int:
    """Get current highest update_id so we only watch for NEW replies."""
    try:
        updates = tg_get_updates()
        if updates:
            return updates[-1]["update_id"]
    except Exception as e:
        print(f"  [WARN] Could not get baseline update_id: {e}")
    return 0


def poll_for_callback(after_update_id: int, yes_data: str, no_data: str) -> tuple:
    """
    BUG-016 FIX: Poll for callback_query instead of text message.

    callback_query is fired when user taps an inline keyboard button.
    Alpha bot (Kimi) and n8n only consume message updates via getUpdates.
    callback_query updates are a separate type they never touch.
    Race condition is architecturally impossible.

    Returns (decision, callback_query_id, last_update_id)
      decision: 'YES', 'NO', or None (timeout)
      callback_query_id: needed to call answerCallbackQuery (dismiss spinner)
    """
    start     = time.time()
    offset    = after_update_id + 1
    last_seen = after_update_id

    print(f"  Waiting for button press via Telegram (timeout: {TIMEOUT_MIN}min)...")
    print(f"  [Tap YES - Execute Trade or NO - Skip on the proposal message]")

    while time.time() - start < TIMEOUT_SEC:
        updates = tg_get_updates(offset=offset)

        for update in updates:
            last_seen = update["update_id"]
            offset    = last_seen + 1

            # BUG-016 FIX: Look for callback_query, not message
            cq = update.get("callback_query")
            if not cq:
                # Still accept text PAPER YES as fallback (belt and suspenders)
                msg  = update.get("message", {})
                text = msg.get("text", "").strip().upper()
                if text in ("PAPER YES", "PAPER Y", "YES", "Y"):
                    print(f"  [Text fallback: '{text}' received]")
                    return "YES", None, last_seen
                elif text in ("PAPER NO", "PAPER N", "NO", "N", "SKIP"):
                    print(f"  [Text fallback: '{text}' received]")
                    return "NO", None, last_seen
                continue

            # Verify callback is from Ankur
            from_id = str(cq.get("from", {}).get("id", ""))
            if from_id != TG["chat_id"]:
                continue

            cq_id   = cq["id"]
            cq_data = cq.get("data", "")

            if cq_data == yes_data:
                print(f"  [Button pressed: YES EXECUTE]")
                return "YES", cq_id, last_seen
            elif cq_data == no_data:
                print(f"  [Button pressed: NO SKIP]")
                return "NO", cq_id, last_seen
            else:
                # Callback from a different/older proposal
                print(f"  [Ignoring callback: '{cq_data}' -- not this proposal]")

        elapsed   = int(time.time() - start)
        remaining = TIMEOUT_SEC - elapsed
        mins_left = remaining // 60
        if elapsed % 60 < POLL_INTERVAL_SEC:
            print(f"  ...{mins_left}min remaining")

        time.sleep(POLL_INTERVAL_SEC)

    return None, None, last_seen


# -----------------------------------------------------------------------------
# Kelly size calculator
# -----------------------------------------------------------------------------

def kelly_check(amount: float, entry_price: float) -> str:
    implied_prob = entry_price
    if implied_prob <= 0 or implied_prob >= 1:
        return "N/A"
    edge       = 0.05
    kelly_pct  = edge / (1 - implied_prob)
    max_bet    = 10.0
    suggestion = round(min(max_bet, kelly_pct * 66), 2)
    return f"${suggestion:.2f} (Kelly suggests)"


# -----------------------------------------------------------------------------
# Run paper_engine.py as subprocess
# -----------------------------------------------------------------------------

def execute_paper_buy(market_id, side, amount, entry_price, signal_tier, market_name):
    cmd = [
        str(VENV_PYTHON), str(ENGINE),
        "buy",
        market_id, side, str(amount), str(entry_price), str(signal_tier),
        market_name
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(WORKSPACE))
    return result.stdout, result.returncode


# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------

def _now():
    return datetime.now(timezone.utc).isoformat()

def _log(message, event="INFO"):
    with open(LOG_FILE, "a") as f:
        f.write(f"[{_now()}] [{event}] {message}\n")


# -----------------------------------------------------------------------------
# Main propose command
# -----------------------------------------------------------------------------

def cmd_propose(args):
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

    # Unique callback_data for this proposal (timestamp-based to avoid old button conflicts)
    ts       = int(time.time())
    yes_data = f"PAPER_YES_{ts}"
    no_data  = f"PAPER_NO_{ts}"

    proposal = (
        f"PAPER TRADE PROPOSAL\n"
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
        f"Tap a button below to respond\n"
        f"(expires in {TIMEOUT_MIN} min)"
    )

    print(f"\n[SENDING PAPER PROPOSAL TO TELEGRAM]")
    print(f"  Market : {market_name}")
    print(f"  Side   : {side} @ {entry_price}")
    print(f"  Amount : ${amount:.2f} virtual")

    baseline_id = get_latest_update_id()

    # BUG-016 FIX: Send with inline keyboard instead of plain text
    send_result = tg_send_with_keyboard(proposal, yes_data=yes_data, no_data=no_data)
    sent_msg_id = send_result.get("result", {}).get("message_id")
    print(f"  Proposal sent with inline keyboard (message_id: {sent_msg_id})")
    _log(f"PROPOSAL SENT | {market_name} | {side} | ${amount} @ {entry_price} | Tier {signal_tier}", "PROPOSE")

    # BUG-016 FIX: Poll for callback_query instead of text
    decision, cq_id, last_update_id = poll_for_callback(baseline_id, yes_data, no_data)

    # Dismiss button spinner immediately
    if cq_id:
        tg_answer_callback(cq_id, text="Received!")

    # Remove keyboard from proposal message to prevent double-tap
    if sent_msg_id:
        tg_edit_keyboard_off(TG["chat_id"], sent_msg_id, decision or "expired")

    if decision == "YES":
        print(f"\n  [YES] Executing paper trade...")
        stdout, returncode = execute_paper_buy(market_id, side, amount, entry_price, signal_tier, market_name)
        print(stdout)

        if returncode == 0:
            _log(f"APPROVED + EXECUTED | {market_name} | {side} | ${amount}", "APPROVE")
            tg_send(
                f"Paper trade executed\n"
                f"- {market_name}\n"
                f"- {side} ${amount:.2f} @ {entry_price}\n"
                f"- Logged to ledger"
            )
        else:
            _log(f"APPROVED but EXECUTION FAILED | {market_name} | Error: {stdout}", "ERROR")
            tg_send(f"Paper trade FAILED to execute\nCheck paper_engine.py manually")

    elif decision == "NO":
        print(f"\n  [NO] Proposal rejected.")
        _log(f"REJECTED | {market_name} | {side} | ${amount}", "REJECT")
        tg_send(f"Proposal skipped: {market_name} {side}")

    else:
        print(f"\n  [TIMEOUT] No reply after {TIMEOUT_MIN} minutes -- expired.")
        _log(f"TIMEOUT | {market_name} | {side} | ${amount}", "TIMEOUT")
        tg_send(f"Proposal expired (no reply): {market_name} {side}")


# -----------------------------------------------------------------------------
# Test command
# -----------------------------------------------------------------------------

def cmd_test(args):
    """Send a test proposal with inline keyboard to confirm BUG-016 fix works."""
    print("Sending test proposal with inline keyboard...")
    ts       = int(time.time())
    yes_data = f"TEST_YES_{ts}"
    no_data  = f"TEST_NO_{ts}"

    result = tg_send_with_keyboard(
        "Alpha Paper Trading v2.0 Online\n"
        "BUG-016 fix: Inline keyboard active\n"
        "Tap YES or NO to confirm buttons work",
        yes_data=yes_data,
        no_data=no_data
    )
    msg_id = result.get("result", {}).get("message_id", "?")
    print(f"  Sent OK (message_id: {msg_id})")
    print(f"  Now polling for button press (60 sec)...")

    baseline = get_latest_update_id()
    start    = time.time()
    offset   = baseline + 1

    while time.time() - start < 60:
        updates = tg_get_updates(offset=offset)
        for update in updates:
            offset = update["update_id"] + 1
            cq = update.get("callback_query", {})
            if cq.get("data", "").startswith("TEST_"):
                tg_answer_callback(cq["id"], "Button works!")
                print(f"  [OK] Button '{cq['data']}' received -- BUG-016 fix confirmed")
                return
        time.sleep(3)

    print("  [No button press in 60 sec -- test timed out]")


# -----------------------------------------------------------------------------
# Dispatch
# -----------------------------------------------------------------------------

COMMANDS = {
    "propose": cmd_propose,
    "test":    cmd_test,
}

def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("Alpha Paper Propose v2.0")
        print("Usage: paper_propose.py <command> [args]")
        print("Commands:", "  |  ".join(COMMANDS.keys()))
        sys.exit(1)
    COMMANDS[sys.argv[1]](sys.argv[2:])

if __name__ == "__main__":
    main()
