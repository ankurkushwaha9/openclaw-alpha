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

---

## BUG-007 | YES/NO Loop Never Wired — Paper Trades Never Executed
Date: 2026-03-03
Status: FIXED
Severity: CRITICAL
Affected: paper_trading/paper_signal_bridge.py

SYMPTOM:
Proposals sent to Telegram with "Reply YES to execute paper trade"
User replies YES or NO but nothing happens.
Ledger never updates. Scorecard stays 0/10.

ROOT CAUSE:
paper_signal_bridge.py was sending Telegram message via send_telegram() then immediately exiting.
Nobody was listening for the YES/NO reply.
paper_propose.py (which polls for reply + executes trade) was NEVER called by the bridge.
The YES/NO instruction in the Telegram message was a dead end from day one.

FIX APPLIED:
Replaced send_telegram(proposal_msg) in bridge with subprocess call to paper_propose.py
paper_propose.py sends proposal + waits 30min for reply + executes trade if YES

FILES CHANGED:
- paper_trading/paper_signal_bridge.py

IMPACT:
Every paper trade proposed since Feb 23 was never executable by user.
All proposals expired silently. Scorecard stuck at 0/10.
2 weeks of paper trading data lost.

LESSON:
End-to-end testing is mandatory. Sending a message is not the same as completing a workflow.
Health check must verify the FULL loop, not just individual components.

---

## BUG-008 | Rojas Position Leaked From E2E Test Into Production Ledger
Date: 2026-03-03
Status: FIXED
Severity: HIGH
Affected: paper_trading/ledger.json

SYMPTOM:
Rojas Texas Abortion Case ($10) appeared in production ledger.json
Gamma API showed "price unavailable" for this position every daily report
Paper balance showed $48 instead of $58

ROOT CAUSE:
E2E test on Feb 24 was supposed to write to test_ledger.json (BOT_ENV=e2e_test)
But Rojas position leaked into production ledger.json
Market ID was hex format (0x3061...) — Gamma API requires numeric IDs
Position could never be priced or resolved

CASCADING EFFECT:
$10 dead position eating 15% exposure capacity permanently
Any new $10 trade pushed exposure to 42.1% > 40% cap
ALL new signals blocked by exposure guard
Paper trading system completely frozen for 7+ days

FIX APPLIED:
Removed Rojas from ledger.json
Refunded $10 virtual to cash: $48 -> $58

FILES CHANGED:
- paper_trading/ledger.json

LESSON:
E2E tests must use strict isolation. BOT_ENV check must be enforced at write time in paper_engine.py.
Any position with hex market ID should be rejected at entry — add validation.

---

## BUG-009 | Health Check Reported ALL SYSTEMS OK While Core Feature Was Broken
Date: 2026-03-03
Status: FIXED
Severity: HIGH
Affected: scripts/health_check.py

SYMPTOM:
Health check showed ALL SYSTEMS OK for 7+ days
Meanwhile YES/NO loop was completely broken (BUG-007)
And Rojas was freezing all new trades (BUG-008)

ROOT CAUSE:
Health check verified: crons active, no log errors, Telegram reachable, no spam
But NEVER verified: whether paper_propose.py was actually called by bridge
"No errors in bridge.log" is not the same as "system working correctly"
Bridge was running perfectly and logging cleanly — while core feature was silently broken

FIX APPLIED:
Added check_yes_no_loop() to health check
Verifies bridge.py contains subprocess call to paper_propose.py
Will now explicitly fail and alert if YES/NO loop breaks again

FILES CHANGED:
- scripts/health_check.py

LESSON:
Health checks must verify OUTCOMES not just ACTIVITY.
"Script ran without errors" != "Script did what it was supposed to do"
Every critical workflow path needs its own health check verification.

---

## BUG-010 | Health Check WORKSPACE Variable Not Defined
Date: 2026-03-04
Status: FIXED
Severity: MEDIUM
Affected: scripts/health_check.py

SYMPTOM:
Health check showing ISSUES DETECTED every 30 mins:
"Cannot verify YES/NO loop: name WORKSPACE is not defined"

ROOT CAUSE:
check_yes_no_loop() used WORKSPACE variable
But health_check.py defines its path variable as BASE not WORKSPACE
Copy-paste error when writing the new check function

FIX APPLIED:
Changed WORKSPACE -> BASE in check_yes_no_loop()

FILES CHANGED:
- scripts/health_check.py

LESSON:
When adding new functions to existing files always check what variable names
that file uses for common paths. Do not assume same names as other files.

---

## BUG-011 | Duplicate Guard Not Preventing Same Market Repeated Every 2 Hours
Date: 2026-03-04
Status: FIXED
Severity: HIGH
Affected: paper_trading/paper_signal_bridge.py

SYMPTOM:
Same market (PH Colombian election) proposed 5 times in one day
Every 2 hour scan sends same proposal to Telegram
Daily cap of 5 hit entirely by one market
All 5 slots wasted — no other signals can get through
User never gets YES/NO prompt for new/different signals

ROOT CAUSE:
guard_duplicate() checks pending_proposals.json for status="sent" within TTL (30 min)
After paper_propose.py runs (30min wait), proposal status stays "sent" in pending
But when paper_propose.py is called via subprocess:
  - It sends proposal and waits 30 min
  - After timeout/expire, bridge marks it "sent" and moves on
  - Next scan 2 hours later: proposal is now 2+ hours old > 30min TTL
  - guard_duplicate() sees it as "expired" — PASSES duplicate check
  - Same market proposed again

CASCADING EFFECT:
5/5 daily cap consumed by same market every day
No other signals reach user
Paper trading scorecard cannot progress
System appears to be working (proposals sent) but user gets spammed with same market

FIX NEEDED:
1. After paper_propose.py completes (YES/NO/timeout), update proposal status:
   - YES -> "approved"
   - NO -> "rejected"  
   - timeout -> "expired"
2. guard_duplicate() must block markets with status "expired" or "rejected" for 24 hours
   Not just "sent" within 30min TTL
3. Raise daily cap from 5 to 10 temporarily during testing phase

FILES TO CHANGE:
- paper_trading/paper_signal_bridge.py (guard_duplicate TTL + status update)
- BUGS.md (this entry)

FIX APPLIED (Mar 04 2026):
1. Added DUPLICATE_BLOCK_HOURS = 24 constant
2. guard_duplicate now blocks ANY proposal status (sent/expired/rejected/approved) for 24h
3. Proposal status now correctly recorded as approved/rejected/expired from paper_propose stdout
4. Daily cap raised from 5 to 10 for testing phase
5. Cleared stale PH Colombian market from pending_proposals.json
6. Logic unit tested - all 3 test cases pass

IMPACT OF FIX:
- Same market will never repeat within 24 hours regardless of outcome
- Daily cap slots reserved for different markets/signals
- User will see diverse signals in Telegram not same market repeated
- BUG-012 and BUG-013 resolved as part of same fix

---

## BUG-014 | n8n Consuming Telegram YES/NO Before paper_propose.py Can Read It
Date: 2026-03-04
Status: FIXED
Severity: CRITICAL
Affected: paper_trading/paper_propose.py

SYMPTOM:
User replies YES to paper trade proposal
Bot responds "Got it. What do you want me to do?" (n8n response)
paper_propose.py never receives the YES reply
Trade never executes. Proposal times out after 30 minutes.

ROOT CAUSE:
n8n is running as a persistent Node.js process on EC2 (PID ~1350)
n8n has a Telegram workflow that uses long-polling on the same bot token
Long-polling grabs ALL incoming messages first (higher priority than short-polling)
paper_propose.py uses short-polling (timeout=0) which arrives AFTER n8n consumes message
Result: paper_propose.py polls but finds no new messages - they were already consumed

ARCHITECTURAL FLAW MISSED IN REVIEW:
ps aux output showed n8n process clearly
Review focused on Python scripts only
Node.js process running n8n was not connected to Telegram conflict

WHY n8n CANNOT BE DISABLED:
n8n will be used for other workflows in future
Disabling it would break future integrations

FIX APPLIED:
Use unique prefix "PAPER YES" / "PAPER NO" for paper trade replies
n8n sees unrecognized command and ignores it (no workflow matches)
paper_propose.py explicitly listens for "PAPER YES" / "PAPER NO"
Both systems coexist on same Telegram bot without conflict

Changes:
1. poll_for_reply() now accepts: PAPER YES, PAPER Y, P YES (and plain YES as fallback)
2. poll_for_reply() now accepts: PAPER NO, PAPER N, P NO (and plain NO as fallback)
3. Proposal message updated: "Reply PAPER YES / PAPER NO"
4. Note added in message explaining prefix avoids bot conflicts

FILES CHANGED:
- paper_trading/paper_propose.py

HOW TO USE GOING FORWARD:
When you see a paper trade proposal in Telegram:
  Reply: PAPER YES  (to execute the trade)
  Reply: PAPER NO   (to skip)
Plain YES/NO still work as fallback but PAPER YES/NO is preferred.

LESSON:
Architectural review must include ALL running processes (ps aux) not just Python scripts.
Any persistent process that shares a Telegram token is a potential message consumer.
When two systems share the same communication channel, use unique namespacing.
Always ask: "What else is listening on this channel?"

---

## BUG-015 | Whale Signal Firing on NO-Side Buys (Wrong Direction Math)
Date: 2026-03-07
Status: FIXED v5.2
Severity: HIGH
Affected: scripts/whale_tracker.py

SYMPTOM:
Scottie Scheffler Masters signal fired at 60.5% divergence.
Whale price 0.81 vs market 0.205 — looked like massive YES signal.
Was a FALSE POSITIVE — no real edge existed.

ROOT CAUSE:
calculate_signal() used whale trade price directly as implied YES probability.
But the whale bought NO at 0.81 — meaning their implied YES = 1 - 0.81 = 0.19.
Market YES = 0.205. Real divergence = 1.5%. Well below 9% threshold.
Code treated any buy as a YES-side buy regardless of outcome field.

FIX APPLIED:
1. find_whale_trades() now stores outcome field ("Yes" or "No") in whale dict
2. calculate_signal() direction-adjusts: if outcome=="No", whale_prob = 1 - raw_price
3. Scan log now shows outcome= and whale_YES= fields for transparency
4. Telegram signal message shows "(NO-side buy, adj. YES=X.XXX)" when applicable

FILES CHANGED:
- scripts/whale_tracker.py (v5.1 → v5.2)

VERIFIED:
Unit tested both cases:
- NO buy at 0.81 → whale_YES=0.190, div=1.5%, tier=0 (correctly no signal)
- YES buy at 0.40 → whale_YES=0.400, div=20.0%, tier=1 (correctly fires)

LESSON:
Polymarket trades have an outcome field ("Yes"/"No") — always direction-adjust.
A whale buying NO at 0.81 is bearish on YES, not bullish.
Never treat raw trade price as implied YES probability without checking outcome.

---

## BUG-016 | Alpha Bot (n8n) Consuming PAPER YES Callback Before paper_propose.py
Date: 2026-03-07
Status: FIXED
Severity: CRITICAL
Affected: paper_trading/paper_propose.py

SYMPTOM:
User presses PAPER YES in Telegram.
Alpha Bot (n8n, PID ~1350) grabs the message via getUpdates (destructive read).
paper_propose.py polls same endpoint, finds nothing, proposal expires after 30 min.
Trade never executes despite user approving.
BUG-014 prefix fix ("PAPER YES") was insufficient — n8n still consumed the message
even if it didn't match a workflow, because getUpdates is destructive regardless.

ROOT CAUSE:
Both n8n AND paper_propose.py poll the same Telegram bot token via getUpdates.
getUpdates is a destructive read — whichever process polls first consumes the update.
n8n is a persistent Node.js process (PID ~1350), always running, faster than Python.
BUG-014's "PAPER YES" prefix only prevented n8n from ACTING on the message,
not from CONSUMING it. The race condition was still fully present.

FIX APPLIED:
Replaced text polling entirely with Telegram Inline Keyboard buttons.
Buttons fire callback_query — a completely different Telegram update type.
n8n only consumes message updates, never callback_query updates.
Race condition is architecturally impossible — different update types, no collision.

Additional hardening:
- answerCallbackQuery called immediately to dismiss loading spinner
- Keyboard removed after button press to prevent double-tap
- Text fallback (PAPER YES/NO) retained as belt-and-suspenders

HOW TO USE GOING FORWARD:
Paper trade proposals now arrive with two buttons: [YES - Execute] [NO - Skip]
Tap the button. That's it. No text reply needed.
Text "PAPER YES" / "PAPER NO" still works as fallback.

FILES CHANGED:
- paper_trading/paper_propose.py

CONFIRMED:
Live test passed — callback_query received: TEST_YES_1772897839
Alpha Bot architecturally cannot interfere with button responses.

LESSON:
When two systems share a Telegram bot token, text polling (getUpdates) is ALWAYS
a shared destructive resource — prefixes don't help.
Inline keyboard buttons use callback_query — a separate, non-competing update stream.
For any approval flow where another process shares the bot token, use inline keyboards.


---

## BUG-017 — Shadow Monitor Scoring Metadata Wrapper Instead of Real Messages
STATUS: FIXED (2026-03-08, commit cc252f4)

DISCOVERED BY: Main Claude session QA review after Day 2 session completed.

ROOT CAUSE:
OpenClaw prepends every user message with a metadata header before writing to session .jsonl:
  "Conversation info (untrusted metadata): ```json { "message_id": "...", "sender": ... } ```
  [actual user message here]"

shadow_monitor.py was passing the FULL string (wrapper + message) to score_complexity()
and has_trading_keyword(). This meant the scorer was evaluating "Conversation info..."
boilerplate every time, not the real Telegram message. Every non-trading message scored
exactly 5 (simple tier) regardless of actual content -- silent accuracy killer.

EVIDENCE:
All routing.log entries showed msg_snippet starting with "Conversation info (untrusted metadata)"
and score=5 uniformly. After fix, real messages appear: 'Hello', 'PAPER YES', 'whale bought YES'.

FIX APPLIED:
Added strip_metadata_wrapper() function to scripts/shadow_monitor.py.
Function detects the "Conversation info" prefix, finds the closing ``` of the JSON block,
and returns only the text after it -- the actual user message.
Wired into watch_session() at the point where pending_user_text is assigned.

FILES CHANGED:
- scripts/shadow_monitor.py (added strip_metadata_wrapper, wired at line ~253)

LESSON:
OpenClaw always wraps messages with metadata. Any component that reads session .jsonl
files and needs to process user content must strip this wrapper first.

---

## BUG-018 — Underscore Callback IDs Bypass Trading Keyword Detection
STATUS: FIXED (2026-03-08, commit cc252f4)

DISCOVERED BY: Main Claude session QA review -- visible in shadow monitor logs after BUG-017 fix.

ROOT CAUSE:
Telegram inline keyboard callbacks use underscore-joined IDs: PAPER_YES_1772897697, TEST_YES_123.
has_trading_keyword() used re.findall(r'\b\w+\b', text) for tokenization.
In regex, underscore (_) is a word character (\w), so "PAPER_YES" has NO word boundary
between PAPER and YES. The token extracted is "PAPER_YES" as one unit, which does not
match the keyword set entry "paper" or "yes".
Result: PAPER_YES_1772897697 scored as SIMPLE tier, not TRADING -- wrong routing.

EVIDENCE:
After BUG-017 fix, shadow log showed:
  SIMPLE | msg='PAPER_YES_1772897697'  <-- wrong, should be TRADING
  SIMPLE | msg='TEST_YES_1772897614'   <-- wrong, should be TRADING

After BUG-018 fix:
  MEDIUM [TRADING_GUARDRAIL] | msg='PAPER_YES_1772897697'  <-- correct

FIX APPLIED:
In has_trading_keyword() in scripts/shadow_monitor.py:
  Before: words = re.findall(r'\b\w+\b', text_lower)
  After:  normalized = text_lower.replace('_', ' ')
          words = re.findall(r'\b[a-z]+\b', normalized)
Underscores become spaces before tokenizing, so PAPER_YES_123 splits into
["paper", "yes", "123"] and both "paper" and "yes" match the keyword set.

FILES CHANGED:
- scripts/shadow_monitor.py (has_trading_keyword function)

LESSON:
Any keyword detection that may encounter underscore-joined identifiers (callback IDs,
snake_case variable names, etc.) must normalize underscores to spaces before tokenizing.
Word-boundary regex alone is not sufficient.


## BUG-019 - OpenClaw Strict Schema Rejects Smart Router Config Keys
- Date: 2026-03-09
- Status: RESOLVED
- Component: smart-router/openclaw-integration.js + openclaw.json
- Symptom: Bot crashed on startup after install script ran. Error:
    "Config invalid: agents.defaults.model: Unrecognized keys: routing, thresholds
     <root>: Unrecognized key: smartRouter"
- Root Cause: openclaw-integration.js tried to inject 3 unknown keys into openclaw.json.
  OpenClaw has a strict Zod schema validator that rejects ANY unknown key at startup.
- Failed Fix: openclaw doctor --fix did NOT remove the injected keys.
  openclaw.json.backup was already overwritten with broken config.
- Resolution: Redesigned entire Day 3 approach.
  Instead of modifying openclaw.json config, deployed proxy-server.js as a local
  OpenAI-compatible HTTP server on port 8081. OpenClaw uses a standard "smart-router"
  provider block (valid schema) pointing to http://127.0.0.1:8081/v1.
  Proxy intercepts requests, scores complexity, routes to Gemma/Kimi/Sonnet.
  Zero unknown keys. Zero schema violations.
- Files Changed:
  smart-router/proxy-server.js (NEW - 341 lines)
  openclaw.json (smart-router provider block added -- valid schema)
  ~/.config/systemd/user/smart-router-proxy.service (NEW - auto-start service)
- WARNING: openclaw.json.backup contains the broken smart-router config -- DO NOT USE TO RESTORE

## BUG-020 - Smart Router Proxy: Gemma Latency Causes OpenClaw Timeout
- Date: 2026-03-09
- Status: OPEN - Smart Router disabled, reverted to Kimi direct
- Component: smart-router/proxy-server.js + Gemma 2B (Ollama)
- Symptom: Bot stops responding to Telegram messages after Smart Router activated.
  Messages show as delivered (double tick) but bot never replies.
- Root Cause Analysis:
  1. "Hello" (score=0) routes to Gemma 2B via Ollama on port 11434
  2. Gemma 2B is cold/slow -- first call takes 35-40 seconds
  3. proxy-server.js originally had 30s Gemma timeout -- whole proxy hangs
  4. Even after reducing to 5s timeout, Gemma fails -> falls to Kimi
  5. Kimi via NVIDIA NIM takes additional 10-15s after Gemma failure
  6. Total latency: 15-40 seconds per message
  7. OpenClaw appears to have its own internal timeout shorter than this
  8. OpenClaw drops the response -> bot appears silent
- What Was Tried:
  * Reduced Gemma timeout from 30s to 5s (partial fix -- still total 15s)
  * Disabled Gemma routing entirely (all -> Kimi) -- still 15s too slow
- Current State: openclaw.json reverted to nvidia-nim/moonshotai/kimi-k2.5 direct
  Smart Router service still running but not being used
- Fix Options (in order of preference):
  Option A: Pre-warm Gemma on startup -- send a dummy request to Ollama when
            proxy-server.js starts so first real request is fast (<2s)
  Option B: Increase OpenClaw timeout -- investigate openclaw.json timeout settings
            (compaction.reserveTokensFloor exists, check if request timeout configurable)
  Option C: Remove Gemma entirely from routing -- use only Kimi (free) and Sonnet (paid)
            Simpler 2-tier routing: score<70 -> Kimi, score>=70 -> Sonnet
  Option D: Use Gemma only for truly non-interactive tasks (cron jobs, background scans)
            Never route real-time Telegram messages to Gemma
- Recommended Fix: Option A (pre-warm) + Option D (no Gemma for Telegram)
  Pre-warm on startup: add to proxy-server.js startup sequence
  Gemma for background only: heartbeat, cron scan summaries -- never Telegram replies
- Files to Change:
  smart-router/proxy-server.js -- add Gemma pre-warm on startup + routing rule change
  openclaw.json -- re-enable smart-router/smart-router as primary after fix confirmed

---

## BUG-021 — whale_tracker.py missing /events endpoint — Geopolitics markets invisible

- Status: OPEN
- Priority: HIGH
- Discovered: 2026-03-09 (Session: Impact analysis + Polymarket screenshot comparison)
- Affected File: scripts/whale_tracker.py (v5.2)

- Symptom:
  Whale tracker scans 500 markets per run but misses ALL major Iran/geopolitics markets.
  Polymarket screenshot confirmed $26M+ volume markets (Iranian regime fall, US x Iran
  ceasefire, Hormuz) are completely absent from scan output.

- Root Cause:
  whale_tracker.py fetches markets exclusively from:
    GET https://gamma-api.polymarket.com/markets
  Polymarket's largest geopolitics markets are structured as EVENTS with multiple dated
  outcomes (e.g., "US x Iran ceasefire by March 15?", "...by March 31?", "...by June 30?")
  and are ONLY accessible via:
    GET https://gamma-api.polymarket.com/events
  The /events endpoint returns nested structure: event.markets[] array.
  These sub-markets NEVER appear in the flat /markets endpoint response.

- Confirmed Missing Markets (from screenshot, all invisible to tracker):
  * Will the Iranian regime fall by March 31? -- $26.6M vol, $938K liq, 21d
  * Will Iran close the Strait of Hormuz by March 31? -- $21.8M vol, $581K liq, 22d
  * US x Iran ceasefire by March 15? -- $4.7M vol, $184K liq, ~6d
  * US x Iran ceasefire by March 31? -- $3.9M vol, $143K liq, ~22d
  * Iranian regime fall by June 30? -- $11.9M vol, $709K liq, 112d
  * Iranian regime fall by April 30? -- $1.5M vol, $397K liq, 51d

- Schema Verification (2026-03-09):
  Event sub-market fields are IDENTICAL to /markets fields. Pipeline-compatible:
  conditionId, endDate, endDateIso, outcomePrices, liquidity, liquidityNum,
  negRisk, clobTokenIds, acceptingOrders, active, closed -- all present, same format.

- Trade History Verification (2026-03-09):
  DATA_API /trades endpoint confirmed working for sub-markets.
  Fields available for Phase 2 accumulation clustering:
    proxyWallet -- wallet address (clustering key)
    timestamp   -- unix epoch integer (window math ready)
    outcome     -- "Yes" / "No" (direction consistency check)
    side        -- "BUY" / "SELL"
    size        -- USDC amount directly (NOT token units -- confirmed)
    price       -- float 0-1
    conditionId -- market identifier
  Wallet clustering observed in real data:
    0x3f049e... -- 30 trades, 48min span, $1,972 total, all YES (classic accumulation)
    0x48f979... -- 3 trades, 1.8min span, $932 total, all YES

- 3-LLM Brainstorm (Claude + Gemini + ChatGPT) Consensus:
  Architecture: Option B -- parallel fetch both endpoints, merge by conditionId
  Priority rules:
    /markets wins on price/liquidity if conditionId in both (closer to CLOB truth)
    Use max(events_liq, markets_liq) for liquidity field
  Guards to add:
    negRisk=True      -> skip (Gemini)
    acceptingOrders=False -> skip / phantom market (ChatGPT)
    endDate=null      -> days=999, Stage 4 Open Horizon, raise min_liq to 25k (ChatGPT)
  Two additional upgrades identified (separate phases):
    Phase 2: Whale accumulation clustering (30min window, 3+ trades, $900 min)
    Phase 3: Liquidity shock detection (persistent state between cron runs)

- Fix Plan (3 phases):
  PHASE 1 (events fix -- build next session):
    1. Add fetch_events() function: GET /events paginated, flatten markets[]
    2. Merge with existing fetch_markets() by conditionId
    3. Add negRisk + acceptingOrders + endDate=null guards
    4. Attach parent_event_title to each sub-market for context
    5. All else unchanged (signal calc, thresholds, Telegram format)

  PHASE 2 (accumulation clustering -- after Phase 1 stable):
    1. Group trades by (proxyWallet, conditionId, outcome) within 30min window
    2. Signal if total >= $900 AND trades >= 3 AND direction consistent
    3. New Telegram label: "Whale Accumulation" vs "Whale Single Trade"

  PHASE 3 (liquidity shock -- after Phase 2 stable):
    1. New file: paper_trading/liquidity_history.json (persists between cron runs)
    2. Read on startup, compare current vs stored, write updated each scan
    3. Shock = -20%+ liquidity within last scan window
    4. Combined signal: shock + cluster + divergence = EXTREME tier

- Related:
  STAGE3_TRIGGER fix (2026-03-09, commit 44f0d19) -- lowers stage escalation threshold
  but does NOT fix the root cause (still only scanning /markets endpoint)
