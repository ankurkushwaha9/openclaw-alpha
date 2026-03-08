#!/usr/bin/env python3
"""
Shadow Monitor — Mission 11 Day 2
Watches real OpenClaw sessions. For every user message, logs what the Smart Router
WOULD have decided vs what Kimi actually answered. Zero impact on production.

Writes to: logs/routing.log (JSONL)
Run: nohup python3 scripts/shadow_monitor.py >> /tmp/shadow_monitor.log 2>&1 &
"""

import json
import os
import time
import re
from pathlib import Path
from datetime import datetime, timezone

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE         = Path('/home/ubuntu/.openclaw/workspace')
SESSIONS_DIR = Path('/home/ubuntu/.openclaw/agents/main/sessions')
LOG_FILE     = BASE / 'logs' / 'routing.log'
PID_FILE     = Path('/tmp/shadow_monitor.pid')
HEARTBEAT    = Path('/tmp/shadow_monitor.heartbeat')

# ─── Router Config (mirrors router-engine.js) ─────────────────────────────────
SIMPLE_THRESHOLD = 30
MEDIUM_THRESHOLD = 70

MODELS = {
    'simple':   'ollama/gemma2:2b',
    'medium':   'nvidia-nim/moonshotai/kimi-k2.5',
    'high':     'anthropic/claude-sonnet-4-20250514',
    'fallback': 'anthropic/claude-opus-4-20250514',
}

# Trading guardrail keywords — ANY match = minimum Kimi, never Gemma
TRADING_KEYWORDS = set([
    # Trading core
    'trade','signal','whale','market','polymarket','price','position',
    'kelly','buy','sell','entry','exit',
    # Paper trading
    'paper','proposal','approve','reject','execute','skip','tier','divergence',
    # Portfolio
    'balance','ledger','pnl','profit','loss','exposure','portfolio',
    'wallet','usdc','stake','bet',
    # Market specific
    'oscar','masters','fed','rate','bitcoin','eth','crypto',
    'resolve','resolution',
    # System ops
    'cron','bridge','scan','tracker','engine','alert','scorecard',
])

# High-complexity patterns → Sonnet tier
HIGH_COMPLEXITY_PATTERNS = [
    r'analyz|compar|evaluat|assess|strateg|recommend|explain why',
    r'what should i|how should i|what do you think',
    r'complex|difficult|challenging',
]

# Skip these system-generated messages (not real user input)
SKIP_PREFIXES = [
    'A new session was started via /new',
    '[System]',
    'SYSTEM:',
]


# ─── Router Logic ─────────────────────────────────────────────────────────────

def has_trading_keyword(text: str) -> bool:
    text_lower = text.lower()
    words = re.findall(r'\b\w+\b', text_lower)
    return bool(set(words) & TRADING_KEYWORDS)


def score_complexity(text: str) -> int:
    """
    Port of complexity-scorer.js heuristics.
    Returns 0-100 score.
    """
    score = 0
    text_lower = text.lower()

    # Length signals
    word_count = len(text.split())
    if word_count > 50:
        score += 20
    elif word_count > 20:
        score += 10
    elif word_count > 5:
        score += 5

    # Question words
    if any(w in text_lower for w in ['why', 'how', 'explain', 'analyze', 'compare']):
        score += 15

    # Multiple sentences
    sentences = len(re.split(r'[.!?]+', text.strip()))
    if sentences > 3:
        score += 10

    # High complexity patterns
    for pattern in HIGH_COMPLEXITY_PATTERNS:
        if re.search(pattern, text_lower):
            score += 20
            break

    # Simple greetings / commands — reduce score
    if any(text_lower.startswith(p) for p in ['hi', 'hello', 'hey', '/', 'ok', 'thanks', 'yes', 'no']):
        score = max(0, score - 20)

    return min(100, score)


def route(text: str) -> dict:
    """Returns routing decision dict."""
    # Trading guardrail
    if has_trading_keyword(text):
        score = score_complexity(text)
        if score > MEDIUM_THRESHOLD:
            return {
                'tier': 'high',
                'model': MODELS['high'],
                'score': score,
                'reason': 'TRADING_GUARDRAIL + high complexity → Sonnet',
                'trading_guardrail': True,
            }
        else:
            return {
                'tier': 'medium',
                'model': MODELS['medium'],
                'score': score,
                'reason': 'TRADING_GUARDRAIL → Kimi (bypass Gemma)',
                'trading_guardrail': True,
            }

    score = score_complexity(text)

    if score <= SIMPLE_THRESHOLD:
        return {
            'tier': 'simple',
            'model': MODELS['simple'],
            'score': score,
            'reason': f'Low complexity ({score}) → Gemma',
            'trading_guardrail': False,
        }
    elif score <= MEDIUM_THRESHOLD:
        return {
            'tier': 'medium',
            'model': MODELS['medium'],
            'score': score,
            'reason': f'Medium complexity ({score}) → Kimi',
            'trading_guardrail': False,
        }
    else:
        return {
            'tier': 'high',
            'model': MODELS['high'],
            'score': score,
            'reason': f'High complexity ({score}) → Sonnet',
            'trading_guardrail': False,
        }


# ─── Session Watcher ──────────────────────────────────────────────────────────

def get_latest_session() -> Path | None:
    """Return the most recently modified session JSONL."""
    sessions = sorted(
        SESSIONS_DIR.glob('*.jsonl'),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    return sessions[0] if sessions else None


def extract_text(content) -> str:
    """Extract plain text from OpenClaw content field (list or str)."""
    if isinstance(content, list):
        return ' '.join(
            c.get('text', '') for c in content
            if isinstance(c, dict) and c.get('type') == 'text'
        )
    return str(content)


def should_skip(text: str) -> bool:
    return any(text.startswith(p) for p in SKIP_PREFIXES)


def write_log(entry: dict):
    """Append JSONL entry to routing.log."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, 'a') as f:
        f.write(json.dumps(entry) + '\n')


def log_print(msg: str):
    ts = datetime.now(timezone.utc).strftime('%H:%M:%S')
    print(f'[{ts}] {msg}', flush=True)


# ─── Main Watch Loop ─────────────────────────────────────────────────────────

def watch_session(session_path: Path, start_offset: int = 0):
    """
    Tail a session file from start_offset.
    Pairs user messages with the following assistant response.
    Returns final file offset when session file changes.
    """
    offset = start_offset
    pending_user_text = None
    pending_ts = None

    log_print(f'Watching session: {session_path.name} (offset={offset})')

    while True:
        # Check for newer session file every 30s
        latest = get_latest_session()
        if latest and latest != session_path:
            log_print(f'New session detected: {latest.name}')
            return 0  # signal caller to switch

        # Read new lines
        try:
            with open(session_path, 'r') as f:
                f.seek(offset)
                new_lines = f.readlines()
                offset = f.tell()
        except Exception as e:
            log_print(f'Read error: {e}')
            time.sleep(10)
            continue

        for raw in new_lines:
            raw = raw.strip()
            if not raw:
                continue
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if entry.get('type') != 'message':
                continue

            msg = entry.get('message', {})
            role = msg.get('role', '')

            if role == 'user':
                text = extract_text(msg.get('content', ''))
                if text and not should_skip(text):
                    pending_user_text = text
                    pending_ts = entry.get('timestamp', datetime.now(timezone.utc).isoformat())

            elif role == 'assistant' and pending_user_text:
                actual_model = msg.get('model', 'unknown')
                decision = route(pending_user_text)

                log_entry = {
                    'ts': pending_ts,
                    'msg_snippet': pending_user_text[:80].replace('\n', ' '),
                    'router_tier': decision['tier'],
                    'router_model': decision['model'],
                    'actual_model': actual_model,
                    'score': decision['score'],
                    'reason': decision['reason'],
                    'trading_guardrail': decision['trading_guardrail'],
                    'session': session_path.stem[:8],
                    'match': decision['model'] == actual_model or
                             (decision['tier'] == 'medium' and 'kimi' in actual_model),
                }

                write_log(log_entry)

                tier_emoji = {'simple': '🟢', 'medium': '🔵', 'high': '🟡', 'fallback': '🔴'}
                guardrail_tag = ' [TRADING_GUARDRAIL]' if decision['trading_guardrail'] else ''
                log_print(
                    f"{tier_emoji.get(decision['tier'], '⚪')} "
                    f"{decision['tier'].upper()}{guardrail_tag} | "
                    f"actual={actual_model.split('/')[-1]} | "
                    f"msg={pending_user_text[:40]!r}"
                )

                pending_user_text = None
                pending_ts = None

        # Update heartbeat
        HEARTBEAT.write_text(datetime.now(timezone.utc).isoformat())

        time.sleep(5)  # poll every 5 seconds

    return offset


def main():
    # Write PID
    PID_FILE.write_text(str(os.getpid()))

    log_print('='*60)
    log_print('Shadow Monitor started — Mission 11 Day 2')
    log_print(f'Logging to: {LOG_FILE}')
    log_print('Zero production impact — observe only')
    log_print('='*60)

    # Write startup entry to routing.log
    write_log({
        'ts': datetime.now(timezone.utc).isoformat(),
        'event': 'SHADOW_MONITOR_START',
        'pid': os.getpid(),
        'config': {
            'simple_threshold': SIMPLE_THRESHOLD,
            'medium_threshold': MEDIUM_THRESHOLD,
            'models': MODELS,
            'trading_keywords_count': len(TRADING_KEYWORDS),
        }
    })

    offset = 0
    while True:
        session = get_latest_session()
        if not session:
            log_print('No sessions found — waiting...')
            time.sleep(30)
            continue

        try:
            offset = watch_session(session, offset)
        except KeyboardInterrupt:
            log_print('Shadow Monitor stopped by user.')
            PID_FILE.unlink(missing_ok=True)
            break
        except Exception as e:
            log_print(f'Watch error: {e} — restarting in 10s')
            time.sleep(10)


if __name__ == '__main__':
    main()
