# Nova Act - Browser Automation Feasibility Study
Status: DRAFT - DO NOT BUILD YET
Gate: Build only after 50-60% win rate AND Profit Alert Layer is built
Created: 2026-03-11 | Author: Ankur + Claude

---

## What Is Nova Act?

Amazon browser automation agent (released March 2025, developer preview).
Controls a real Chrome browser via natural language instead of CSS selectors.

Core capabilities:
- Natural language clicks instead of brittle DOM selectors
- Visual reasoning: screenshot + DOM simultaneously
- Human-in-the-loop: pauses on CAPTCHA, resumes after manual step
- Pydantic schema extraction: structured data from any web page

---

## Feasibility Assessment - 3 Categories

### Category 1 - HIGH VALUE (solves a real gap)

Use case: Automated early sell via MetaMask on polymarket.com

Current problem:
  US IP blocks CLOB sell endpoint -> HTTP 403 always
  Cannot sell positions early via API
  Only option: manual MetaMask on polymarket.com
  Requires Ankur to be at his computer

Nova Act solution:
  nova.act("Connect MetaMask wallet")
  nova.act("Navigate to my open positions")
  nova.act("Sell [position] at market price")
  nova.act("Confirm transaction in MetaMask")

This enables:
  Profit Alert Layer -> triggers Nova Act -> automated early exit
  Stop-loss when thesis breaks, profit-taking when target hit
  No more manual MetaMask intervention needed

Verdict: HIGH VALUE - only legitimate use case for our system

---

### Category 2 - ZERO VALUE (already solved better)

Use case: Extract market odds from polymarket.com UI

Why we do not need this:
  gamma-api.polymarket.com  -> market prices (JSON, fast, free)
  clob.polymarket.com       -> live order book (JSON, fast)
  data-api.polymarket.com   -> trade history (JSON, fast)

Browser scraping is 10-50x slower, more fragile, unnecessary.
We scan 13,533+ markets via API already.

Verdict: ZERO VALUE - REST APIs are strictly better

---

### Category 3 - PREMATURE

Use case: Market discovery / research browsing

We already have 13,533+ markets via /events + /markets API.
Phase 5 (order book thinning) and Phase 6 (swarm detection)
will cover pre-whale and coordinated signals.

Verdict: PREMATURE - build Phase 5 and 6 first

---

## Critical Constraints

Constraint 1 - EC2 Has No Display:
  Nova Act requires real Chrome browser
  EC2 is headless Ubuntu server
  Needs: Xvfb + Chromium + 2GB extra RAM
  Solvable but adds infrastructure complexity

Constraint 2 - MetaMask Security on EC2:
  Automated sells require private key in browser extension on server
  Current risk surface: .env on EC2 (controlled)
  Nova Act surface: key in browser + automation layer accessing it
  Needs security review before implementing

Constraint 3 - SDK Maturity:
  Nova Act still in developer preview (March 2025)
  API could change without notice
  Financial bots need stable dependencies

---

## Gate Conditions Before Building (ALL must be true)

1. Paper trading win rate >= 50% over minimum 10 resolved trades
2. Profit Alert Layer built and tested (must exist to trigger Nova Act)
3. Security review of MetaMask-on-EC2 completed
4. Nova Act out of developer preview (stable API)
5. EC2 upgraded for headless Chrome

---

## Decision Log

2026-03-11: Feasibility study - Ankur + Claude
Finding shared by Ankur from external research
Assessment: one real use case (MetaMask sells), everything else
already covered by REST APIs
Decision: DRAFT and HOLD - same gate as Phase 6 swarm detection
