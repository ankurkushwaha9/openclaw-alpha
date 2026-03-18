# Real Money Trade History & Wallet Reference
**Created: 2026-03-18 | READ THIS BEFORE ASKING ANKUR ABOUT REAL MONEY**

Any Claude session, any chat window — read this file first.
Never ask Ankur to re-explain his wallet or how trades were placed.

---

## HOW REAL MONEY TRADES ARE PLACED (Critical)

Ankur is based in Montana, USA.
Polymarket blocks US users from trading via their website UI.

Trade execution method:
- Trades are placed via MetaMask wallet directly
- MetaMask connects to Polymarket's smart contracts on Polygon blockchain
- NO Polymarket website login is used
- NO Polymarket UI wallet is used
- The Alpha0609 Polymarket profile shows ZERO positions because
  trades bypass the UI entirely — this is EXPECTED and NOT a bug

Do NOT check polymarket.com/@Alpha0609 for position verification.
It will always show $0.00 and no positions. This is correct.

---

## WALLET DETAILS

Primary trading wallet (MetaMask):
  Address:  0x6695ebAC8bb8d7636d6744643DeDE27eD67bccB3
  Network:  Polygon (MATIC)
  Token:    USDC (native) -- contract 0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359
  NOTE:     0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359 is the USDC TOKEN CONTRACT
            not Ankur's wallet. Do not confuse the two.

Gas token:
  POL (MATIC): ~19.49 (as of March 2026)

How to verify balance on-chain (no login needed):
  Use Polygon public RPC: https://polygon-bor-rpc.publicnode.com
  Call balanceOf(wallet) on USDC contract
  Confirmed balance as of March 15, 2026: $66.00 USDC

How to verify transactions:
  Polygonscan: polygonscan.com/address/0x6695ebAC8bb8d7636d6744643DeDE27eD67bccB3
  Look for USDC token transfers on Polygon network

---

## HOW BOT MONITORS REAL MONEY POSITIONS

The bot does NOT execute real money trades.
The bot only MONITORS real positions by:
  1. Hardcoding market IDs and entry prices in daily_monitor.py
  2. Querying Gamma API for current prices
  3. Calculating P&L from: (shares * current_price) - invested

Code location: scripts/daily_monitor.py
Variable: OSCAR_POSITIONS dict (lines 28-30)

Ankur tells the bot what he bought manually.
Bot tracks it for reporting purposes only.

---

## TRADE HISTORY

### Batch 1 -- Oscar 2026 Trades (Placed Feb 2026)

All three placed manually via MetaMask on Polygon.
Markets sourced from Polymarket via Gamma API.
Ceremony date: March 15, 2026.

| Market | Market ID | Side | Entry | Invested | Outcome | P&L |
|--------|-----------|------|-------|----------|---------|-----|
| Best Picture (OBAA) | 613835 | YES | 74.5c | $10.00 | WIN | +$3.42 |
| Best Actor (Chalamet) | 614008 | YES | 79.0c | $8.00 | LOSS | -$8.00 |
| Best Supporting (Teyana) | 614355 | YES | 70.0c | $7.00 | LOSS | -$7.00 |

NET P&L Batch 1: -$11.58 (-46.3%)
Total invested: $25.00
Total returned: $13.42 (OBAA payout only)

Resolution status (as of March 18, 2026):
  All 3 markets: closed=True, resolved=None on Gamma API
  Prices confirmed: OBAA YES=100c, Chalamet YES=0c, Teyana YES=0c
  OBAA payout of ~$13.42 USDC: PENDING on-chain settlement
  Wallet balance still at $66.00 -- payout not arrived yet
  Expected: Polymarket settles on-chain within 24-72hrs of ceremony
  No action needed -- payout arrives automatically

Verification method used:
  Gamma API: gamma-api.polymarket.com/markets/{market_id}
  Polygon RPC: balance confirmed $66.00 USDC (unchanged)
  Polymarket profile: shows $0 (expected -- US MetaMask bypass)

---

## HOW TO VERIFY POSITIONS IN FUTURE (Step by Step)

Step 1: Check Gamma API for market outcome
  GET https://gamma-api.polymarket.com/markets/{market_id}
  Look at: outcomePrices[0] = YES price
  If 1.0 = YES won, if 0.0 = YES lost

Step 2: Check wallet balance on-chain
  python3 -c "
  import requests
  wallet = '0x6695ebAC8bb8d7636d6744643DeDE27eD67bccB3'
  rpc = 'https://polygon-bor-rpc.publicnode.com'
  contract = '0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359'
  payload = {'jsonrpc':'2.0','method':'eth_call',
    'params':[{'to':contract,'data':'0x70a08231000000000000000000000000'+wallet[2:]},'latest'],'id':1}
  r = requests.post(rpc, json=payload, timeout=8)
  bal = int(r.json()['result'],16)/1_000_000
  print(f'USDC balance: \${bal:.4f}')
  "

Step 3: Check POL gas balance
  Same RPC, use eth_getBalance method

Step 4: Do NOT check polymarket.com/@Alpha0609
  Will always show $0 -- US MetaMask bypass makes this useless

---

## IMPORTANT NOTES FOR ANY FUTURE SESSION

1. Never ask Ankur "which wallet did you use" -- it is always
   0x6695ebAC8bb8d7636d6744643DeDE27eD67bccB3

2. Never suggest checking polymarket.com portfolio page -- it is
   always empty because US IP bypass is used

3. The Polymarket profile Alpha0609 is linked to this wallet
   but shows no activity because trades go direct to smart contracts

4. Bot's daily_monitor.py Real Money Report queries Gamma API
   using hardcoded market IDs -- Ankur must manually tell the bot
   when he places a new real money trade so it can be added

5. MetaMask extension cannot be read or screenshot by Claude in Chrome
   due to Chrome security sandbox -- this is a hard browser limitation

6. To add a new real money trade to bot monitoring:
   Edit scripts/daily_monitor.py
   Add to REAL_MONEY_POSITIONS dict:
   "market_id": ("Label", entry_price_decimal, invested_amount)

---

## PENDING ACTIONS (as of March 18, 2026)

- OBAA payout (~$13.42 USDC) still pending on Polygon
  Monitor wallet balance -- should jump from $66 to ~$79
  No manual action needed
- BUG-027: bridge get_live_price() still uses Gamma-only for hex IDs
  Fix on dev branch as next task
- Daily monitor REAL_MONEY_POSITIONS needs update once Oscar
  markets fully resolved -- remove them from monitoring
