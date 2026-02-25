# Ankur's AI Alpha
### Personal AI Operating System — Production Deployment

> Built by **Ankur Kush**  
> Engineering Partner: **Claude (Anthropic)**  
> Status: **LIVE** | Version: 1.0 | Updated: Feb 24, 2026

---

## What Is This?

Ankur's AI Alpha is a fully autonomous personal AI agent that lives on AWS EC2
and talks to you via Telegram. It combines prediction market intelligence,
paper trading simulation, whale signal tracking, and a conversational AI brain
into one unified system.

This is not a chatbot. This is an AI Operating System.

---

## Architecture

```
You (Telegram)
      |
      v
OpenClaw Gateway (port 18789)
      |
      v
Smart Router
  - Primary:    Kimi K2.5 via NVIDIA NIM (free, 256K context)
  - Fallback 1: Claude Sonnet 4 (Anthropic API)
  - Fallback 2: Claude Opus 4 (Anthropic API)
      |
      v
Skills Layer
  - Finance Skill    (Polymarket trading intelligence)
  - PolyClaw Skill   (Prediction market tools)
  - Data Skill       (Research + analysis)
      |
      v
Memory System
  - SOUL.md      (Identity + personality — immutable)
  - USER.md      (Your preferences + profile)
  - MEMORY.md    (Recent context — auto updated)
  - TOOLS.md     (Tool registry)
      |
      v
Integrations Bridge
  - VAPI         (Voice calls + outbound reservations)
  - Perplexity   (Deep research)
  - Brave Search (Web search)
  - Fireflies AI (Meeting transcription)
  - HeyGen       (Video generation)
  - Groq Whisper (Voice transcription)
  - ElevenLabs   (Text to speech via Composio)
```

---

## What's Built (Missions Complete)

### Mission 5 - Paper Trading Engine
Full paper trading simulation with virtual ledger.
Commands: init, buy, status, resolve, report
Virtual balance mirrors real wallet for accurate training.

### Mission 6 - Whale Signal Bridge
Connects whale tracker signals to paper trading proposals.
Sends Telegram proposals with Kelly sizing and 4 guard checks.
Daily cap: 5 proposals. Kelly fraction: 25%.

### Mission 7 - Active Intelligence Layer
Whale tracker v4 scanning 500 Polymarket markets every 2 hours.
Filters: 3-7 day resolution window + $5K liquidity floor.
Tier 1: >15% divergence | Tier 2: 8-15% | Tier 3: ignored.

### Mission 8 - End-to-End Pipeline Test
Full chain verified: signal -> bridge -> Telegram -> paper_engine -> ledger.
Synthetic test tool built (bridge_test.py) for regression testing.
Production ledger never touched during tests (BOT_ENV=e2e_test).

---

## Go-Live Scorecard

Paper trading trains the system before real money scaling begins.

| Gate | Requirement | Current |
|------|-------------|---------|
| 1 | 10+ resolved trades | 0/10 |
| 2 | 60%+ win rate | 0% |
| 3 | 10%+ average ROI | 0% |
| 4 | 50%+ approval rate | 100% |

When all 4 gates pass: whale proposals include real money suggestions.
Ankur always makes the final decision. Nothing executes automatically.

---

## Daily Use Cases (Vision)

Alpha is designed to handle these real daily conversations via Telegram:

**Morning**
- "Top 10 news — politics, AI, markets, sports"
- "Temperature in Montana"
- "Best AI jobs matching my skills"

**During The Day**
- "Go through my emails and schedule a call with marketing"
- "Make a restaurant reservation for 2 people"
- "Check my Instagram messages"
- "Create a reel from this link"

**Evening**
- "How did the market do today and what about our open trades?"
- "Weather along my drive from Great Falls to Helena"
- "Find me iPhone deals online"
- "Create AI content for Instagram"

---

## Infrastructure

- Cloud: AWS EC2 m7i-flex.large, us-east-1
- Storage: EBS 20GB gp3
- Docker: v28.2.2 (n8n automation container)
- Python: 3.12 with virtual environment
- Automation: n8n on port 5678
- Monitoring: UptimeRobot (5 min intervals)
- Gateway: OpenClaw on port 18789

---

## Security Model

All sensitive data stays LOCAL on EC2. Never in this repository.

Files blocked by .gitignore (never committed):
- openclaw.json (all API keys)
- ledger.json (real trade history)
- pending_proposals.json (operational data)
- .env files of any kind
- Virtual environment

To deploy your own instance:
1. Copy openclaw.json.example
2. Fill in your own API keys
3. Never commit the real file

---

## How To Deploy Your Own Alpha

```bash
# 1. Clone this repo
git clone https://github.com/ankurkushwaha9/openclaw-alpha.git
cd openclaw-alpha

# 2. Install OpenClaw
# Follow OpenClaw installation docs

# 3. Configure your keys
cp openclaw.json.example openclaw.json
# Edit openclaw.json with your API keys

# 4. Set up Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 5. Initialize paper trading
python paper_trading/paper_engine.py init

# 6. Set up cron jobs
# Whale scan every 2 hours:
# 0 */2 * * * cd /path/to/workspace && python scripts/whale_tracker.py
# Daily report 9am MST:
# 0 16 * * * cd /path/to/workspace && python paper_trading/daily_monitor.py

# 7. Start OpenClaw gateway
# openclaw start

# 8. Message your bot on Telegram
# "Hey Alpha, what's my paper trading status?"
```

---

## Channel Support

Currently live:
- Telegram (primary)

Designed to support (future):
- WhatsApp
- Discord
- Web interface

The core intelligence layer is channel-agnostic.
Swap the channel adapter and everything else stays identical.

---

## The Backbone

**CLAUDE.md** is the engineering bible of this project.
If anything breaks, a new Claude session reads CLAUDE.md and
can rebuild the entire system from scratch. Every decision,
every architecture choice, every lesson learned is documented there.

**ALPHA_MEMORY.md** is what Alpha reads during conversations.
It contains the current state of all systems, positions, and context.

---

## Created By

**Ankur Kush** — Vision, product direction, and all key decisions  
**Claude (Anthropic)** — Engineering partner, architecture, and implementation  

*"We are building an empire, one mission at a time."*

---

## License

Private repository. All rights reserved.
Contact: kush.ankur0609@gmail.com
