# Playlist Prefix Configuration Guide

## Overview

The spotim8 project now supports **extended prefix options** for different types of playlists. You can customize prefixes and templates for each playlist type independently.

## Configuration

All settings are configured via environment variables in your `.env` file. See `env.example` for the full list.

## Playlist Types & Prefixes

### 1. Monthly Playlists
**Default Prefix:** `Finds`  
**Example:** `AJFindsDec25`  
**Config:** `PLAYLIST_PREFIX_MONTHLY`

### 2. Genre-Split Monthly Playlists
**Default Prefix:** `Finds`  
**Example:** `HipHopFindsDec25`, `DanceFindsDec25`, `OtherFindsDec25`  
**Config:** `PLAYLIST_PREFIX_GENRE_MONTHLY`


### 4. Master Genre Playlists
**Default Prefix:** `am`  
**Example:** `AJamHip-Hop`, `AJamElectronic`  
**Config:** `PLAYLIST_PREFIX_GENRE_MASTER`

### 5. Most Played Playlists
**Default Prefix:** `Top`  
**Example:** `AJTopDec25` → `AJTop24` (yearly)  
**Config:** `PLAYLIST_PREFIX_MOST_PLAYED`

### 6. Time-Based Playlists
**Status:** ❌ **REMOVED** - Vibes playlists no longer supported  
**Config:** `PLAYLIST_PREFIX_TIME_BASED` (deprecated)

### 7. Repeat/Comfort Zone Playlists
**Status:** ❌ **REMOVED** - OnRepeat playlists no longer supported  
**Config:** `PLAYLIST_PREFIX_REPEAT` (deprecated)

### 8. Discovery Playlists
**Default Prefix:** `Dscvr`  
**Example:** `AJDscvrDec25` → `AJDscvr24` (yearly)  
**Config:** `PLAYLIST_PREFIX_DISCOVERY`

## Template Customization

You can also customize the **entire naming format** using templates:

### Available Placeholders
- `{owner}` - Your owner name (from `PLAYLIST_OWNER_NAME`)
- `{prefix}` - The prefix for this playlist type
- `{mon}` - Month abbreviation (Jan, Feb, etc.)
- `{year}` - 2-digit year (24, 25, etc.)
- `{genre}` - Genre name (HipHop, Dance, etc.)
- `{type}` - Type name (Morning, Evening, Weekend)

### Template Variables

- `PLAYLIST_TEMPLATE_MONTHLY` - Format for monthly playlists
- `PLAYLIST_TEMPLATE_YEARLY` - Format for yearly playlists
- `PLAYLIST_TEMPLATE_GENRE_MONTHLY` - Format for genre-split monthly
- `PLAYLIST_TEMPLATE_GENRE_MASTER` - Format for master genre playlists
- `PLAYLIST_TEMPLATE_MOST_PLAYED` - Format for most played playlists
- `PLAYLIST_TEMPLATE_TIME_BASED` - Format for time-based playlists
- `PLAYLIST_TEMPLATE_REPEAT` - Format for repeat playlists
- `PLAYLIST_TEMPLATE_DISCOVERY` - Format for discovery playlists

## Examples

### Example: Current Default Configuration
```bash
PLAYLIST_OWNER_NAME=AJ
PLAYLIST_PREFIX_MONTHLY=Finds
PLAYLIST_PREFIX_MOST_PLAYED=Top
PLAYLIST_PREFIX_TIME_BASED=VBZ
PLAYLIST_PREFIX_REPEAT=RPT
PLAYLIST_PREFIX_DISCOVERY=Dscvr
KEEP_MONTHLY_MONTHS=3
```

**Results (if today is January 2025):**
- Monthly (last 3 months): `AJFindsNov24`, `AJFindsDec24`, `AJFindsJan25`
- Top: `AJTop24` (yearly only)
- Discovery: `AJDscvr24` (yearly only)
- Yearly (consolidated): `AJFinds24`, `AJTop24`, `AJDscvr24` (VBZ/RPT removed)


## How It Works

1. **Monthly Playlists**: Created for the last 3 months (configurable)
   - Finds: Liked songs from each month
   - Top: Most played tracks from streaming history
   - Dscvr: Newly discovered tracks (VBZ/RPT removed from yearly)

2. **Yearly Consolidation**: Older months automatically consolidated
   - Monthly playlists older than 3 months are deleted
   - Tracks are consolidated into yearly playlists
   - Only **Finds**, **Top**, and **Discovery** playlists are kept for yearly consolidation
   - Genre splits (HipHop, Dance, Other) created for Finds playlists only

## Migration

Existing playlists will continue to work. When you change prefixes:
- **New playlists** will use the new prefix
- **Existing playlists** keep their current names
- The sync script will find existing playlists by name and update them

## See Also

- `env.example` - Full configuration reference
- `scripts/sync.py` - Implementation details
- `README.md` - General project documentation

