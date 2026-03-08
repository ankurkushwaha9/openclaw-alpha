#!/bin/bash
# shadow_watchdog.sh
# Called by cron every 10 minutes to ensure shadow_monitor stays running.
# Cron entry: */10 * * * * /bin/bash /home/ubuntu/.openclaw/workspace/scripts/shadow_watchdog.sh

HEARTBEAT="/tmp/shadow_monitor.heartbeat"
PID_FILE="/tmp/shadow_monitor.pid"
LOG="/tmp/shadow_monitor.log"
SCRIPT="/home/ubuntu/.openclaw/workspace/scripts/shadow_monitor.py"

is_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            return 0
        fi
    fi
    return 1
}

is_stale() {
    if [ ! -f "$HEARTBEAT" ]; then
        return 0
    fi
    # Check if heartbeat is older than 2 minutes
    LAST=$(date -d "$(cat $HEARTBEAT)" +%s 2>/dev/null || echo 0)
    NOW=$(date +%s)
    AGE=$((NOW - LAST))
    if [ "$AGE" -gt 120 ]; then
        return 0
    fi
    return 1
}

if is_running && ! is_stale; then
    exit 0
fi

echo "[$(date -u +%H:%M:%S)] Shadow monitor not running or stale — restarting" >> "$LOG"
nohup python3 "$SCRIPT" >> "$LOG" 2>&1 &
echo "Watchdog restarted shadow_monitor at $(date -u)"
