# ALPHA_MEMORY.md — Ankur's AI Alpha Working Memory
# Version: 3.0 | Updated: 2026-02-24
# READ THIS FIRST — This is Alpha's source of truth for all conversations

---

## WHO ALPHA IS

Alpha is Ankur's personal AI operating system.
Primary interface: Telegram
Brain: Kimi K2.5 (free) → Claude Sonnet → Claude Opus (fallback chain)
Location: AWS EC2 m7i-flex.large, us-east-1
Owner: Ankur Kush | Telegram ID: 8583530506

---

## THE TWO SYSTEMS — CRITICAL DISTINCTION

Alpha runs TWO completely separate trading systems in parallel:

### System 1 — REAL MONEY (Polygon Wallet)
- Wallet: 0x6695ebAC8bb8d7636d6744643DeDE27eD67bccB3
- Network: Polygon
- These are REAL USDC trades Ankur placed manually
- Whale system does NOT auto-trade real money — ever
- Current balance: ~$41 USDC remaining

Active real positions (resolve March 15, 2026 — Oscars):
- OBAA Best Picture:      $10 real | entry 74c | current ~75c | P&L ~+$0.16
- Chalamet Best Actor:    $8 real  | entry 79c | current ~77c | P&L ~-$1.84
- Teyana Best Supporting: $7 real  | entry 70c | current ~69c | P&L ~-$2.17
Total real money at risk: $25 | Unrealized P&L: ~-$3.85
Strategy: Hold to resolution. CLOB sell blocked from US IP. Auto-resolve only.
Action: Monitor only. No new real trades until paper system graduates.

### System 2 — PAPER TRADING (Virtual Training System)
- Platform: LOCAL ledger.json on EC2 — NOT PolySimulator
- Location: /home/ubuntu/.openclaw/workspace/paper_trading/ledger.json
- Virtual balance: $66 USDC (mirrors real wallet exactly — intentional design)
- Purpose: Train the whale signal system before risking more real money
- PolySimulator.com account exists but is NOT used — no API available

Active paper positions:
- OBAA Best Picture:    $8 virtual  | entry 79c | current ~75c | P&L +$0.16
- Rojas Texas Case:     $10 virtual | entry 6.2c | current 2.7c | P&L -$5.65

To check live paper status:
  cd /home/ubuntu/.openclaw/workspace
  source skills/polyclaw/.venv/bin/activate
  python paper_trading/paper_engine.py status
  python paper_trading/paper_engine.py report

---

## GRADUATION SYSTEM — When Real Money Trading Begins

Paper trading trains the system. Real money suggestions begin ONLY after:

Gate 1: 10+ resolved paper trades
Gate 2: 60%+ win rate
Gate 3: 10%+ average ROI
Gate 4: 50%+ YES approval rate

Current scorecard: 0/10 resolved trades. Still in training.

When graduated — whale proposals will show BOTH paper + real money suggestion.
Ankur always makes final decision. Nothing ever executes automatically with real money.

---

## INTELLIGENCE LAYER — HOW WHALE SIGNALS WORK

Whale Tracker v4 (LIVE — runs every 2 hours automatically):
- Script: scripts/whale_tracker.py
- Scans: 500 Polymarket markets
- Filter: 3-7 day resolution window + $5K liquidity floor
- Output: scripts/whale_signals.json

Signal tiers:
- Tier 1: >15% divergence → propose immediately (high confidence)
- Tier 2: 8-15% divergence → propose and monitor
- Tier 3: <8% → ignore

Bridge v2 (LIVE — runs after every whale scan):
- Script: paper_trading/paper_signal_bridge.py
- Daily cap: 5 proposals per UTC day
- Kelly sizing: 25% fractional ($3 min, $10 max per trade)
- 4 guards: tier filter, 40% exposure cap, no duplicates, 40% category cap

When real whale signal fires:
1. Bridge detects Tier 1 or 2 signal
2. Runs all 4 guards
3. Sends PAPER TRADE PROPOSAL to Ankur's Telegram
4. Ankur replies YES or NO
5. If YES: run paper_engine.py buy with args from proposal
6. Ledger updates, scorecard progresses

Important: Whale system currently proposes PAPER TRADES ONLY.
Real money suggestions added after graduation (10 resolved trades + 60% WR).

---

## MONITORING (LIVE)

Daily report: 9am MST (4pm UTC) — real + paper portfolio sent to Telegram
Weekly report: Sundays 9am MST
UptimeRobot: monitors EC2 every 5 min
Dashboard: dashboard.uptimerobot.com/monitors/802403664

---

## INFRASTRUCTURE STATUS (Feb 24, 2026)

All missions complete as of today:
- Mission 5 DONE: Paper trading engine (init/buy/status/resolve/report)
- Mission 6 DONE: Whale-to-paper bridge fully wired
- Mission 7 DONE: 500 markets, 3-7 day filter, cron every 2 hours
- Mission 8 DONE: End-to-end chain proven via synthetic test

Key fixes applied:
- ACL permanent fix: SSM root files auto-writable by ubuntu (no more permission errors)
- CLOB API fix: conditionId markets now use scan-based price lookup
- Market ID fix: 0x hex markets use query param, numeric IDs use path param

Key files:
- Paper ledger:     paper_trading/ledger.json (SINGLE SOURCE OF TRUTH)
- Bridge log:       paper_trading/bridge.log
- Whale signals:    scripts/whale_signals.json
- Test tool:        paper_trading/bridge_test.py (reusable regression test)
- Engineering log:  CLAUDE.md (backbone — full build history)

---

## ANKUR'S FULL VISION — ALPHA AS PERSONAL AI OS

What Ankur wants to say to Alpha and have Alpha actually do:

Morning:
- "Top 10 news — politics, AI, markets, sports" → Brave + Perplexity search
- "Temperature in Montana" → Weather API
- "Best AI jobs matching my skills" → Brave + Perplexity search

During day:
- "Go through my emails and schedule a call" → Gmail + Google Calendar
- "Make a restaurant reservation for 2" → VAPI outbound call (LIVE TODAY)
- "Check my Instagram messages" → Instagram Graph API
- "Create a reel from this link" → HeyGen + Perplexity + Gemini

Evening:
- "How did market do + open/closed trades?" → paper_engine.py + Gamma API
- "Weather Great Falls to Helena by car" → Weather + Google Maps API
- "Find iPhone deals online" → Brave Search
- "Create AI content for Instagram" → Perplexity + HeyGen

Random:
- "Build a production website" → Claude Code + EC2
- "How to lower my medical bill" → Perplexity research
- "LLC formation legal advice" → Perplexity research

---

## MISSION 9 — NEXT BUILD (Not started yet)

Goal: Register Alpha's first 5 live callable tools so Alpha executes
real actions instead of guessing from memory.

Tool 1: get_portfolio_status() → runs paper_engine.py status live
Tool 2: search_and_summarize(query) → Brave + Perplexity
Tool 3: get_weather(location) → OpenWeatherMap API
Tool 4: make_phone_call(purpose) → VAPI outbound
Tool 5: analyze_trades() → Gamma API + ledger.json

Two-Brain architecture to implement:
- SOUL.md: Alpha's identity, personality, non-negotiables (immutable)
- USER.md: Ankur's preferences, location, risk appetite (rarely changes)
- MEMORY.md: Recent conversations, running projects (auto-updated)
- TOOLS.md: Tool registry, when to call what (updated when tools change)

Router rule: Any question with "how much / balance / P&L / status /
current / today / now / signals" → FORCE live tool execution. Never guess.

---

## COMPOSIO INTEGRATION (Audit pending)

Composio is installed and connected — 250+ app integrations available including:
Gmail, Google Calendar, Instagram, Facebook, Slack, LinkedIn, Notion, GitHub
66 ElevenLabs voice actions confirmed available

Full Composio audit needed before Mission 9 build.
Many Tier 2/3 tools may already be wired through Composio.

---

## KEY LESSONS LEARNED

- Virtual balance = $66 to mirror real wallet (intentional — better training data)
- PolySimulator has no API — built local ledger.json instead (more powerful)
- SSM runs as root — ACL fix applied permanently Feb 24
- Gamma API = metadata only, NOT reliable for live prices
- CLOB API = live prices for conditionId hex markets
- ConditionId markets: scan all active/closed markets, match by conditionId exactly
- End-to-end chain proven Feb 24: synthetic test passed all 6 steps
- Rojas trade -56%: whale signals can be wrong, paper trading exists for this reason
- One trade means nothing statistically — need 10 resolved to evaluate system
