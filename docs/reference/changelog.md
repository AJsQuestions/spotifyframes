# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [4.0.0] - 2025-01-22

### 🎉 Major Release: Production-Grade Features & Creative Enhancements

### 🎨 Creative Features (NEW)
- **Theme-Based Playlists** - Generate playlists for workout, study, chill, party, roadtrip
- **Time Capsule Playlists** - Create playlists from specific years
- **"On This Day" Playlists** - See what you listened to on this date in previous years
- **Smart Playlist Mixing** - Intelligently mix multiple playlists with different strategies
- **Listening Insights Report** - Comprehensive reports with visual formatting
- **Playlist Intelligence** - Similarity detection, merge suggestions, health scores
- **Creative CLI** - Interactive command-line interface for creative features

### 🎵 Advanced Genre Classification (NEW)
- **Multi-Dimensional Classification** - Uses collaborative filtering, playlist co-occurrence, artist networks, and temporal patterns
- **Collaborative Filtering** - Infers genres from similar tracks (shared artists, same playlists)
- **Playlist Co-occurrence** - Tracks appearing together frequently share genre signals
- **Artist Network Analysis** - Uses collaboration patterns to infer genres
- **Temporal Patterns** - Genre evolution over time based on release years
- **Genre Discovery** - Discovers genre clusters, hybrids, and emerging trends
- **Dynamic Learning** - Learns genre patterns from your library and playlists
- **Hybrid Detection** - Identifies tracks that blend multiple genres
- **Emerging Genres** - Tracks trending genres in your library over time

### 🛡️ Data Protection (NEW)
- **Automatic Backups** - All destructive operations create backups automatically
- **Verification Before Deletion** - Tracks verified in target before source deletion
- **Safe Track Removal** - Protected track removal with backup and validation
- **Zero Data Loss Guarantee** - Operations abort if verification fails
- **Backup Management** - Tools to list, restore, and cleanup backups
- **Recovery System** - Restore playlists from backups if needed

### ✨ Playlist Aesthetics (NEW)
- **Rich Descriptions** - Auto-generated descriptions with statistics, genres, and metadata
- **Playlist Statistics** - Track count, duration, popularity, year range, top artists
- **Enhanced Formatting** - Professional, informative playlist descriptions
- **Cover Image Recommendations** - Smart strategies for playlist artwork

### 🏥 Organization Tools (NEW)
- **Health Check Script** - Comprehensive library health analysis
- **Playlist Categorization** - Automatic categorization (automated, manual, genre, etc.)
- **Empty Playlist Detection** - Find playlists with no tracks
- **Stale Playlist Detection** - Identify playlists not updated recently
- **Duplicate Detection** - Find duplicate tracks within playlists
- **Organization Reports** - Detailed metrics and recommendations

### 🛡️ Production Infrastructure (NEW)
- **Error Handling** - Robust error handling with decorators and retries
- **Structured Logging** - Comprehensive logging with file rotation
- **Configuration Validation** - Automatic validation of environment setup
- **Custom Exceptions** - Better error types for debugging

### Changed
- **Enhanced Sync Script** - Now includes optional health checks after sync
- **Protected Operations** - All merge/delete operations use safe deletion
- **Playlist Descriptions** - Automatically enhanced with rich statistics (if enabled)

---

## [3.0.0] - 2025-01-18

### 🎉 Major Release: Smart Genre Management & Enhanced Automation

### Added

#### Smart Genre Tag Management
- **Automatic Genre Tag Removal** - When tracks are manually removed from genre master playlists, their genre tags are automatically removed from the track's stored genres
- **Genre Master Playlist Cleanup** - Genre master playlists now automatically remove tracks that don't match the genre (prevents accumulation of incorrect tracks)
- **Incremental Sync After Write Operations** - Automatic incremental sync triggered after playlist modifications (controlled by `AUTO_SYNC_AFTER_WRITE` environment variable)

#### Enhanced Emoji Diversity
- **Updated Genre Emojis** - More diverse and culturally appropriate emoji selection for genre tags
- **Removed Problematic Emojis** - Replaced stereotypical emojis with more inclusive alternatives (e.g., Latin genre emoji updated)

### Changed

#### Genre Master Playlist Behavior
- **Automatic Track Removal** - Genre master playlists now remove tracks that don't match the genre (only for liked songs, preserves manually added non-liked tracks)
- **Improved Genre Matching** - Better detection of tracks that should be in genre playlists vs. tracks that were manually added

#### Automation Improvements
- **Post-Write Sync Integration** - Playlist merge and modification scripts now trigger incremental syncs automatically
- **Sync Helper Module** - New `src/scripts/common/sync_helpers.py` module for shared sync functionality

### Fixed

- **Genre Master Playlist Overpopulation** - Fixed issue where genre master playlists would accumulate all liked songs instead of only genre-matching tracks
- **Genre Tag Persistence** - Fixed issue where genre tags would persist even after tracks were removed from genre playlists
- **Emoji Consistency** - Updated emoji mapping to be more consistent and diverse across all genres

### Technical Improvements

- **Better Error Handling** - Improved error handling in playlist update operations
- **Code Organization** - Better separation of concerns in playlist update logic
- **Documentation** - Updated documentation for new genre management features

## [3.0.0] - 2025-01-XX

### 🎉 Major Release: Project Reorganization & Structure Improvements

### Changed

#### Project Structure Reorganization
- **Scripts Reorganized** - All scripts now organized into logical subdirectories:
  - `scripts/automation/` - Sync, cron, and automation scripts
  - `scripts/playlist/` - Playlist management and manipulation scripts
  - `scripts/utils/` - Utility and setup scripts
- **Improved Organization** - Better separation of concerns and easier navigation
- **Updated Path References** - All documentation and scripts updated to reflect new structure

#### Script Organization
- **Automation Scripts** (`scripts/automation/`):
  - `sync.py` - Main sync & playlist update script
  - `runner.py` - Local sync runner wrapper
  - `cron_wrapper.sh` - Robust cron wrapper
  - `cron.sh` - Cron job setup helper
  - `check_cron.sh` - Cron diagnostic tool
  - `email_notify.py` - Email notification service
- **Playlist Scripts** (`scripts/playlist/`):
  - `merge_playlists.py` - Merge two playlists
  - `merge_multiple_playlists.py` - Merge multiple playlists
  - `merge_to_new_playlist.py` - Merge to new playlist
  - `delete_playlists.py` - Delete playlists
  - `add_genre_tags_to_descriptions.py` - Add genre tags to descriptions
  - `update_all_playlist_descriptions.py` - Update all playlist descriptions
  - `playlist_helpers.py` - Shared playlist utilities
- **Utility Scripts** (`scripts/utils/`):
  - `get_token.py` - Get refresh token for automation
  - `setup.py` - Initial setup helper

### Removed

- **Test Notebooks** - Removed `06_identify_redundant_playlists_test.ipynb` (test file)

### Fixed

- **Path References** - Updated all script paths in documentation and helper scripts
- **Cron Scripts** - Fixed path references in cron wrapper and setup scripts
- **Dynamic Path Resolution** - Improved path resolution in shell scripts for better portability

### Documentation

- **Updated README** - All script paths updated to reflect new organization
- **Project Structure** - Updated project structure documentation with new organization
- **Migration Guide** - Script paths updated throughout documentation

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

