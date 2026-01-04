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

# Check wrapper script
WRAPPER="/Users/aryamaan/Desktop/Projects/spotim8/scripts/cron_wrapper.sh"
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
LOG_FILE="/Users/aryamaan/Desktop/Projects/spotim8/logs/sync.log"
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
LOCK_FILE="/Users/aryamaan/Desktop/Projects/spotim8/logs/sync.lock"
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
echo "   ⚠️  IMPORTANT: macOS cron needs Full Disk Access to run scripts!"
echo ""
echo "   To grant Full Disk Access (new macOS System Settings):"
echo "   1. Open System Settings (or System Preferences on older macOS)"
echo "   2. Go to: Privacy & Security"
echo "   3. Scroll down to: Full Disk Access"
echo "   4. Click the lock icon (bottom left) to unlock"
echo "   5. Click the '+' button to add an app"
echo "   6. Navigate to: /usr/sbin/cron"
echo "   7. Select it and click 'Open'"
echo "   8. Make sure the checkbox next to 'cron' is checked"
echo "   9. Restart your Mac OR restart cron with: sudo launchctl stop com.apple.cron"
echo ""
echo "   Path to add: /usr/sbin/cron"
echo ""

# Test wrapper script syntax
echo "🧪 Testing wrapper script syntax..."
if bash -n "$WRAPPER" 2>/dev/null; then
    echo "✅ Wrapper script syntax: VALID"
else
    echo "❌ Wrapper script syntax: INVALID"
    bash -n "$WRAPPER"
fi
echo ""
echo "💡 To test the wrapper manually (will run full sync):"
echo "   cd /Users/aryamaan/Desktop/Projects/spotim8"
echo "   /bin/bash scripts/cron_wrapper.sh"
echo ""
echo "💡 Or test just the sync script:"
echo "   cd /Users/aryamaan/Desktop/Projects/spotim8"
echo "   python scripts/sync.py --skip-sync"

