#!/bin/bash
# Diagnostic script to check cron job status

echo "=== Cron Job Status Check ==="
echo ""

# Check if cron is running
if pgrep -x cron > /dev/null; then
    echo "✅ Cron daemon is running"
else
    echo "❌ Cron daemon is NOT running"
fi

echo ""

# Show configured cron jobs
echo "📋 Configured cron jobs:"
crontab -l | grep -v "^#" | grep -v "^$" || echo "  (none found)"
echo ""

# Get project root dynamically
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Check wrapper script
WRAPPER="$PROJECT_ROOT/scripts/automation/cron_wrapper.sh"
if [ -f "$WRAPPER" ]; then
    echo "✅ Wrapper script exists: $WRAPPER"
    if [ -x "$WRAPPER" ]; then
        echo "✅ Wrapper script is executable"
    else
        echo "❌ Wrapper script is NOT executable (fixing...)"
        chmod +x "$WRAPPER"
        echo "✅ Fixed"
    fi
else
    echo "❌ Wrapper script NOT found: $WRAPPER"
fi
echo ""

# Check log file
LOG_FILE="$PROJECT_ROOT/logs/sync.log"
if [ -f "$LOG_FILE" ]; then
    echo "✅ Log file exists: $LOG_FILE"
    LAST_RUN=$(tail -1 "$LOG_FILE" | grep -oE "[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}" | tail -1)
    if [ -n "$LAST_RUN" ]; then
        echo "   Last log entry: $LAST_RUN"
    fi
    # Check for 2 AM runs
    AM_RUNS=$(grep -E " 02:" "$LOG_FILE" | wc -l | tr -d ' ')
    echo "   Number of 2 AM runs found: $AM_RUNS"
else
    echo "❌ Log file NOT found: $LOG_FILE"
fi
echo ""

# Check lock file
LOCK_FILE="$PROJECT_ROOT/logs/sync.lock"
if [ -f "$LOCK_FILE" ]; then
    PID=$(cat "$LOCK_FILE" 2>/dev/null)
    if kill -0 "$PID" 2>/dev/null; then
        echo "⚠️  Lock file exists - sync may be running (PID: $PID)"
    else
        echo "⚠️  Stale lock file found (removing...)"
        rm -f "$LOCK_FILE"
        echo "✅ Removed stale lock"
    fi
else
    echo "✅ No lock file (no sync currently running)"
fi
echo ""

# Check if macOS cron needs Full Disk Access
echo "📝 macOS Cron Permission Check:"
echo "   On macOS, cron jobs may need Full Disk Access to work properly."
echo "   To grant it:"
echo "   1. System Preferences → Security & Privacy → Privacy"
echo "   2. Select 'Full Disk Access'"
echo "   3. Click the lock to make changes"
echo "   4. Add '/usr/sbin/cron' to the list"
echo ""

# Test wrapper script
echo "🧪 Testing wrapper script..."
cd "$PROJECT_ROOT"
if /bin/bash "$WRAPPER" --skip-sync > /dev/null 2>&1; then
    echo "✅ Wrapper script test: SUCCESS"
else
    echo "❌ Wrapper script test: FAILED"
    echo "   Run manually to see errors: /bin/bash $WRAPPER --skip-sync"
fi

