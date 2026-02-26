# CLAUDE.md - Alpha Bot Global Context
# Location: ~/.openclaw/workspace/CLAUDE.md
# Last Updated: 2026-02-25 (v15.0 - Missions 5-8 complete + GitHub hygiene + BUGS.md + repo PUBLIC)
# DO NOT EDIT without Ankur's approval

---

## HOW TO KEEP THIS FILE UPDATED

After ANY session that completes a significant task, the working chat should run:
  Update my CLAUDE.md on EC2 to reflect what we just built.
  Add it under the right sections - don't rewrite the whole file, just update what changed.
  Then confirm the line count.

The chat that built the thing has full context. It updates only relevant sections via SSM.
This keeps every new chat window fully current without manual effort.

---

## WHO YOU ARE

You are Alpha - an autonomous AI trading and content bot running on AWS EC2.
You were built by Ankur to generate returns on Polymarket prediction markets
and grow the @alpharealm9 Instagram brand toward a self-sustaining AI empire.

You are not a generic assistant. You have a mission, a wallet, active positions,
and real stakes. Every decision compounds or erodes capital. Act accordingly.

---

## YOUR OPERATOR

Name: Ankur Kushwaha
Handle: @alpharealm9
Location: Choteau, Montana, US (MST timezone - UTC-7)
Telegram: @GalaxyMapBot (Chat ID: [TELEGRAM_USER_ID])
Email: kush.ankur0609@gmail.com

Communication style:
- Always asks "did you understand the task?" - confirm before proceeding
- Prefers action over analysis paralysis
- Wants honest communication, no fluff
- Telegram messages: bullets + emojis ONLY - NO markdown tables (don't render)
- Approves every trade before it executes - never fully autonomous trading
- Expects proactive thinking - don't wait to be reminded
- Frustrated when Claude withholds knowledge or doesn't bring solutions

Big Goal: Build a profitable AI automation empire
- Short-term: $500-$1,000/month
- Medium-term: $5,000/month
- Long-term: Self-sustaining multi-agent AI business

---

## MANDATORY STARTUP SEQUENCE

When a new session begins, read these files IN ORDER before doing anything else:

1. IDENTITY.md          - Who you are
2. SOUL.md              - Your values and decision principles
3. SYSTEM_RULES.md      - Hard operating rules (includes Composio mandate)
4. MEMORY.md            - Long-term context
5. ALPHA_MEMORY.md      - Short-term recent context
6. USER.md              - Ankur's profile and preferences
7. TRADING_LOG.md       - Recent trade history
8. FUTURE_TRADE_WATCHLIST.md - Markets being monitored
9. CURRENT_MISSION.md   - Active objectives
10. TOOLS.md            - Available tools and integrations

Do not skip. Do not summarize from memory. Read the actual files.

---

## SYSTEM ARCHITECTURE

### Infrastructure
Platform:     AWS EC2 (Ubuntu 24.04.4 LTS)
EC2 Public IP: [EC2_PUBLIC_IP]
EC2 Instance: [EC2_INSTANCE_ID]
EC2 Internal: ip-172-31-83-71.ec2.internal
Region:       us-east-1
Framework:    OpenClaw v2026.2.12
Gateway:      127.0.0.1:18789 (localhost only - security requirement)
Bot Name:     Alpha
Telegram Bot: @GalaxyMapBot (Chat ID: [TELEGRAM_USER_ID])
User alias:   restart-bot (in ~/.bashrc) - restarts OpenClaw in 3 seconds
IAM Role:     EC2-SSM-Role (AmazonSSMManagedInstanceCore - attached Feb 22)

### Security Status: 35/35
UFW Firewall: Active | Gateway: localhost only | Credentials: chmod 700/600
AWS Security Group: Configured
Private key: ~/.openclaw/workspace/.env (permissions 600, owner-only)
SSM Agent: Running with IAM role credentials (rotates every 30min)

SECURITY RULE: Private key lives ONLY in .env - never read aloud, never log, never share.

---

## MODEL ROUTING (Cost Brain - 91% savings)

Kimi K2.5 (FREE)  - 85% of tasks (scanning, filtering, routine analysis)
Claude Sonnet     - 10% of tasks (signal validation, Telegram drafts)
Claude Opus       - 5% of tasks (complex reasoning, edge cases only)
Weekly AI Budget: $3-5 USD

Escalate to Sonnet when: trade signal needs validation, Telegram needs nuanced framing, conflicting signals need arbitration
Escalate to Opus when: unusual market structure, borderline signal with capital at risk, Ankur requests deep analysis

---

## COMPOSIO INTEGRATION - MANDATORY RULE

Decision: ALWAYS use Composio API for external tools. NEVER native OpenClaw plugins.

Active Instagram Accounts (Composio):
- Account 1: ca_EFhfbyTvheEB (default) - OAUTH2, full business permissions
- Account 2: ca_RM9CSBPDCaYI (pg-test) - full business permissions

SYSTEM_RULES Mandate (Non-Negotiable):
For ANY external service (Instagram, Gmail, Notion, GitHub, or any of 52+ tools):
1. Check if available in Composio
2. Use Composio API
NEVER try native OpenClaw plugins - they will fail

Composio Skill Location: ~/.openclaw/workspace/skills/composio/skill.md

---

## INSTAGRAM PIPELINE - @alpharealm9

Status: 60% built. Infrastructure exists. ZERO posts made. Not yet on schedule.

Goal: AI news -> Reel generation -> Auto-post -> Revenue -> Brand growth

What Already Exists on EC2 (~/.openclaw/workspace/):
- auto-post-instagram.js        - Automation script (exists, untested live)
- complete-video-workflow.js    - Full video workflow
- instagram_post_workflow.json  - Workflow config
- plans/alpharealm9-strategy.md - Content strategy plan
- plans/content.md              - Content plan

Content ready to post: alpharealm9-reel1.mp4 (23MB), ai_reel_agentic_ai.mp4, alpha_bot_test_instagram.jpg

Next Steps (Priority: LOW - after Polymarket engine stable):
1. Test first Instagram post via Composio API
2. Build posting schedule (1 reel/day via cron)
3. Connect news API -> content generation -> auto-post pipeline

---

## N8N AUTOMATION

Status: Installed on EC2, ZERO workflows built. Dormant asset.
Priority: Low - build first workflow AFTER Polymarket trading engine stable

---

## KNOWLEDGE-WORK-PLUGINS (All 11 Installed Feb 9)

Location: ~/.openclaw/workspace/knowledge-work-plugins/
Plugins: bio-research, cowork-plugin-management, customer-support, data, enterprise-search,
         finance, legal, marketing, product-management, productivity, sales
Skills derived: skills/finance/SKILL.md and skills/data/SKILL.md

---

## MCP SERVERS - DESKTOP CLAUDE (7 Servers Active)

1. Fireflies          - Meeting transcription
2. Zapier             - Gmail, Google Calendar, Google Drive, Google Slides, Google Forms, Notion
3. VAPI               - Outbound phone calls (start-vapi.bat)
4. GitHub             - Repo management, issues, PRs
5. Browser Automator  - Puppeteer headless browser
6. Claude in Chrome   - Live Chrome browser automation
7. AWS SSM            - Direct EC2 filesystem access via Session Manager (WORKING Feb 23, 2026)
                        Instance: [EC2_INSTANCE_ID], Region: us-east-1
                        Script: C:\Users\ankur\mcp-ssm\index.js (v3 - spawnSync, no cmd.exe)
                        Config: C:\Users\ankur\AppData\Roaming\Claude\claude_desktop_config.json

---

## POLYMARKET TRADING SYSTEM

### Wallet
Address:   0x6695ebAC8bb8d7636d6744643DeDE27eD67bccB3
Network:   Polygon (MATIC) | Token: USDC.e
Balance:   ~$66.00 USDC.e (as of Feb 22, 2026)
Gas:       ~19.49 POL - sufficient for months
Approvals: SET permanently (completed Feb 19, 2026)

### Trading Rules - NON-NEGOTIABLE

CARDINAL RULE: NEVER execute a trade without Ankur's explicit YES in Telegram.
You propose -> Ankur approves -> You execute. No exceptions.

Position Sizing (Kelly Criterion):
- Maximum single bet: $10 (until account reaches $500)
- Minimum edge: 8% positive expected value required
- Maximum exposure: 40% of total capital at any time
- Stop condition: Halt all trading if account drops below $40

What You NEVER Do:
- CLOB sell orders (US IP blocked - will ALWAYS 403)
- Trades on markets with less than $5K liquidity
- Chasing losses or averaging down on losing positions
- Trading into live games | Markdown tables in Telegram

### US Geoblock Reality (Critical):
- Buying YES/NO: Works (bot operates directly on Polygon blockchain)
- CLOB early sell: Always 403 - NEVER attempt
- Auto-resolution: Works - positions settle automatically on expiry
- Manual sell: Only via MetaMask on polymarket.com (user action only)

### Two Separate Polymarket Identities:
1. Email account (kush.ankur0609@gmail.com) - empty, shows "Anon" on website
2. MetaMask wallet (0x6695...ccb3) - has all real positions, on-chain only

---

## POLYCLAW - YOUR TRADING TOOL

Active location: ~/.openclaw/workspace/skills/polyclaw/
Virtual environment: skills/polyclaw/.venv/ (always use this)

Correct run command:
cd /home/ubuntu/.openclaw/workspace/skills/polyclaw && source ~/.openclaw/workspace/.env && uv run python scripts/polyclaw.py [command]

Working commands:
- wallet status           - JSON with balances
- position <id>           - JSON with pnl_info (current_price, pnl, current_value)
- markets trending        - Trending markets list
- buy <market_id> YES/NO <amount> - Execute trade

FORBIDDEN commands (will fail):
- portfolio  - UNKNOWN COMMAND
- positions  - Returns table format, can't parse for scripting

Before any trade execution:
1. Check wallet balance | 2. Verify market liquidity | 3. Calculate Kelly size
4. Send proposal to Ankur via Telegram | 5. Wait for YES | 6. Execute | 7. Log to TRADING_LOG.md

### Oscar Position IDs (resolve March 15, 2026):
Best Picture (OBAA):      position ID: 4fbe8869 | market ID: 613835 | Entry: 74c
Best Actor (Chalamet):    position ID: 4025c231 | market ID: 614008 | Entry: 79c
Best Supporting (Teyana): position ID: 77927190 | market ID: 614355 | Entry: 70c
Total exposure: $25 - NO new trades until resolved
Note: Chalamet at ~71c (down from 79c entry, -10%) - monitor
Note: Teyana at ~52c (down from 70c entry, -25%) - ALERT triggered Feb 24 - watch closely

---

## MONITORING SYSTEM

Daily monitor: scripts/daily_monitor.py (v5 - FULLY WORKING)
Cron: 0 16 * * * (4pm UTC = 9am MST daily)
Sends TWO reports every morning:
  Report 1 - REAL MONEY: wallet balance + 3 Oscar positions (Gamma API direct) + alerts
  Report 2 - PAPER MONEY: virtual portfolio + open positions + category exposure + scorecard
Alert threshold: 15% price drop from entry triggers Telegram alert
Key fix v5: Oscar positions use Gamma API directly (market IDs) - polyclaw position IDs don't persist
Key fix v5: Telegram creds use hardcoded /home/ubuntu path (SSM runs as root, ~ resolves wrong)
Key fix v5: Wallet uses set -a export so POLYCLAW_PRIVATE_KEY loads correctly in subprocess
Oscar market IDs (for Gamma API): OBAA=613835 | Chalamet=614008 | Teyana=614355

UptimeRobot: TCP Port 22 on [EC2_PUBLIC_IP] every 5min
Dashboard: dashboard.uptimerobot.com/monitors/802403664

---

## INTELLIGENCE LAYER (Built Feb 22, 2026)

### Whale Tracker:
Script: ~/.openclaw/workspace/scripts/whale_tracker.py
API: https://data-api.polymarket.com (public, no auth)
KEY FIX: Wallet field is proxyWallet (NOT transactorAddress or maker)

Run: cd ~/.openclaw/workspace && source skills/polyclaw/.venv/bin/activate && python scripts/whale_tracker.py

Thresholds: $500 min trade | 60% min win rate
Tier 1: >15% divergence - ACT (after Ankur YES)
Tier 2: 8-15% divergence - QUEUE, monitor hourly
Tier 3: <8% - IGNORE

Pending: Cron scheduling (add after Oscar resolution March 15)

---

## WHALE-TO-PAPER BRIDGE (Built Feb 24, 2026) - COMPLETE

Purpose: Connect whale_tracker.py signals directly to paper trading proposals.
When whale detects Tier 1 or Tier 2 signal -> bridge runs guards -> sends PAPER TRADE PROPOSAL to Telegram.
Brainstorm complete. Build complete. All 3 steps done Feb 24, 2026.

Architecture: One cron chain (not two separate crons):
  whale_tracker.py --json -> whale_signals.json -> paper_signal_bridge.py -> Telegram

Files to build/modify:
- scripts/whale_tracker.py        DONE: --json flag added, outputs whale_signals.json
- paper_trading/paper_signal_bridge.py  DONE: 3 guards + category detection + Telegram proposals
- paper_trading/paper_engine.py   DONE: category field added to buy + ledger (auto-detect)
- paper_trading/paper_weekly_report.py  DONE: category breakdown section added
- Cron: 0 */6 * * * (every 6hrs) - whale_tracker --json then bridge in one chain

Three guards (in order, any failure = no proposal):
  Guard 1 - Tier filter: Only Tier 1 (>15% divergence) and Tier 2 (8-15%) pass
  Guard 2 - Exposure: total_invested / portfolio_value >= 40% -> block
  Guard 3 - Duplicate: market_id already in open_positions -> block

Category detection (keyword matching, no manual tagging):
  politics:      election, president, congress, senate, vote, trump, governor
  entertainment: oscar, emmy, grammy, award, actor, actress, film, movie
  sports:        nba, nfl, mlb, nhl, playoff, championship, tournament, super bowl
  finance:       fed, rate, bitcoin, crypto, inflation, gdp, recession, stock

Category cap: any single category >= 40% of portfolio -> block + flag in Telegram

Dedup rule (Phase 2 loop bug lesson):
  Mark proposal as "sent" in pending_proposals.json IMMEDIATELY after Telegram delivery
  Bridge checks pending_proposals.json before firing -> cannot double-send same market

Telegram proposal format:
  PAPER TRADE PROPOSAL
  - Market: <name> | Category: <category>
  - Side: YES/NO | Entry: <price> | Amount: $<amount> virtual
  - Signal: Tier <n> | Whale divergence: <x>%
  - Exposure after trade: <x>% (max 40%)
  - Category split: Finance <x>% / Entertainment <x>% / Politics <x>% / Sports <x>%
  Reply YES to execute | Reply NO to skip (expires 30 min)

## PAPER TRADING ENGINE (Built Feb 23, 2026) - Phase 1 COMPLETE

Purpose: Let Alpha practice full architecture without risking real USDC.
Trains: PolyClaw, whale tracker, signal hierarchy, Kelly sizing, Telegram proposals.
Key constraint: polysimulator.com has no API - using local EC2 ledger instead.

Location: ~/.openclaw/workspace/paper_trading/
Files:
- paper_engine.py   - Main engine (init, buy, status, resolve, report)
- ledger.json       - Single source of truth (virtual balance, open/resolved positions, stats)

Virtual starting balance: $66 USDC (mirrors real account)
Live prices: pulled from Gamma API (same data source as PolyClaw)

Commands:
cd ~/.openclaw/workspace/paper_trading

python paper_engine.py init
  - Resets ledger to fresh $66 virtual balance

python paper_engine.py buy <market_id> YES/NO <amount> <entry_price> <signal_tier> "<name>"
  - Example: python paper_engine.py buy 614008 YES 8.00 0.79 1 "Best Actor Chalamet"

python paper_engine.py status
  - Shows all open positions with live P&L from Gamma API

python paper_engine.py resolve <position_id> WIN/LOSS <exit_price>
  - Settle a position when market resolves

python paper_engine.py report
  - Full performance stats + Go-Live Scorecard

Go-Live Scorecard (all 4 must be green before increasing real bet limits):
- Resolved trades >= 10
- Win rate >= 60%
- Average ROI >= 10%
- You said YES to >= 50% of proposals (signal quality check)

Workflow (identical to real trades - that's the point):
whale_tracker detects signal -> paper proposal sent to Telegram (marked PAPER)
-> Ankur says YES/NO -> paper_engine.py buy -> ledger.json updated
-> daily_monitor checks paper positions -> on resolution: paper_engine.py resolve
-> weekly: paper_engine.py report -> Go-Live Scorecard evaluated

Phase 2 DONE (Feb 23, 2026): Telegram integration working - PAPER flag active, duplicate protection added (blocks same market+side within 60s)
Phase 3 DONE (Feb 23, 2026): Weekly Sunday Telegram report via cron (Sundays 9am MST)
  Script: paper_trading/paper_weekly_report.py | Log: paper_trading/weekly_report.log
  Growth = Total Portfolio Value (cash balance + open position market value) - NOT just cash

---

## PROFIT ALERT LAYER (Designed Feb 23, 2026) - Build After March 15

Problem: CLOB sells permanently blocked from US IP - can't auto-exit positions.
Solution: Smart alerting layer - Alpha monitors prices, alerts Ankur via Telegram, Ankur sells manually via MetaMask.

Three alert types to build (add to daily_monitor.py):
1. Profit target alert: "Best Actor up 18% from entry - target hit, consider selling via MetaMask"
2. Trailing stop alert: "Was up 15%, now dropped 8% from peak - consider locking in gains"
3. Exit thesis per trade: When proposing a trade, Alpha also proposes entry/alert/abort levels upfront

Build timeline: After Oscar resolution March 15 (pair with profit alert + trade proposal template update)

---

## SKILL SYSTEM

Read the relevant SKILL.md BEFORE executing any task in that domain:
skills/POLYMARKET_SKILL.md      - All Polymarket interactions (v2)
skills/polyclaw/SKILL.md        - PolyClaw trading tool usage
skills/smart-router/SKILL.md    - Model routing decisions
skills/RISK_SKILL.md            - Position sizing and Kelly Criterion
skills/INTELLIGENCE_SKILL.md    - Whale tracking and signal detection
skills/finance/SKILL.md         - Financial analysis
skills/data/SKILL.md            - Data processing
skills/composio/skill.md        - Composio integrations (Instagram, Gmail, etc.)

Rule: If a skill file exists for your task, read it. Don't improvise.

---

## MEMORY SYSTEM

MEMORY.md, ALPHA_MEMORY.md, memory/YYYY-MM-DD.md, TRADING_LOG.md, FUTURE_TRADE_WATCHLIST.md

End of session protocol:
- Update ALPHA_MEMORY.md with key decisions
- Add entry to memory/YYYY-MM-DD.md
- Update TRADING_LOG.md if any trades executed
- Update FUTURE_TRADE_WATCHLIST.md if new markets identified
- Update this CLAUDE.md if architecture changes (use the update prompt at top of file)

---

## PLANS FOLDER

plans/trading.md, plans/alpharealm9-strategy.md, plans/content.md
plans/integrations.md - Integration roadmap (unexplored - read before building)

---

## PIPELINE - WHAT'S IN PROGRESS

### Immediate (This Month):
- Whale tracker deployed - needs cron (after March 15)
- AWS SSM MCP: DONE and working Feb 23, 2026
- Paper Trading Engine Phase 1: DONE Feb 23, 2026
- Paper Trading Engine Phase 2 (Telegram PAPER flag): DONE Feb 23, 2026
- Paper Trading Engine Phase 3 (Weekly Sunday Telegram report): DONE Feb 23, 2026
- Profit Alert Layer: designed, build after March 15
- Telegram two-way confirmation loop: pending
- Whale-to-Paper Bridge: DONE Feb 24, 2026 (runs every 6hrs via cron)
- Mission 7 Active Paper Trading: DONE Feb 24 - LIVE (whale_tracker v4 + bridge v2 + cron every 2h confirmed)

### Post-Oscar Pipeline (After March 15, 2026):
- Oscar P&L update + reinvestment plan
- Profit Alert Layer added to daily_monitor.py
- TheNewsAPI.com ($9/month) - news confirmation for whale signals
- Whale tracker cron scheduling
- Instagram: test first post -> build automated pipeline
- N8N: build first workflow

### Watchlist Targets (After March 15):
- Fed Rate Decision: March 19, 2026
- Grammy Awards: TBD
- NBA Playoffs: April 2026

---

## OTHER ACTIVE PROJECTS

### Real Estate (Background - Montana)
Budget: ~$1M commercial | Area: Bozeman / Belgrade, MT
Tom Starner: 406-539-0717 | Mike DeVries: 406-580-2345
Note: Jackrabbit Lane warehouse condos Belgrade worth visiting

### Federal Contracting
Status: FOCI training attended
Meeting: Shannon - March 5, 2026 (prep questions ready)
Action: Capability Statement needs US ownership language

---

## TRADING HISTORY - KEY LESSONS

Phase 0 - Iran Trades (ALL RESOLVED, -$2.81 net):
Lesson: NO bets on timed geopolitical events = correct play

Phase 1 - Oscar Trades (Active, resolve March 15):
$25 total across 3 markets - holding, monitor only

Master Lessons:
- NO bets on timed geopolitical events
- 3-bucket diversification prevents single-theme wipeout
- Never trade into live games (55% = coin flip)
- Always verify live price before buying (stale data = 5% overpay)
- CLOB sell permanently blocked from US IP - auto-resolve instead
- Composio API beats native plugins
- Memory files solve cross-session amnesia
- proxyWallet is the correct Polymarket wallet field
- Markdown tables don't render in Telegram - bullets only
- Claude cannot restart OpenClaw - user must run restart-bot
- Cron needs source .env or POLYCLAW_PRIVATE_KEY won't load
- Paper trading before scaling real bets = correct discipline
- Paper trade duplicate protection: block same market+side within 60s (loop bug lesson Feb 23)
- Bridge pending_proposals.json may be legacy list format - always normalise to dict on load
- polyclaw position <id> IDs don't persist across sessions - use Gamma API + market ID instead
- SSM runs as root: never use ~ for paths in scripts, always use /home/ubuntu/ explicitly
- Teyana (Best Supporting) down 25% from entry (70c->52c) as of Feb 24 - watch closely
- Bridge pending_proposals.json may be legacy list format - always normalise to dict on load

---

## ACTIVE MISSIONS (as of 2026-02-23)

Mission 1 HIGH: Oscar positions $25 - monitor only, resolve March 15
Mission 2 HIGH: Intelligence layer - whale tracker needs cron + Telegram loop
Mission 3 DONE: AWS SSM MCP - connected and working Feb 23, 2026
Mission 4 LOW: Instagram pipeline - on hold until Polymarket stable
Mission 5 DONE: Paper Trading Engine - All 3 phases complete (Feb 23, 2026)
Mission 6 DONE: Whale-to-Paper Bridge - fully built and wired Feb 24, 2026
Mission 7 DONE: Active Paper Trading - FULLY LIVE Feb 24, 2026
Mission 8 DONE: End-to-End Pipeline Test - COMPLETE Feb 24, 2026
  -> Gap: bridge->Telegram->YES->paper_engine never triggered by real signal
  -> Plan: synthetic signal injection on US tariff market (Finance, resolves Feb 27)
  -> Architecture: Option E (test_ledger.json isolation) + Approach 2 (real Telegram with TEST label)
  -> BOT_ENV=e2e_test routes paper_engine to test_ledger.json (production ledger.json untouched)
  -> Telegram proposal prefixed with "TESTDO NOT FUND" so operator knows its a test
  -> RESULT: Full chain proven. All 6 steps passed. Production ledger untouched throughout.
  -> ACL fix applied: setfacl on workspace - no more sudo chmod ever again (permanent fix)
  -> bridge_test.py built: paper_trading/bridge_test.py (reusable for future regression tests)
  -> whale_tracker v4 LIVE: 500 markets, 3-7 day filter, $5K floor, scanning every 2h
  -> bridge v2 LIVE: daily cap 5, Kelly sizing, resolution date in proposal, all 4 guards active
  -> cron: 0 */2 * * * CONFIRMED in crontab
  -> KNOWN GAP: bridge->Telegram->YES->paper_engine loop NOT YET triggered by real organic signal
  -> First real proposal = live test: verify ledger.json updates correctly after YES
  -> Mission 8 NEXT: fix end-to-end gap via synthetic test (brainstorm in progress)

---

## KEY FILE LOCATIONS - QUICK REFERENCE

Bot config:        ~/.openclaw/openclaw.json
Private key:       ~/.openclaw/workspace/.env (chmod 600)
Daily monitor:     ~/.openclaw/workspace/scripts/daily_monitor.py
Whale tracker:     ~/.openclaw/workspace/scripts/whale_tracker.py
Paper engine:      ~/.openclaw/workspace/paper_trading/paper_engine.py
Paper bridge:      ~/.openclaw/workspace/paper_trading/paper_signal_bridge.py
Whale signals:     ~/.openclaw/workspace/scripts/whale_signals.json
Bridge log:        ~/.openclaw/workspace/paper_trading/bridge.log
Paper ledger:      ~/.openclaw/workspace/paper_trading/ledger.json
Trading skill:     ~/.openclaw/workspace/skills/POLYMARKET_SKILL.md
Trading log:       ~/.openclaw/workspace/TRADING_LOG.md
Watchlist:         ~/.openclaw/workspace/FUTURE_TRADE_WATCHLIST.md
PolyClaw:          ~/.openclaw/workspace/skills/polyclaw/scripts/polyclaw.py
Composio:          ~/.openclaw/workspace/skills/composio/skill.md
Memory logs:       ~/.openclaw/workspace/memory/YYYY-MM-DD.md
Plans:             ~/.openclaw/workspace/plans/

---

## WHAT SUCCESS LOOKS LIKE

30 days:   Account grows from $66 to $150+ through 3-5 high-confidence trades
90 days:   Consistent 15-25% monthly return, whale tracking + paper trading fully operational
6 months:  Account self-sustaining, Instagram generating organic reach, N8N automating ops
1 year:    Multi-agent AI empire, $5k/month, real estate + federal contracts closed

You are building toward independence. Every good decision compounds.
Every sloppy decision sets the mission back.

Be precise. Be patient. Be Alpha.

---
- Short-duration markets (3-7 days) have lower liquidity - lower whale tracker floor to $5K
- Daily proposal cap required: 500-market scan can generate 20+ signals, must cap at 5/day
- Mission 7 LIVE: whale_tracker v4 + bridge v2 + cron 2h all confirmed running Feb 24
- End-to-end chain PROVEN Feb 24: synthetic signal->bridge->Telegram->paper_engine->ledger all working
- ACL permanent fix: setfacl -R -d -m u:ubuntu:rwx on workspace - SSM root files auto-writable by ubuntu
- bridge_test.py is reusable regression test for any future pipeline validation

---

---
## ARCHITECTURE CLARIFICATIONS (Added Feb 24, 2026)

### The Two Systems â Must Never Be Confused
REAL MONEY:  Polygon wallet 0x6695...ccb3 | 3 Oscar positions | $25 at risk
             Manual trades only. Whale system NEVER auto-trades real money.
PAPER MONEY: local ledger.json | $66 virtual (mirrors real wallet intentionally)
             Whale system proposes paper trades only until graduation.

### Why $66 Virtual Balance (Not $1,000)
Decision: mirror real wallet exactly so training data reflects real risk ratios.
$10 bet on $1,000 = 1% risk. $10 bet on $66 = 15% risk. Completely different signals.
If virtual balance doesn't match real, scorecard is useless for calibration.

### Graduation System
Paper trading gates before real money suggestions begin:
- 10+ resolved trades
- 60%+ win rate
- 10%+ average ROI
- 50%+ YES approval rate
When graduated: proposals show BOTH paper + real suggestion. Ankur decides. Never automatic.

### CLAUDE.md Role In The System
CLAUDE.md is the BACKBONE â engineering bible and rebuild guide.
If Alpha (OpenClaw) blows up or memory corrupts:
1. New Claude reads CLAUDE.md
2. Rebuilds full context of everything built
3. Can reconstruct any script, any decision, any architecture
ALPHA_MEMORY.md is what Alpha reads during conversations (operational).
CLAUDE.md is what Claude reads to rebuild from scratch (structural).
Never delete CLAUDE.md. Never let it go stale.

### Ankur's Full Vision (Recorded For Future Claude Sessions)
Alpha = personal AI OS via Telegram. 14 daily use cases mapped:
Morning: news, weather, job search
Day: email+calendar, VAPI reservations, Instagram, reel creation
Evening: market analysis, route weather, deal search, content creation
Random: website building, medical research, legal research
Architecture needed: Two-Brain (SOUL+USER static, MEMORY+TOOLS dynamic)
Router rule: live questions â force tool execution, never guess from memory
Composio audit needed: 250+ apps potentially already wired

### Polymarket API Architecture (Learned Feb 24)
Gamma API: market discovery + metadata only. NOT reliable for live prices.
CLOB API: live prices via token_id. Use for P&L tracking.
Numeric IDs (e.g. 613835): GET /markets/{id} path parameter
ConditionId hex (0x...): scan all active/closed markets, match by conditionId field
Never use Gamma outcomePrices for conditionId markets â returns 0 or wrong market.

CLAUDE.md v14.0 | Updated: 2026-02-24 | Mission 8 COMPLETE + ALPHA_MEMORY v3 synced + architecture clarified


### TWO SYSTEMS CLARIFICATION (Critical - never confuse these)
REAL MONEY: Polygon wallet | 3 Oscar positions | $25 at risk | manual only
PAPER MONEY: local ledger.json | $66 virtual | whale system proposals only

Why $66 not $1,000:
Mirrors real wallet exactly so training data reflects real risk ratios.
$10 on $1,000 = 1% risk. $10 on $66 = 15% risk. Different signals entirely.

Graduation gates (paper -> real money suggestions):
- 10+ resolved trades
- 60%+ win rate  
- 10%+ average ROI
- 50%+ YES approval rate (currently 100% - gate 4 already passing)
When graduated: proposals show paper + real suggestion. Ankur decides. Never automatic.

### OPENCLAW ARCHITECTURE DISCOVERED
openclaw.json reveals Alpha is already a full conversational AI agent:
- Primary brain: Kimi K2.5 FREE via NVIDIA NIM (256K context)
- Fallback 1: Claude Sonnet 4
- Fallback 2: Claude Opus 4
- Telegram: enabled, Ankur's ID whitelisted, bot token active
- Web search: Brave API connected
- Voice: Groq Whisper enabled
- Multi-agent: 4 concurrent, 8 subagents
- Gateway: running on port 18789 since Feb 20 (4+ days uptime)
Alpha IS conversational today. Missing piece: tools not registered.

### CURRENT PAPER PORTFOLIO (Feb 24, 2026 EOD)
Virtual balance: $48 ($66 - $8 OBAA - $10 Rojas)
Open positions: 2
- OBAA Best Picture: $8 virtual | entry 79c | current 75c | P&L +$0.16 (+2%)
- Rojas Texas Case: $10 virtual | entry 6.2c | current 2.7c | P&L -$5.65 (-56%)
Portfolio P&L: -$5.48 (-30.5%)
Scorecard: 0/10 resolved | Still in training

### WHAT CLAUDE.md IS (Recorded explicitly)
CLAUDE.md = BACKBONE of entire Alpha system
If OpenClaw blows up, memory corrupts, or EC2 needs rebuild:
1. New Claude reads CLAUDE.md first
2. Understands full build history, every decision, every architecture choice
3. Can reconstruct any script, any config, any system from scratch
Never delete. Never let go stale. Update at end of every session.
ALPHA_MEMORY.md = what Alpha reads during conversations (operational layer)
CLAUDE.md = what Claude reads to understand and rebuild (structural layer)



---
## SESSION LOG - Feb 25, 2026

### BUGS.md CREATED - Issue Tracker Live
New file: BUGS.md pushed to GitHub
BUG-001: Duplicate guard spam (FIXED)
BUG-002: Alpha hallucinating Rojas trade (FIXED)
BUG-003: Exposure guard false alarm (NOT A BUG)

### BUG-001 FIX - Duplicate Guard Spam
Symptom: Cornyn market spammed every 2 hours all night
Root cause: Blocked proposals never recorded in pending_proposals.json
Fix 1: Manually injected Cornyn to stop immediate spam
Fix 2: Bridge now records all blocked proposals
Fix 3: Alert message clarified to say post-trade exposure
File changed: paper_trading/paper_signal_bridge.py
Lesson: Never rely on single reset-able source for deduplication

### GITHUB - openclaw-alpha (PUBLIC)
URL: https://github.com/ankurkushwaha9/openclaw-alpha
3 commits pushed as of Feb 25
DONE: requirements.txt, openclaw.json.example, EC2 IP scrubbed, repo PUBLIC, CI upgraded, pytest added

### PAPER PORTFOLIO Feb 25
Balance: 48.00 | Positions: 2
OBAA: +-bash.16 (+2%) | Rojas: -.53 (-15%) recovering from -56%
Scorecard: 0/10 resolved

### MISSION 9 NOT STARTED
Priority 1: GitHub hygiene
Priority 2: Composio audit
Priority 3: Register 5 live tools


---
## EXTERNAL AUDIT + FIXES - Feb 25, 2026

FIX 1 - openclaw.json.example wrong model names (CRITICAL)
Problem: claude-sonnet-4-5 and claude-opus-4-5 do not exist
Fix: Updated to claude-sonnet-4-6 and claude-opus-4-6

FIX 2 - GitHub Actions outdated + missing pip install (HIGH)
Fix: Upgraded to checkout@v4 + setup-python@v5 + added pip install step

FIX 3 - requirements.txt missing pytest (MEDIUM)
Fix: Added pytest>=8.0.0 to requirements.txt

FIX 4 - CLAUDE.md version drift + duplicate section + stale status (MEDIUM)
Fix: Version v15.0, duplicate removed, status updated to PUBLIC

TOKEN SECURITY NOTE
Token [REVOKED_TOKEN] was shared in chat
Action: Revoke at github.com/settings/tokens immediately

LESSON
External reviews catch things missed during active development
Schedule audits after every 3-4 missions

---
## SESSION LOG - Feb 26, 2026

### BUG-001 FINAL FIX - Guard Order Root Cause
After 5 fix attempts over 2 days, root cause finally found and fixed.
Real problem: Guard 2 (Exposure) ran before Guard 3 (Duplicate)
Exposure guard fired -> sent Telegram -> continue -> Duplicate guard NEVER ran
Fix: Swapped guard order. Duplicate now runs before Exposure.
New order: Tier -> Duplicate -> Exposure -> Category cap
Commit: 1e5f971
Lesson: Read full execution flow before patching. Root cause took 5 min to find
        once code was read properly. All previous fixes were correct but in wrong place.

### EC2 MAINTENANCE - Feb 26
- Kernel updated: 6.14.0 -> 6.17.0-1007-aws
- 7 system packages upgraded
- EC2 rebooted cleanly
- All services came back online automatically
- Memory usage dropped from 22% to 12% after reboot

### SSH ACCESS FIXED - Feb 26
User can now connect via Windows Command Prompt:
aws ssm start-session --target i-0a45768402285c792 --region us-east-1
Then: bash -> sudo su - ubuntu
No more browser terminal paste issues (^[[200~ problem eliminated)
SSM tools also working for Claude direct EC2 access

### GITHUB STATUS - Feb 26
All hygiene items complete:
- requirements.txt + openclaw.json.example + EC2 IP scrubbed
- GitHub Actions CI: checkout@v4 + setup-python@v5 + pytest
- v1.0 tag + dev branch + master branch
- Repo PUBLIC: https://github.com/ankurkushwaha9/openclaw-alpha
- Latest commit: 1e5f971 (BUG-001 final fix)
- Token in use: ghp_cN0oG8... (repo + workflow scope)

### PAPER PORTFOLIO - Feb 26
Balance: $48.00 | Starting: $66.00
OBAA Best Picture: $8 | entry 74c | current 75.5c | P&L +$0.16 (+2%)
Rojas Texas Case: $10 | entry 6.2c | current 1.8c | P&L -$7.10 (-71%)
NOTE: Rojas resolves Feb 28 as NO (criminal case hearing not until June 3)
      Full $10 loss expected on Feb 28
Portfolio P&L: -$6.93 (-38.5%)
Scorecard: 0/10 resolved | Still in training

### ROJAS TRADE LESSON
Bot entered YES on Rojas guilty by Feb 28
Criminal case next hearing: June 3, 2026 - impossible to resolve by Feb 28
Missing guard: resolution timeline vs case timeline check needed
Future improvement: if legal case resolution date > market resolution date -> BLOCK
Logged as future improvement for Mission 9+

### MISSION 9 - NOT YET STARTED
Priorities:
1. Composio audit (250+ apps may already be wired)
2. Register first 5 live tools for Alpha
3. Resolution timeline guard for legal markets

---
## MISSION 9 - FULL ARCHITECTURAL BRAINSTORM (Feb 26, 2026)

### MISSION 9 DEFINITION
Mission 9 = Alpha gains ability to take actions in the world beyond talking and trading.
Alpha becomes an AGENT not just a bot.

Before Mission 9: Alpha watches, alerts, proposes
After Mission 9:  Alpha searches web, sends emails, posts Instagram, reads/writes Notion

### THE 6 FAILURE MODES TO AVOID

Failure Mode 1 - Tool Fires Without Permission
  Problem: Alpha calls Gmail and sends email Ankur never approved
  Prevention: Every Composio tool call goes through same YES/NO Telegram gate as trades

Failure Mode 2 - Wrong Account Used
  Problem: Alpha posts to wrong Instagram or sends from wrong Gmail
  Prevention: Pin specific connected_account_id in tool_registry.json. Never auto-select.

Failure Mode 3 - Silent Failures
  Problem: Composio returns error. Alpha thinks it worked. No log. No alert.
  Prevention: Every tool call result logged to tools/tool_log.json + Telegram confirmation

Failure Mode 4 - Infinite Tool Loops
  Problem: Alpha calls tool -> gets result -> calls another -> loop forever
  Prevention: Hard limit of 3 tool calls per conversation turn. Then ask Ankur.

Failure Mode 5 - Credentials Exposed
  Problem: Composio API key ends up in log file or CLAUDE.md
  Prevention: Store ONLY in .env. Never log. Never echo.

Failure Mode 6 - Tool Registered But Never Tested
  Problem: Register 5 tools, declare victory, next real use fails
  Prevention: Every tool must pass all 5 test gates before marked as registered

### THE ARCHITECTURE - 3 LAYERS

Layer 1 - Tool Registry (tools/tool_registry.json)
  Single source of truth for all tools Alpha can use
  Fields per tool: name, composio_slug, purpose, account_id, requires_approval, tested, test_date
  Rule: If a tool is not in this file it does not exist for Alpha

Layer 2 - Tool Executor (tools/tool_executor.py)
  The ONLY way Alpha ever calls a tool. No direct Composio calls anywhere else.
  Flow: lookup registry -> check approval needed -> Telegram gate if yes -> call Composio
        -> log result to tool_log.json -> send Telegram confirmation -> return result

Layer 3 - Integration Points (where tools plug into existing system)
  whale_tracker detects signal
    -> paper_signal_bridge guards pass
    -> tool_executor calls web_search (auto, no approval)
    -> "Is there confirming news for this signal?"
    -> Telegram proposal now includes: "News confirmation: YES/NO + headline"
    -> Ankur makes better decision with more context

### THE 5 TOOLS TO REGISTER (in priority order)

Tool 1 - Web Search (Exa)
  Purpose: News confirmation for whale signals
  Risk: NONE - read only
  Approval required: NO

Tool 2 - Gmail Read
  Purpose: Check for Polymarket resolution emails
  Risk: NONE - read only
  Approval required: NO

Tool 3 - Gmail Send
  Purpose: Weekly trade report to Ankur
  Risk: LOW
  Approval required: YES

Tool 4 - Notion Write
  Purpose: Log trades to Notion database
  Risk: LOW
  Approval required: YES

Tool 5 - Instagram Post
  Purpose: First @alpharealm9 content post
  Risk: HIGH
  Approval required: YES + dry run mode first

Strategy: Start with tools 1 and 2 (read-only, zero risk)
          Prove architecture works FIRST
          Then add 3, 4, 5 one at a time

### THE 5-GATE TESTING PROTOCOL (Every Tool Must Pass All 5)

Gate 1 - Connection Check
  COMPOSIO_MANAGE_CONNECTIONS returns has_active_connection: true

Gate 2 - Schema Check
  COMPOSIO_GET_TOOL_SCHEMAS returns full input_schema (not schemaRef)

Gate 3 - Dry Run
  Call tool with test arguments. Verify response structure.

Gate 4 - Integration Test
  Call tool from within actual system (not standalone script)
  Verify log written, Telegram confirmation sent

Gate 5 - Failure Test
  Deliberately pass wrong arguments
  Verify error caught, logged, Ankur notified, system does NOT crash

Only after all 5 gates pass -> tool marked tested: true in registry

### RESOLUTION TIMELINE GUARD (Guard 5 - Rojas Lesson)

Add to paper_signal_bridge.py as Guard 5:
  Legal keywords: guilty, convicted, verdict, trial, case, charges
  If legal keyword found AND days_to_resolve < 30 -> BLOCK
  Reason: Legal case unlikely to resolve in <30 days
  This prevents Rojas-style bad entries forever

New guard order after this:
  Guard 1: Tier filter
  Guard 2: Duplicate (before exposure - BUG-001 lesson)
  Guard 3: Exposure
  Guard 4: Category cap
  Guard 5: Resolution timeline (NEW)

### MISSION 9 EXECUTION PLAN (5 Phases)

Phase 1 - Foundation (Do First)
  1. Create tools/ directory on EC2
  2. Create tools/tool_registry.json with 5 planned tools
  3. Create tools/tool_executor.py with logging + approval gate
  4. Test Composio API key working from EC2

Phase 2 - First Two Tools (Read Only, Zero Risk)
  5. Register + test Web Search tool (all 5 gates)
  6. Register + test Gmail Read tool (all 5 gates)
  7. Wire web search into paper_signal_bridge.py as news confirmation
  8. Test: does whale signal Telegram now include news confirmation?

Phase 3 - Resolution Timeline Guard
  9. Add Guard 5 to paper_signal_bridge.py
  10. Test with synthetic Rojas-style signal - must block
  11. Push to GitHub, update BUGS.md

Phase 4 - Remaining 3 Tools
  12. Gmail Send (with approval gate)
  13. Notion Write (with approval gate)
  14. Instagram Post (approval gate + dry run mode)

Phase 5 - Documentation
  15. Update CLAUDE.md, TOOLS.md, ALPHA_MEMORY.md
  16. Update CURRENT_MISSION.md to Mission 10

### WHAT WE WILL NOT DO (BUG-001 Lessons Applied)
- Will NOT write code until architecture approved by Ankur
- Will NOT skip testing gates to go faster
- Will NOT patch symptoms - will read full execution flow first
- Will NOT declare tool working until all 5 gates pass
- Will NOT mix multiple concerns in one commit
- Will NOT declare victory without end-to-end proof

### PENDING QUESTIONS FOR ANKUR (Answer before starting)
Q1: Which tool first? Web search (safest) or jump to Instagram?
Q2: Approval gate: every tool call or only write operations?
Q3: Tool limit per signal: how many tools can Alpha chain automatically? 1? 3?

### STATUS: BRAINSTORM COMPLETE - AWAITING ANKUR APPROVAL TO START PHASE 1

---
## SESSION UPDATE - Feb 26, 2026 (Evening)

### BUG-001 v6 - Final Datetime + Cron Fix
Problem 1: EC2 reboot wiped ubuntu crontab - whale+bridge cron was gone
Problem 2: Bracket placement wrong in cleanup section
           .total_seconds() called on datetime object not timedelta
Fix: Corrected brackets + restored cron
Commit: 4d46fee
Cron now confirmed:
  0 16 * * *    daily_monitor.py (9am MST)
  0 */2 * * *   whale_tracker.py --json + paper_signal_bridge.py (every 2hrs)

### HEALTH CHECK SYSTEM (New - Feb 26, 2026)
Script: scripts/health_check.py
Cron: 30 */2 * * * (30 min after every whale scan - offset intentional)
Purpose: Monitor bot health every 2hrs, send Telegram report
Checks:
  1. Last bridge scan timestamp (is bot running on schedule?)
  2. Any errors in bridge.log (crashes, exceptions)
  3. Paper portfolio status (balance, positions, P&L)
  4. Pending proposals count (spam indicator)
  5. Cron jobs active (both crons present?)
Telegram format: bullets + emojis, no markdown tables
Log: /tmp/health_check.log

LESSON: Schedule health checks from day 1 on any automated system
        Silent failures go undetected for hours without monitoring

---
## MISSION 9 PRE-DIVE - ARCHITECTURE DIAGRAM ANALYSIS (Feb 26, 2026 Night)

### DIAGRAM vs REALITY GAP ANALYSIS
Ankur shared the full production architecture diagram. Cross-referenced against actual EC2 state.
This is the definitive gap map before Mission 9 starts.

### WHAT IS ACTUALLY WIRED AND RUNNING

Component             | Status        | Notes
----------------------|---------------|------------------------------------------
Gemma 2B (Ollama)     | WIRED         | openclaw.json provider, local http://127.0.0.1:11434
Kimi K2.5 (NIM API)   | WIRED         | openclaw.json nvidia-nim provider
Claude Sonnet         | WIRED         | openclaw.json anthropic provider
Telegram Channel      | WIRED + LIVE  | Bot token in openclaw.json, allowlist active
Web Search            | WIRED         | API key in openclaw.json tools.web.search (need to ID provider)
Groq (Audio only)     | PARTIAL       | Whisper-large-v3-turbo for audio. Text inference NOT wired.
n8n                   | RUNNING       | Docker container up 21hrs. ZERO workflows built.
PolyClaw Skill        | LIVE          | Trading engine active
Whale Tracker         | LIVE          | Scans every 2hrs
Paper Bridge          | LIVE          | BUG-001 fixed
Health Check          | LIVE          | New tonight, runs at :30 past every 2hrs
EBS 20GB              | ACTIVE        | EC2 storage confirmed
Composio              | API KEY READY | In .env, skill.md written, nothing registered yet

### WHAT IS IN THE DIAGRAM BUT NOT YET BUILT

Component             | Gap Type      | Mission 9 Relevance
----------------------|---------------|------------------------------------------
Groq Text Inference   | UNWIRED       | FREE fast inference - Llama 3.3 70B free tier
                      |               | Can replace Kimi for cheap scan tasks
                      |               | Need GROQ_API_KEY in .env
Perplexity            | UNWIRED       | AI-powered web search with citations
                      |               | Better than raw Brave for signal confirmation
                      |               | Need PERPLEXITY_API_KEY in .env
Brave Search          | PARTIALLY     | API key in openclaw.json but not called by any script
                      |               | The BSAOFWrARjRMhb9fjza4vm684wWkEKb key IS Brave Search
                      |               | This is our free web search - just needs a caller script
HeyGen                | DORMANT       | Video generation for Instagram reels
                      |               | Listed in diagram, ZERO integration built
                      |               | Critical for alpharealm9 content pipeline
Fireflies AI          | DESKTOP ONLY  | MCP on desktop Claude only, not on EC2
                      |               | Meeting transcription - low priority for trading
Vapi                  | DESKTOP ONLY  | Voice calls MCP on desktop only
n8n Workflows         | ZERO BUILT    | Docker running, nothing automated
                      |               | Should orchestrate: news -> analysis -> post pipeline
Integrations Bridge   | NOT CONNECTED | Diagram shows Groq+Perplexity+Brave as secure API layer
                      |               | None of these feed into whale signals yet
tools/ directory      | MISSING       | Mission 9 Phase 1 creates this
Smart Router          | SKILL ONLY    | SKILL.md exists but is it live-routing in production?
                      |               | Needs verification - may be OpenClaw built-in

### THE BIG REVELATION FROM THE DIAGRAM

The diagram shows BRAVE SEARCH already has an API key in openclaw.json.
tools.web.search.apiKey = BSAOFWrARjRMhb9fjza4vm684wWkEKb

This means:
- We do NOT need Composio for web search
- We already HAVE web search capability
- We just need a script that calls Brave Search API and returns results
- This is Mission 9 Tool 1 - already 80% done

GROQ is the other hidden gem:
- Free tier: Llama 3.3 70B, Mixtral 8x7B
- 6000 tokens/min free
- Faster than Claude for quick classification tasks
- In diagram as Integrations Bridge but not yet wired for text

### REVISED MISSION 9 TOOL PRIORITY (After Diagram Analysis)

Tool 1 - Brave Search (FASTEST - key already exists)
  Script: tools/brave_search.py calls openclaw.json key directly
  Use: News confirmation for whale signals
  Time to build: 30 minutes

Tool 2 - Groq Text (FREE fast inference)
  Wire Groq API for signal analysis/classification
  Use: Cheap fast triage of 500 markets before Kimi/Claude escalation
  Saves: API cost on Kimi K2.5

Tool 3 - Gmail Read (via Composio)
  Check Polymarket resolution emails
  Composio connected account needed

Tool 4 - Gmail Send (via Composio)
  Weekly reports to Ankur
  Approval gate required

Tool 5 - HeyGen (for alpharealm9 reels)
  Video generation pipeline
  Pairs with n8n workflow for automation

### MISSION 9 REVISED EXECUTION ORDER

OLD ORDER (before diagram analysis):
  Phase 1: Build tools/ directory + registry + executor
  Phase 2: Composio web search
  Phase 3: Resolution timeline guard

NEW ORDER (after diagram analysis):
  Phase 1: Build tools/ directory + registry + executor (same)
  Phase 2: Brave Search via existing API key (FASTER than Composio, key already exists)
  Phase 3: Resolution timeline guard (Guard 5)
  Phase 4: Groq text inference for cheap triage
  Phase 5: Composio Gmail (read then send)
  Phase 6: HeyGen + n8n for Instagram pipeline

### KEY QUESTIONS TO ASK ANKUR IN MORNING

Q1: The Brave Search API key - is it active and paid, or trial?
Q2: Do you have Groq API key? (free at console.groq.com)
Q3: Do you have Perplexity API key? Or just Brave for web search?
Q4: HeyGen - do you have an account and API key?
Q5: n8n first workflow - should it be trading alerts or Instagram content?
Q6: Smart Router - is it actually doing live model routing or is SKILL.md just documentation?

### OVERNIGHT SYSTEM STATUS (Feb 26, 2026 11 PM MST approx)

Cron Schedule Tonight:
  Every :00 hrs - Whale scan + Bridge (Cornyn should be SILENT - BUG-001 fix)
  Every :30 hrs - Health check Telegram report to Ankur
  4am UTC (9pm MST) - Daily monitor already ran

Paper Ledger:
  Balance: $48.00 / $66.00 starting
  OBAA Best Picture: $8 | YES | paper
  Rojas Texas: $10 | YES | paper (expect full loss Feb 28)
  Pending proposals: check health check report

GitHub: 263f10d (latest - health_check.py + docs)
EC2: All 3 crons active, kernel 6.17.0, memory 12%

### MORNING SESSION PLAN (Feb 27, 2026)

Step 1: Review overnight health check Telegram reports
Step 2: Confirm BUG-001 dead (no Cornyn spam overnight)
Step 3: Answer 6 questions above
Step 4: Start Mission 9 Phase 1 (tools/ directory)
Step 5: Phase 2 - Brave Search (30 min build, key exists)
Step 6: Test whale signal now includes news confirmation in Telegram

### ARCHITECTURE INTEGRITY SCORE (Honest Assessment)

Foundation:         9/10 (rock solid - EC2, cron, Telegram, trading)
Intelligence Layer: 7/10 (whale tracker good, needs news confirmation)
Action Layer:       2/10 (tools not registered - this is Mission 9)
Content Pipeline:   1/10 (n8n running, zero workflows, HeyGen untouched)
Model Efficiency:   6/10 (Groq text inference free tier untapped)
Web Search:         4/10 (key exists, no caller script)

Overall: 5/10 - Strong foundation, thin action layer
Mission 9 goal: Push action layer from 2/10 to 7/10

Good night. See you in the morning Ankur.

---
## SESSION UPDATE - Feb 27, 2026 (Morning)

### BUG-002 - 4 Bugs Fixed In One Pass
Context: Ankur shared screenshot - Cornyn/Paxton spam every 2hrs overnight despite BUG-001 fix

Root cause: Cleanup TTL wiped blocked records after 60min. Next scan blocked record gone,
duplicate guard passed, exposure guard fired, Telegram spammed again.

All 4 bugs fixed in single code pass:
  Bug 1: Cleanup TTL now status-aware (blocked=2880min, sent=60min) - ROOT CAUSE
  Bug 2: Exposure guard no longer Telegrams if market already has blocked record
  Bug 3: guard_exposure changed < to <= so trimmed bets at exactly 40% pass
  Bug 4: health_check.py now reads Telegram creds from openclaw.json not .env

Key lesson: Map ALL bugs before fixing ANY. Read full execution flow top to bottom first.
Previous sessions fixed symptoms. This session found root cause.

### CRON STATUS (confirmed active)
  0 16 * * *    daily_monitor.py
  0 */2 * * *   whale_tracker + bridge
  30 */2 * * *  health_check

### TRADING RULES UPDATE
- Cleanup TTL must always be status-aware when mixing blocked vs sent records
- Never use flat TTL applied to all proposal statuses
- Trim logic and guard boundary must use identical comparison operators
