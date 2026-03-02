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

---

## BUG-004 | Bridge Log Duplicate Writes — 273KB Bloat / SSM Timeouts
Date: 2026-03-01
Status: FIXING
Severity: MEDIUM
Affected: paper_trading/paper_signal_bridge.py, paper_trading/bridge.log

SYMPTOM:
bridge.log grew to 273KB / 3,861 lines causing SSM reads to timeout.
Every log entry appeared 2x (sometimes 3x) with identical timestamps.
Claude could not read bridge.log via SSM - had to ask for manual runs.

ROOT CAUSE:
log() function in paper_signal_bridge.py does TWO writes per call:
  1. print(line)  → stdout → cron captures via >> bridge.log
  2. open(BRIDGE_LOG, "a") → writes directly to bridge.log
Cron line: python paper_signal_bridge.py >> paper_trading/bridge.log 2>&1
Both paths land in the same file = every log line written exactly 2x.
With ~30 log calls per run × 2x = 60 lines per run instead of 30.
Running every 2hrs × days = rapid bloat.

FIX APPLIED:
1. Archived bloated bridge.log → bridge.log.bak (273KB preserved)
2. Created fresh empty bridge.log
3. Removed print(line) from log() function — kept direct file write
   Cron >> redirect now captures nothing meaningful
   Result: exactly 1 write per log call going forward

FILES CHANGED:
- paper_trading/paper_signal_bridge.py (removed print(line) from log())
- paper_trading/bridge.log (archived → .bak, fresh file created)

PREVENTION:
Never mix stdout redirect (>>) in cron AND internal file writes in same script.
Choose one logging path — internal file write preferred (gives more control).

LESSON:
Read the cron AND the script together — bugs often live at the boundary.
A 5-minute code read would have caught this before 273KB of duplicate logs.

---

## BUG-004 | Bridge Log Duplicate Writes - 273KB Bloat / SSM Timeouts
Date: 2026-03-01
Status: FIXED
Severity: MEDIUM
Affected: paper_trading/paper_signal_bridge.py, paper_trading/bridge.log

SYMPTOM:
bridge.log grew to 273KB / 3,861 lines causing SSM reads to timeout.
Every log entry appeared 2x with identical timestamps.
Claude could not read bridge.log via SSM - had to ask for manual runs.

ROOT CAUSE:
log() function does TWO writes per call:
  1. print(line) - stdout - cron captures via >> bridge.log
  2. open(BRIDGE_LOG, "a") - writes directly to bridge.log
Cron: python paper_signal_bridge.py >> paper_trading/bridge.log 2>&1
Both paths land in the same file = every log line written exactly 2x.
30 log calls per run x 2 = 60 lines instead of 30. Every 2hrs = rapid bloat.

FIX APPLIED:
1. Archived bloated bridge.log to bridge.log.bak (273KB preserved)
2. Created fresh empty bridge.log
3. Removed print(line) from log() function - kept direct file write only
   Result: exactly 1 write per log call going forward

FILES CHANGED:
- paper_trading/paper_signal_bridge.py (removed print(line) from log())
- paper_trading/bridge.log (archived to .bak, fresh file created)

PREVENTION:
Never mix stdout redirect (>>) in cron AND internal file writes in same script.
Choose one logging path - internal file write preferred.

LESSON:
Read the cron AND the script together - bugs live at the boundary.
A 5-minute code read would have caught this before 273KB of duplicate logs.

---

## BUG-005 | Iran Positions Not Resolved - Stale polyclaw/positions.json + ALPHA_MEMORY.md
Date: 2026-03-01
Status: FIXED
Severity: HIGH
Affected: polyclaw/positions.json, ALPHA_MEMORY.md

SYMPTOM:
All 5 Iran positions still showing status "open" in polyclaw/positions.json
even though all Iran markets resolved on Feb 28, 2026 (US struck Iran).
ALPHA_MEMORY.md last updated Feb 24 - has no record of Iran trades at all.
Bot reporting wrong wallet balance (~$41) vs reality ($66 USDC).
Health check showing "2 positions / -27.3%" - Iran trades invisible to system.

ROOT CAUSE:
market-monitor.js crashed on Feb 16 with Web3 constructor error (Node v24.13.0).
Monitor never ran again after crash - no position resolution tracking.
polyclaw/positions.json never updated after Feb 16.
ALPHA_MEMORY.md never updated with Iran trade entries or resolution.
Result: Bot completely blind to Feb 28 strike event and resulting P&L.

IRAN POSITIONS RESOLUTION (confirmed via Polymarket + news sources):
1. US strikes Iran by Feb 28 - YES - WIN  - entry $1.00 @ 0.175 - payout $5.71 - profit +$4.71
2. US strikes Iran by Feb 16 - NO  - WIN  - entry $3.00 @ 0.9955 - payout $3.01 - profit +$0.01
3. US strikes Iran by Feb 20 - NO  - WIN  - entry $3.00 @ 0.935 - payout $3.21 - profit +$0.21
4. US strikes Iran by Feb 20 - YES - LOSS - entry $2.00 @ 0.065 - payout $0.00 - profit -$2.00
5. US strikes Iran by Feb 16 - NO  - WIN  - entry $2.00 @ 0.9955 - payout $2.01 - profit +$0.01
NET: Invested $11.00 - Returned $13.94 - Profit +$2.94 USDC

FIX APPLIED:
1. Updated polyclaw/positions.json - all 5 Iran positions marked resolved with P&L
2. Updated ALPHA_MEMORY.md - added Iran trade history + corrected wallet balance

FILES CHANGED:
- polyclaw/positions.json
- ALPHA_MEMORY.md

PREVENTION:
Fix market-monitor.js Web3 crash (BUG-006) so future resolutions auto-tracked.
Update ALPHA_MEMORY.md at end of every session where real money state changes.

LESSON:
A crashed monitor creates invisible blind spots - system says OK but data is stale.
Always verify monitor process is running after any EC2 reboot or code change.

---

## BUG-006 | Health Check "2 Positions / -27.3%" Misread As Bug
Date: 2026-03-01
Status: NOT A BUG - Working As Designed
Severity: N/A
Affected: scripts/health_check.py

SYMPTOM:
Health check reporting "Balance: $48.00 | Positions: 2 | P&L: -27.3%" every 2 hours.
Looked wrong compared to real wallet ($66 USDC, 8 positions).

ROOT CAUSE:
Health check reads paper trading ledger.json - NOT real money positions.
Numbers are 100% correct for the paper system:
  - $48 virtual balance (paper started at $66, Rojas position losing)
  - 2 open paper positions (OBAA Best Picture + Rojas Texas Case)
  - -27.3% = ($48 - $66) / $66 * 100 = correct paper P&L
Real money tracked separately in polyclaw/positions.json - different system.

FIX APPLIED:
No logic fix needed. One clarity improvement only:
Changed portfolio message from "Balance:" to "PAPER | Balance:"
So future health checks clearly say PAPER to avoid confusion.

FILES CHANGED:
- scripts/health_check.py (label only - no logic change)

SIDE EFFECT NOTED:
BUG-004 fix (archiving bridge.log) caused temporary empty bridge.log.
Health check will show "No scan found" until next cron run writes fresh START entry.
Self-heals automatically. Fix: copy tail of bridge.log.bak to bridge.log.

LESSON:
Always label which system (PAPER vs REAL) in health check messages.
Two parallel systems with similar numbers will always cause confusion without labels.
