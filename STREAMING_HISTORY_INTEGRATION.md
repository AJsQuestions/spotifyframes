# Streaming History Integration Guide

This document describes the new streaming history features integrated into spotim8.

## Overview

The project now integrates Spotify data exports to enable:
- **Most Played Playlists** - Monthly playlists based on actual listening data
- **Time-Based Playlists** - Morning, Evening, Weekend playlists
- **Repeat/Comfort Zone Playlists** - Tracks you listen to repeatedly
- **Enhanced Analysis** - Listening patterns, discovery insights, redundancy detection

## Setup

### 1. Download Spotify Data Exports

Download your data from Spotify:
1. Go to https://www.spotify.com/account/privacy/
2. Request your data (takes a few days)
3. Download and extract the ZIP file
4. Place these folders in your project root:
   - `Spotify Account Data/` - Contains basic streaming history
   - `Spotify Extended Streaming History/` - Contains detailed streaming history
   - `Spotify Technical Log Information/` - Optional, for technical analysis

### 2. Configure Environment Variables

Add to your `.env` file:

```bash
# Enable streaming history features
ENABLE_MOST_PLAYED_PLAYLISTS=true
ENABLE_TIME_BASED_PLAYLISTS=false
ENABLE_REPEAT_PLAYLISTS=false

# Playlist naming prefixes
PLAYLIST_PREFIX_MOST_PLAYED=Top
PLAYLIST_PREFIX_TIME_BASED=Vibes
PLAYLIST_PREFIX_REPEAT=OnRepeat

# Most played playlist settings
MOST_PLAYED_TOP_N=25
MOST_PLAYED_MIN_PLAYS=3
MOST_PLAYED_MIN_SECONDS=30

# Optional: Custom paths (defaults to PROJECT_ROOT/Spotify Account Data)
SPOTIFY_ACCOUNT_DATA_DIR=
SPOTIFY_EXTENDED_HISTORY_DIR=
```

### 3. Sync Streaming History

**Option A: Via Notebook**
Run `01_sync_data.ipynb` - it now includes a streaming history sync section.

**Option B: Via Script**
Run `python scripts/sync.py` - streaming history syncs automatically.

## New Features

### Most Played Monthly Playlists

Creates playlists like `AJTopDec25` with your top 25 most played tracks each month.

**Configuration:**
- `ENABLE_MOST_PLAYED_PLAYLISTS=true` - Enable feature
- `MOST_PLAYED_TOP_N=25` - Number of tracks per playlist
- `MOST_PLAYED_MIN_PLAYS=3` - Minimum plays to include
- `MOST_PLAYED_MIN_SECONDS=30` - Minimum seconds to count as a play

### Time-Based Playlists

Creates playlists based on when you listen:
- `AJVibesMorning` - Tracks you listen to 6-11 AM
- `AJVibesEvening` - Tracks you listen to 6-10 PM
- `AJVibesWeekend` - Tracks you listen to on weekends

**Configuration:**
- `ENABLE_TIME_BASED_PLAYLISTS=true` - Enable feature
- `PLAYLIST_PREFIX_TIME_BASED=Vibes` - Playlist prefix

### Repeat/Comfort Zone Playlists

Creates `AJOnRepeat` playlist with tracks you play 5+ times in recent months.

**Configuration:**
- `ENABLE_REPEAT_PLAYLISTS=true` - Enable feature
- `PLAYLIST_PREFIX_REPEAT=OnRepeat` - Playlist prefix

## Updated Notebooks

### Notebook 01: Sync Data
- ✅ Added streaming history sync section
- ✅ Shows streaming history file in saved files list

### Notebook 02: Analyze Library
- 📝 **To Add:** Streaming history comparison section
  - Compare library tracks vs. actually played tracks
  - Show discovery rate (listened but not saved)
  - Show unused library rate (saved but never played)

### Notebook 03: Playlist Analysis
- 📝 **To Add:** Listening-based genre analysis
  - Which genres you actually listen to most
  - Genre listening patterns over time

### Notebook 04: Monthly Playlists
- 📝 **To Add:** Most played playlist creation option
  - Preview most played tracks for each month
  - Create most played playlists manually

### Notebook 05: Redundant Playlists
- 📝 **To Add:** Listening-based redundancy detection
  - Identify playlists with similar listening patterns
  - Find "dead" playlists (never actually played from)
  - Weight redundancy by actual listening frequency

## Data Schema

Streaming history is saved as `data/streaming_history.parquet` with columns:
- `timestamp` - When the track was played
- `artist_name` - Artist name
- `track_name` - Track name
- `minutes_played` - How long it was played
- `date`, `hour`, `day_of_week`, `month` - Temporal features
- `track_id` - Spotify track ID (if available)
- `source` - 'basic' or 'extended'

## API Reference

### `spotim8.streaming_history` Module

```python
from spotim8.streaming_history import (
    sync_streaming_history,
    load_streaming_history,
    consolidate_streaming_history
)

# Sync from export folders
history_df = sync_streaming_history(
    account_data_dir=Path("Spotify Account Data"),
    extended_history_dir=Path("Spotify Extended Streaming History"),
    data_dir=Path("data"),
    force=False  # Set True to re-sync
)

# Load existing synced data
history_df = load_streaming_history(Path("data"))
```

## Cron Job Integration

All new features work automatically with cron jobs. The `scripts/sync.py` script:
1. Syncs streaming history automatically (if export folders exist)
2. Creates/updates most played playlists (if enabled)
3. Creates/updates time-based playlists (if enabled)
4. Creates/updates repeat playlists (if enabled)

No additional cron configuration needed - just set the environment variables!

## Troubleshooting

### "No streaming history data available"
- Ensure export folders are in project root
- Check folder names match exactly: `Spotify Account Data` and `Spotify Extended Streaming History`
- Verify JSON files exist in those folders

### "Could not find track" warnings
- Some tracks may not be found via search (removed, renamed, etc.)
- This is normal - script continues with tracks it can find

### Playlists not updating
- Check feature flags in `.env` file
- Verify streaming history synced successfully
- Check cron job logs: `logs/sync.log`

## Future Enhancements

Planned features (not yet implemented):
- Discovery playlists (searched but not saved)
- Skip rate analysis for playlist quality
- Temporal redundancy detection
- Technical log analysis

See `notebooks/04_analyze_listening_history.ipynb` for detailed analysis and ideas.

