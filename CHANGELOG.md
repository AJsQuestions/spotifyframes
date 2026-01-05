# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2025-01-XX

### 🎉 Major Release: Streaming History Integration & Enhanced Playlist Management

### Added

#### Streaming History Integration
- **New `streaming_history.py` module** - Complete integration with Spotify data exports
  - Loads and processes Spotify Account Data and Extended Streaming History
  - Consolidates multiple data sources into unified parquet format
  - Functions: `sync_streaming_history()`, `load_streaming_history()`, `sync_all_export_data()`
  - Support for search queries, wrapped data, follow data, library snapshots, playback errors/retries, and web API events

#### Enhanced Playlist Types
- **5 Playlist Types** with monthly and yearly formats:
  1. **Finds** - Liked songs from each month (from API)
  2. **Top** - Most played tracks from streaming history
  3. **Vibes** - Time-based tracks (morning, evening, weekend) - *Deprecated in v2*
  4. **OnRepeat** - Tracks played multiple times - *Deprecated in v2*
  5. **Discover** - Newly discovered tracks (first time played)
- **Automatic Monthly Retention** - Keeps last 3 months as monthly playlists, consolidates older months into yearly playlists
- **Genre-Split Playlists** - Automatic genre-based splitting for Finds playlists (HipHop, Dance, Other)
- **Master Genre Playlists** - All-time playlists by genre (e.g., `AJamHip-Hop`)

#### Enhanced Analysis Notebooks
- **Notebook 04: Analyze Listening History** - Comprehensive analysis of actual listening patterns
- **Notebook 05: Liked Songs Monthly Playlists** - Enhanced with streaming history integration
- **Notebook 06: Identify Redundant Playlists** - Listening-based redundancy detection
- **Notebook 07: Analyze Crashes** - Technical log analysis

#### Configuration & Customization
- **Extended Environment Variables** - Comprehensive `.env` configuration:
  - Per-playlist-type enable/disable flags
  - Customizable prefixes for each playlist type
  - Template-based playlist naming (supports placeholders: `{owner}`, `{prefix}`, `{mon}`, `{year}`, `{genre}`)
  - Date format options (short, medium, long, numeric)
  - Separator options (none, space, dash, underscore)
  - Capitalization options (title, upper, lower, preserve)
- **Playlist Description Templates** - Customizable playlist descriptions

#### Scripts & Utilities
- **Enhanced `sync.py`** - Now handles all 5 playlist types automatically
- **Playlist Helper Scripts** - Utilities for managing playlists:
  - `delete_duplicates.py` - Remove duplicate tracks
  - `delete_incorrect_playlists.py` - Clean up incorrectly named playlists
  - `list_genre_playlists.py` - List all genre playlists
  - `playlist_helpers.py` - Shared playlist utilities

#### Documentation
- **Comprehensive Documentation**:
  - `STREAMING_HISTORY_INTEGRATION.md` - Complete integration guide
  - `PLAYLIST_TYPES_IMPLEMENTATION.md` - Playlist type system documentation
  - `PLAYLIST_PREFIXES.md` - Prefix configuration guide
  - `ENHANCEMENTS_SUMMARY.md` - Feature summary
  - `CRASH_ANALYSIS.md` - Technical log analysis guide

### Changed

- **Version bumped to 2.0.0** - Major version release
- **Playlist Management** - Improved duplicate prevention and playlist matching
- **Data Schema** - Enhanced streaming history schema with temporal features
- **Notebook Organization** - Reorganized and enhanced all analysis notebooks

### Deprecated

- **Vibes/Time-Based Playlists** - Removed from yearly consolidation (monthly only)
- **OnRepeat Playlists** - Removed from yearly consolidation (monthly only)

### Fixed

- Improved error handling in sync operations
- Better handling of missing or incomplete streaming history data
- Enhanced playlist name matching and duplicate detection

### Security

- Enhanced `.gitignore` to ensure sensitive data (`.env`, data files, logs) are never committed

## [1.0.0] - Previous Release

### Initial Release
- Core Spotify Web API integration
- Basic playlist management
- Pandas DataFrame interface
- Monthly playlist creation
- Genre classification
- Basic analysis notebooks

