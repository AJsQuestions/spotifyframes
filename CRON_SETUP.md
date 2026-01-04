# macOS Cron Job Setup - Full Disk Access Required

## ⚠️ IMPORTANT: Grant Full Disk Access

Your cron job is configured but **NOT running** because macOS requires Full Disk Access permission for cron jobs.

## Setup Instructions (macOS System Settings)

1. **Open System Settings**
   - Click Apple menu → System Settings (or System Preferences on older macOS)

2. **Navigate to Privacy & Security**
   - Click "Privacy & Security" in the sidebar

3. **Select Full Disk Access**
   - Scroll down to find "Full Disk Access"
   - Click it to expand

4. **Unlock Settings**
   - Click the lock icon at the bottom left
   - Enter your password to unlock

5. **Add Cron**
   - Click the "+" button
   - In the file picker, press `Cmd+Shift+G` (Go to Folder)
   - Type: `/usr/sbin`
   - Click "Go"
   - Select `cron` and click "Open"
   - Make sure the checkbox next to `cron` is **checked**

6. **Restart Cron Service**
   ```bash
   sudo launchctl stop com.apple.cron
   sudo launchctl start com.apple.cron
   ```

   OR restart your Mac.

## Verify It's Working

After granting Full Disk Access, wait until 2:00 AM and check:

```bash
# Check if cron job ran at 2 AM
tail -100 /Users/aryamaan/Desktop/Projects/spotim8/logs/sync.log | grep "02:"

# Or check the last few entries
tail -20 /Users/aryamaan/Desktop/Projects/spotim8/logs/sync.log
```

## Test Manually

You can also test the cron wrapper right now:

```bash
cd /Users/aryamaan/Desktop/Projects/spotim8
/bin/bash scripts/cron_wrapper.sh
```

## Current Status

- ✅ Cron daemon: Running
- ✅ Cron job configured: `0 2 * * * /bin/bash /Users/aryamaan/Desktop/Projects/spotim8/scripts/cron_wrapper.sh`
- ✅ Wrapper script: Exists and executable
- ❌ Full Disk Access: **NOT GRANTED** (needs setup)
- ❌ 2 AM runs: **0 runs** (because Full Disk Access not granted)

## Troubleshooting

If cron still doesn't run after granting Full Disk Access:

1. **Check system logs:**
   ```bash
   log show --predicate 'process == "cron"' --last 1d --style syslog | grep spotim8
   ```

2. **Verify cron is in Full Disk Access:**
   - System Settings → Privacy & Security → Full Disk Access
   - Make sure `cron` has a checkmark

3. **Restart cron service:**
   ```bash
   sudo launchctl stop com.apple.cron
   sudo launchctl start com.apple.cron
   ```

4. **Check wrapper script permissions:**
   ```bash
   ls -la /Users/aryamaan/Desktop/Projects/spotim8/scripts/cron_wrapper.sh
   ```

5. **Run diagnostic script:**
   ```bash
   /Users/aryamaan/Desktop/Projects/spotim8/scripts/check_cron.sh
   ```

