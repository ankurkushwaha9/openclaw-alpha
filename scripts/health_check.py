#!/usr/bin/env python3
"""
health_check.py - Alpha Bot Health Monitor
Runs every 2 hours, sends Telegram status report
Location: ~/.openclaw/workspace/scripts/health_check.py
"""

import os
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# ── Config ───────────────────────────────────────────────────────────────────
BASE = Path('/home/ubuntu/.openclaw/workspace')
BRIDGE_LOG   = BASE / 'paper_trading/bridge.log'
LEDGER       = BASE / 'paper_trading/ledger.json'
PENDING      = BASE / 'paper_trading/pending_proposals.json'
ENV_FILE     = BASE / '.env'

# Load Telegram creds from openclaw.json (that's where they actually live)
def load_telegram_creds():
    import json
    try:
        cfg = json.loads(open('/home/ubuntu/.openclaw/openclaw.json').read())
        token   = cfg['channels']['telegram']['botToken']
        chat_id = str(cfg['channels']['telegram']['allowFrom'][0])
        return token, chat_id
    except Exception as e:
        print(f"Cannot load Telegram creds from openclaw.json: {e}")
        return '', ''

def send_telegram(msg):
    import urllib.request, json
    token, chat_id = load_telegram_creds()
    if not token or not chat_id:
        print("No Telegram creds found")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({"chat_id": chat_id, "text": msg}).encode()
    req = urllib.request.Request(url, data=data,
                                  headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

# ── Checks ───────────────────────────────────────────────────────────────────

def check_last_scan():
    """When did the bridge last run?"""
    try:
        lines = BRIDGE_LOG.read_text().splitlines()
        # Find last [START] line
        for line in reversed(lines):
            if '[START]' in line:
                ts = line.split(']')[0].replace('[', '').strip()
                dt = datetime.fromisoformat(ts)
                age_mins = (datetime.now(timezone.utc) - dt).total_seconds() / 60
                if age_mins < 130:
                    return True, f"✅ Last scan: {int(age_mins)}min ago"
                else:
                    return False, f"⚠️ Last scan: {int(age_mins)}min ago (OVERDUE)"
        return False, "❌ No scan found in bridge.log"
    except Exception as e:
        return False, f"❌ Cannot read bridge.log: {e}"

def check_errors():
    """Any errors in last 50 lines of bridge.log?"""
    try:
        lines = BRIDGE_LOG.read_text().splitlines()[-50:]
        errors = [l for l in lines if 'Error' in l or 'Traceback' in l or 'Exception' in l]
        if errors:
            return False, f"❌ {len(errors)} error(s) in bridge.log"
        return True, "✅ No errors in bridge.log"
    except Exception as e:
        return False, f"❌ Cannot check errors: {e}"

def check_portfolio():
    """Current paper portfolio status."""
    try:
        d = json.loads(LEDGER.read_text())
        meta = d.get('meta', {})
        balance = meta.get('virtual_balance', 0)
        starting = meta.get('starting_balance', 66)
        positions = d.get('open_positions', [])
        pnl_pct = ((balance - starting) / starting) * 100
        return True, (f"📄 PAPER | Balance: ${balance:.2f} | "
                      f"Positions: {len(positions)} | "
                      f"P&L: {pnl_pct:+.1f}%")
    except Exception as e:
        return False, f"❌ Cannot read ledger: {e}"

def check_spam():
    """Is Cornyn still spamming?"""
    try:
        d = json.loads(PENDING.read_text())
        props = d.get('proposals', [])
        # Count how many times Cornyn appears
        cornyn = [p for p in props if 'Cornyn' in p.get('market_name', '') or
                  '0x781a' in p.get('market_id', '')]
        if len(cornyn) > 1:
            # Check if latest is recent (within 3 hours)
            latest = cornyn[-1]
            ts = datetime.fromisoformat(latest['sent_at'])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age_mins = (datetime.now(timezone.utc) - ts).total_seconds() / 60
            if age_mins < 130:
                return False, f"🚨 BUG-001 STILL ACTIVE - Cornyn fired {int(age_mins)}min ago"
        return True, "✅ No spam detected"
    except Exception as e:
        return False, f"❌ Cannot check pending: {e}"

def check_cron():
    """Are both crons active?"""
    try:
        result = subprocess.run(['crontab', '-u', 'ubuntu', '-l'],
                                capture_output=True, text=True)
        crons = result.stdout
        has_monitor = 'daily_monitor' in crons
        has_bridge  = 'whale_tracker' in crons
        if has_monitor and has_bridge:
            return True, "✅ Both crons active"
        elif has_monitor:
            return False, "⚠️ Whale+bridge cron MISSING"
        elif has_bridge:
            return False, "⚠️ Daily monitor cron MISSING"
        else:
            return False, "❌ ALL CRONS MISSING"
    except Exception as e:
        return False, f"❌ Cannot check cron: {e}"


def check_yes_no_loop():
    """Is paper_propose.py actually wired into the bridge? Core YES/NO loop check."""
    try:
        bridge_path = BASE / "paper_trading" / "paper_signal_bridge.py"
        propose_path = BASE / "paper_trading" / "paper_propose.py"

        if not bridge_path.exists():
            return False, "❌ paper_signal_bridge.py missing"
        if not propose_path.exists():
            return False, "❌ paper_propose.py missing"

        with open(bridge_path) as f:
            bridge_code = f.read()

        # Check that bridge actually calls paper_propose.py
        if "paper_propose.py" not in bridge_code:
            return False, "❌ YES/NO loop BROKEN - bridge not calling paper_propose.py"
        if "subprocess.run" not in bridge_code:
            return False, "❌ YES/NO loop BROKEN - no subprocess call in bridge"

        return True, "✅ YES/NO loop wired (bridge -> paper_propose.py)"
    except Exception as e:
        return False, f"❌ Cannot verify YES/NO loop: {e}"


def check_shadow_monitor():
    from pathlib import Path
    from datetime import datetime, timezone
    heartbeat = Path('/tmp/shadow_monitor.heartbeat')
    log_file = Path('/home/ubuntu/.openclaw/workspace/logs/routing.log')

    if not heartbeat.exists():
        return False, 'Shadow monitor NOT running - start: nohup python3 scripts/shadow_monitor.py >> /tmp/shadow_monitor.log 2>&1 &'

    try:
        last_beat = datetime.fromisoformat(heartbeat.read_text().strip())
        age = (datetime.now(timezone.utc) - last_beat).total_seconds()
        if age > 120:
            return False, f'Shadow monitor stale (last beat {int(age)}s ago)'
    except Exception:
        return False, 'Shadow monitor heartbeat unreadable'

    lines_count = 0
    if log_file.exists():
        lines_count = sum(1 for _ in open(log_file))

    return True, f'Shadow monitor running | routing.log: {lines_count} entries'

def run_health_check():
    now = datetime.now(timezone.utc).strftime('%b %d %H:%M UTC')
    
    checks = [
        check_cron(),
        check_last_scan(),
        check_errors(),
        check_portfolio(),
        check_spam(),
        check_yes_no_loop(),
        check_shadow_monitor(),
    ]
    
    all_ok = all(ok for ok, _ in checks)
    status = "🟢 ALL SYSTEMS OK" if all_ok else "🔴 ISSUES DETECTED"
    
    lines = [
        f"🤖 ALPHA HEALTH CHECK - {now}",
        f"{status}",
        "─────────────────────",
    ]
    for ok, msg in checks:
        lines.append(f"- {msg}")
    
    if not all_ok:
        lines.append("─────────────────────")
        lines.append("⚠️ Action may be required")
    
    report = "\n".join(lines)
    print(report)
    send_telegram(report)

if __name__ == '__main__':
    run_health_check()
