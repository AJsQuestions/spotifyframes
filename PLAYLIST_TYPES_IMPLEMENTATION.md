# Playlist Types Implementation

## Overview

The spotim8 project now supports **5 different playlist types**, each with monthly and yearly formats:

1. **Finds** (monthly prefix) - Liked songs from each month
2. **Top** (most_played prefix) - Most played tracks from streaming history
3. **Vibes** (time_based prefix) - Time-based tracks (morning, afternoon, evening, night, weekend)
4. **OnRepeat** (repeat prefix) - Tracks played multiple times
5. **Discover** (discovery prefix) - Newly discovered tracks (first time played)

## Monthly Playlists (Last 3 Months)

All playlist types create monthly playlists for the **last 3 months only**:

- `AJFindsNov25` - Finds (liked songs)
- `AJTopNov25` - Most played tracks
- `AJVBZNov25` - Time-based tracks (evening by default)
- `AJRPTNov25` - On repeat tracks
- `AJDscvrNov25` - Newly discovered tracks

## Yearly Consolidation

Older months (beyond the last 3) are automatically consolidated into yearly playlists:

- `AJFinds24` - All liked songs from 2024
- `AJTop24` - Most played tracks from 2024
- `AJVBZ24` - Time-based tracks from 2024
- `AJRPT24` - On repeat tracks from 2024
- `AJDscvr24` - Newly discovered tracks from 2024

## Data Sources

### Finds Playlists
- **Source**: Liked Songs (from Spotify API)
- **Data**: `playlist_tracks.parquet`
- **Logic**: Tracks added to Liked Songs in each month

### Top/Most Played Playlists
- **Source**: Streaming History
- **Data**: `streaming_history.parquet`
- **Logic**: Tracks sorted by play count and total duration

### Vibes/Time-Based Playlists
- **Source**: Streaming History
- **Data**: `streaming_history.parquet`
- **Logic**: Tracks played during specific times:
  - Morning: 6 AM - 12 PM
  - Afternoon: 12 PM - 6 PM
  - Evening: 6 PM - 12 AM (default)
  - Night: 12 AM - 6 AM
  - Weekend: Saturday & Sunday

### OnRepeat Playlists
- **Source**: Streaming History
- **Data**: `streaming_history.parquet`
- **Logic**: Tracks played at least 3 times in the period

### Discover Playlists
- **Source**: Streaming History
- **Data**: `streaming_history.parquet`
- **Logic**: Tracks played for the first time in the period

## Configuration

All playlist types can be configured via `.env`:

```bash
# Prefixes
PLAYLIST_PREFIX_MONTHLY=Finds
PLAYLIST_PREFIX_MOST_PLAYED=Top
PLAYLIST_PREFIX_TIME_BASED=VBZ
PLAYLIST_PREFIX_REPEAT=RPT
PLAYLIST_PREFIX_DISCOVERY=Dscvr

# Retention (how many months to keep as monthly)
KEEP_MONTHLY_MONTHS=3
```

## Functions

### Track Generation Functions

- `get_most_played_tracks(history_df, month_str, limit=50)` - Most played tracks
- `get_time_based_tracks(history_df, month_str, time_type="evening", limit=50)` - Time-based tracks
- `get_repeat_tracks(history_df, month_str, min_repeats=3, limit=50)` - On repeat tracks
- `get_discovery_tracks(history_df, month_str, limit=50)` - Newly discovered tracks

### Playlist Management

- `update_monthly_playlists(sp, keep_last_n_months=3)` - Creates/updates monthly playlists for all types
- `consolidate_old_monthly_playlists(sp, keep_last_n_months=3)` - Consolidates older months into yearly playlists
- `create_or_update_playlist(...)` - Helper function with duplicate prevention

## Duplicate Prevention

- All playlist creation checks for existing playlists by name
- Only adds new tracks, never removes existing tracks
- Manually added tracks are preserved

## Creation Dates

- Playlists are created with period end dates calculated (last day of month/year)
- **Note**: Spotify API doesn't support setting creation dates directly
- Dates are calculated for reference but playlists will have current timestamp

## Example Output

If today is January 2025:

**Monthly Playlists (Last 3 Months):**
- `AJFindsNov24`, `AJFindsDec24`, `AJFindsJan25`
- `AJTopNov24`, `AJTopDec24`, `AJTopJan25`
- `AJVBZNov24`, `AJVBZDec24`, `AJVBZJan25`
- `AJRPTNov24`, `AJRPTDec24`, `AJRPTJan25`
- `AJDscvrNov24`, `AJDscvrDec24`, `AJDscvrJan25`

**Yearly Playlists (Consolidated):**
- `AJFinds24`, `AJFinds23`, etc.
- `AJTop24`, `AJTop23`, etc.
- `AJVBZ24`, `AJVBZ23`, etc.
- `AJRPT24`, `AJRPT23`, etc.
- `AJDscvr24`, `AJDscvr23`, etc.

## Requirements

- Streaming history data (`streaming_history.parquet`) for Top/Vibes/OnRepeat/Discover playlists
- Liked songs data (`playlist_tracks.parquet`) for Finds playlists
- Both are automatically synced via `sync_all_export_data()` and `sync_full_library()`

