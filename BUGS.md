# BUGS.md — Alpha Bot Issue Tracker
# Created: 2026-02-25
# Rule: Log BEFORE fixing. Update status AFTER fix confirmed.

---

## BUG-001 | Duplicate Guard Spam — Same Market Proposed Every 2 Hours
Date: 2026-02-25
Status: FIXED v3
Severity: HIGH
Affected: paper_signal_bridge.py + pending_proposals.json

SYMPTOM:
Telegram flooded with same alert every 2 hours all night.
Market: Will John Cornyn win 2026 Texas Republican Pri
Fired at: 23:00, 01:00, 03:00, 05:00, 07:00 (every scan)

ROOT CAUSE:
pending_proposals.json resets at UTC midnight to empty list.
Bridge duplicate guard checks this list, finds nothing, proposes again.
Exposure guard blocks it correctly but still sends Telegram alert.
Result: infinite spam loop every 2 hours.
Secondary: bridge never cross-checks ledger.json open_positions.

FIX APPLIED:
1. Manually inject Cornyn into pending_proposals.json
2. Patch bridge duplicate check to also check ledger.json positions
FILES CHANGED:
- paper_trading/pending_proposals.json
- paper_trading/paper_signal_bridge.py

PREVENTION:
Duplicate guard now has two layers:
Layer 1: pending_proposals.json (resets daily)
Layer 2: ledger.json open+resolved positions (permanent, never resets)

LESSON:
Never rely on single source for deduplication when that source can reset.
Always cross-check permanent ledger as ground truth.

---

## BUG-002 | Alpha Hallucinating Rojas Trade Missing
Date: 2026-02-25
Status: FIXED
Severity: MEDIUM
Affected: ALPHA_MEMORY.md (stale data)

SYMPTOM:
Alpha said Rojas trade never existed. Said balance $1,000 and
platform PolySimulator. All wrong.

ROOT CAUSE:
ALPHA_MEMORY.md frozen at Feb 19. Alpha reading stale docs as truth.
Ledger.json was correct all along.

FIX APPLIED:
ALPHA_MEMORY.md fully rewritten to v3.0 on Feb 24, 2026.
FILES CHANGED:
- ALPHA_MEMORY.md

PREVENTION:
Update ALPHA_MEMORY.md at end of every session where state changes.
Mission 9 tool registration fixes this permanently via live execution.

LESSON:
Memory files drift. For live financial data Alpha must always execute
paper_engine.py status rather than reading memory files.

---

## BUG-003 | Exposure Guard Misread As Bug (False Alarm)
Date: 2026-02-25
Status: NOT A BUG — Working As Designed
Severity: N/A
Affected: paper_signal_bridge.py exposure guard

SYMPTOM:
User saw Exposure 42.3% but portfolio showed 27.2% deployed.

ROOT CAUSE:
27.2% = current invested / starting balance (current state)
42.3% = (current + proposed trade) / starting (post-trade projection)
Guard correctly calculates POST-TRADE exposure. Working as designed.

FIX APPLIED:
Alert message updated to say "Post-trade exposure: 42.3%" for clarity.
FILES CHANGED:
- paper_trading/paper_signal_bridge.py (message only)

LESSON:
Always verify whether a guard is broken before declaring a bug.
Message clarity matters as much as logic correctness.

---

## TEMPLATE (Copy for new bugs)

## BUG-00X | Title
Date:
Status: OPEN / FIXING / FIXED / NOT A BUG
Severity: CRITICAL / HIGH / MEDIUM / LOW
Affected:
SYMPTOM:
ROOT CAUSE:
FIX APPLIED:
FILES CHANGED:
PREVENTION:
LESSON:


### BUG-001 Fix History
v1: Manually injected Cornyn into pending_proposals.json
v2: Bridge records blocked proposals with status=blocked
v2 gap: duplicate guard only checked status=sent not status=blocked
v3: Fixed guard to check both sent+blocked status
v3 gap: blocked TTL was 30min same as sent - expired and spammed again
v4 (current): Blocked proposals now suppressed 48hrs (2880min) vs 30min for sent
Lesson: Exposure guard blocks are semi-permanent - need long TTL not short

v4 gap: Cleanup section had datetime timezone mismatch error
        offset-naive vs offset-aware datetime comparison crashed bridge
v5 (final): Added .replace(tzinfo=timezone.utc) for naive datetimes in cleanup
Status: FIXED v5 - awaiting next scan confirmation

v5 gap: REAL ROOT CAUSE FOUND - Guard order was wrong the entire time
        Guard 2 (Exposure) fired -> sent Telegram -> continue
        Guard 3 (Duplicate) NEVER RAN because continue skipped it
        All previous fixes were patching symptoms not root cause

v6 FINAL FIX: Swapped guard order
        Guard 1: Tier check
        Guard 2: Duplicate (runs FIRST - silent block, no Telegram)
        Guard 3: Exposure (only reached for fresh markets)
        Guard 4: Category cap
Status: FIXED v6 - DEFINITIVE - pushed to GitHub commit 1e5f971
Date: Feb 26, 2026
Lesson: When bug survives multiple fixes, read the full execution flow
        Fixing symptoms without reading the code wastes days
        Root cause was 1 line - guard order. Found in 5 min by reading properly.

v5 gap: Bracket placement wrong in cleanup section
        .total_seconds() called on datetime object instead of timedelta
        AttributeError: 'datetime.datetime' object has no attribute 'total_seconds'
v6 FINAL: Fixed bracket placement - now correctly calculates timedelta first then .total_seconds()
        Also: cron for whale+bridge was wiped during EC2 reboot - restored
Status: FIXED v6 - cron restored - datetime clean - pushed commit 4d46fee
Date: Feb 26, 2026

FULL BUG-001 LESSONS SUMMARY:
1. Always read full execution flow before patching symptoms
2. Guard order matters - duplicate must run before exposure
3. Blocked proposals need long TTL (48hrs) not short (30min)
4. Datetime timezone consistency - always use timezone-aware datetimes
5. Bracket placement in complex expressions - test carefully
6. EC2 reboots wipe crontab - always verify cron after any reboot
7. Health checks needed - silent failures go undetected for hours

---
## BUG-002 - Exposure Guard Spam + Cleanup TTL Wipes Blocked Records
Date: Feb 27, 2026
Status: FIXED (single pass, 4 bugs)

### ROOT CAUSE
Cleanup TTL at bottom of bridge used flat PROPOSAL_TTL_MINS * 2 (60 min) for ALL proposals
regardless of status. Blocked records should survive 48hrs (2880 min) but were wiped after 60 min.
Next scan 120 min later = blocked record gone = duplicate guard passes = exposure guard fires again
= Telegram spam every 2 hours. Exactly what Ankur saw in screenshot.

### ALL 4 BUGS IN THIS BATCH

Bug 1 - Cleanup TTL wipes blocked records after 60 min (ROOT CAUSE of spam)
  Location: paper_signal_bridge.py line ~537 cleanup section
  Problem:  PROPOSAL_TTL_MINS * 2 = 60 min applied to ALL proposals
  Fix:      Respect status - blocked = 2880 min TTL, sent = 60 min TTL

Bug 2 - Exposure guard sends Telegram on every repeat block
  Location: paper_signal_bridge.py line ~453 exposure guard block handler
  Problem:  Telegram fires even when market already has a blocked record
  Fix:      Check if market already blocked before sending Telegram alert

Bug 3 - Trim boundary hits exactly 40.0% which fails strict < check
  Location: paper_signal_bridge.py guard_exposure function
  Problem:  Trim sets amount = headroom so new_exposure = exactly 40.0%
            guard_exposure uses < (strict) so 40.0% fails even at cap
  Fix:      Change < to <= in guard_exposure

Bug 4 - Health check cannot find Telegram creds
  Location: scripts/health_check.py load_env() function
  Problem:  Reads TELEGRAM_BOT_TOKEN from .env but creds are in openclaw.json
  Fix:      Read bot token and chat_id from openclaw.json directly

### LESSONS
1. Cleanup TTL must be status-aware - never use flat TTL for mixed-status records
2. Spam guard needs two layers: duplicate guard (primary) + no-repeat Telegram (secondary)
3. Trim logic and guard boundary must use same operator (both <= or both <)
4. Health check creds must match where system actually stores them
5. Read FULL execution flow top to bottom before touching any code
6. Map ALL bugs before fixing ANY of them
