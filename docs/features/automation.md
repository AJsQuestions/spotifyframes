# Automation & Scheduled Syncs

SpotiM8 supports fully automated daily syncs via cron jobs.

## Cron Job Setup

The cron job runs daily at 2:00 AM and automatically syncs your library and updates playlists.

### Quick Setup

```bash
# Easy setup (recommended):
./src/scripts/automation/cron.sh
```

### Manual Setup

```bash
crontab -e
# Add: 0 2 * * * /bin/bash /path/to/SPOTIM8/src/scripts/automation/cron_wrapper.sh
```

### Verify Cron Job

```bash
# Check if cron job is installed
crontab -l | grep spotim8

# Test the wrapper manually
/bin/bash src/scripts/automation/cron_wrapper.sh
```

## Cron Wrapper Features

The `cron_wrapper.sh` script provides:

- ✅ **Automatic log rotation** (keeps last 3 backups)
- ✅ **Prevents concurrent runs** with lock file mechanism
- ✅ **Dependency verification** before execution
- ✅ **Automatic cleanup** on errors
- ✅ **macOS permission handling**

## Logs

Sync logs are written to `logs/sync.log`:

```bash
# View recent logs
tail -f logs/sync.log

# Check last sync status
tail -20 logs/sync.log
```

## Email Notifications

Get email notifications after each sync run. Configure in your `.env` file:

**Gmail Setup:**
1. Enable 2-factor authentication on your Gmail account
2. Generate an [App Password](https://myaccount.google.com/apppasswords)
3. Add to `.env`:
   ```bash
   EMAIL_ENABLED=true
   EMAIL_SMTP_HOST=smtp.gmail.com
   EMAIL_SMTP_PORT=587
   EMAIL_SMTP_USER=your_email@gmail.com
   EMAIL_SMTP_PASSWORD=your_16_char_app_password
   EMAIL_TO=recipient@example.com
   ```

**Note:** Email failures won't break the sync - notifications are non-blocking.

## Sync Options

```bash
# Full sync + playlist update (default)
python src/scripts/automation/sync.py

# Skip sync, only update playlists (fast, uses existing data)
python src/scripts/automation/sync.py --skip-sync

# Sync only, don't update playlists
python src/scripts/automation/sync.py --sync-only

# Process all months, not just current month
python src/scripts/automation/sync.py --all-months
```

## Troubleshooting

### Cron Job Not Running

1. Check cron service is running:
   ```bash
   # macOS
   sudo launchctl list | grep cron
   
   # Linux
   sudo systemctl status cron
   ```

2. Verify cron job path is correct:
   ```bash
   crontab -l | grep spotim8
   # Should show: 0 2 * * * /bin/bash /path/to/SPOTIM8/src/scripts/automation/cron_wrapper.sh
   ```

3. Check logs for errors:
   ```bash
   tail -50 logs/sync.log
   ```

### Permission Issues

Make sure the cron wrapper script is executable:
```bash
chmod +x src/scripts/automation/cron_wrapper.sh
```

### Virtual Environment Not Found

The cron wrapper automatically detects and activates the virtual environment. Make sure it's at:
- `venv/` or `.venv/` in the project root
