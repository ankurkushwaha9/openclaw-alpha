# Smart Router Skill — Mission 11

## Purpose
Handles `/cost` and `/routing` Telegram commands.
Provides API cost tracking and routing analytics.

---

## Command: /cost

**Trigger:** User sends `/cost` in Telegram

**Action:** Run the following bash command and return the output verbatim as a Telegram message:
```bash
cd /home/ubuntu/.openclaw/workspace && python3 scripts/cost_tracker.py
```

**If the script fails or returns empty:** Reply with:
"💰 No API cost data yet. Cost tracking begins once Smart Router starts routing to Claude models."

---

## Command: /routing

**Trigger:** User sends `/routing` in Telegram

**Action:** Run the following bash command and return the formatted output:
```bash
cd /home/ubuntu/.openclaw/workspace && python3 scripts/routing_report.py
```

**If routing.log does not exist yet:** Reply with:
"📊 Shadow monitor not yet collecting data. Run: `nohup python3 scripts/shadow_monitor.py >> /tmp/shadow_monitor.log 2>&1 &`"

---

## Command: /shadow

**Trigger:** User sends `/shadow` in Telegram

**Action:** Check shadow monitor status:
```bash
cat /tmp/shadow_monitor.heartbeat 2>/dev/null && echo "---PID---" && cat /tmp/shadow_monitor.pid 2>/dev/null && echo "---LINES---" && wc -l /home/ubuntu/.openclaw/workspace/logs/routing.log 2>/dev/null || echo "routing.log not found"
```

Return status as:
- ✅ Running (show last heartbeat + lines logged) if heartbeat exists and is recent
- ❌ Not running if no heartbeat or PID file missing

---

## Notes
- cost_tracker.py tracks Anthropic API spend only (Sonnet + Opus)
- Kimi K2.5 and Gemma are free — not tracked
- Weekly cap: $5.00 | Alert threshold: $4.50
- routing.log is JSONL at: logs/routing.log
- Shadow monitor PID: /tmp/shadow_monitor.pid
- Shadow monitor heartbeat: /tmp/shadow_monitor.heartbeat (updated every 5s)
