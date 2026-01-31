"""
Playlist update utilities.

Functions for updating monthly, genre-split, and master genre playlists.

This module is extracted from sync.py and uses late imports to access
utilities from sync.py to avoid circular dependencies.
"""

import spotipy
import pandas as pd
from datetime import datetime

from .formatting import format_playlist_name, format_playlist_description
from src.features.genres import get_all_split_genres, get_all_broad_genres, get_broad_genre, SPLIT_GENRES, ALL_BROAD_GENRES
from .error_handling import handle_errors

@handle_errors(reraise=False, default_return={}, log_error=True)
def update_monthly_playlists(sp: spotipy.Spotify, keep_last_n_months: int = 3) -> dict:
    """Update monthly playlists for all types (Finds, Discover).
    
    Only creates/updates monthly playlists for the last N months (default: 3).
    Older months are automatically consolidated into yearly playlists.
    
    Data Sources:
    - "Finds" playlists: Use API data (liked songs) - always up-to-date
    - Top and Discovery playlists: Use streaming history from exports (Vibes/OnRepeat removed)
      - Streaming history is updated periodically and may lag behind API data
      - Recent months may be incomplete if export is outdated
      - Missing history results in empty playlists for those types
    
    Args:
        keep_last_n_months: Number of recent months to keep as monthly playlists (default: 3)
    
    Note: This function only ADDS tracks to playlists. It never removes tracks.
    Manually added tracks are preserved and will remain in the playlists.
    """
    # Late imports from sync.py
    from .sync import (
        log, verbose_log, DATA_DIR, ENABLE_MONTHLY, ENABLE_MOST_PLAYED, ENABLE_DISCOVERY,
        LIKED_SONGS_PLAYLIST_ID, MONTHLY_NAME_TEMPLATE, get_existing_playlists, get_user_info, get_playlist_tracks, api_call,
        _chunked, _update_playlist_description_with_genres, _playlist_tracks_cache
    )
    log(f"\n--- Monthly Playlists (Last {keep_last_n_months} Months Only) ---")
    
    # Log enabled playlist types
    # NOTE: Only "Finds" playlists are created monthly. Top/Dscvr are yearly only.
    enabled_types = []
    if ENABLE_MONTHLY:
        enabled_types.append("Finds (monthly)")
    if ENABLE_MOST_PLAYED:
        enabled_types.append("Top (yearly only)")
    # Vbz/Rpt removed - only Top and Discovery kept for yearly
    # if ENABLE_TIME_BASED:
    #     enabled_types.append("Vbz (yearly only)")
    # if ENABLE_REPEAT:
    #     enabled_types.append("Rpt (yearly only)")
    if ENABLE_DISCOVERY:
        enabled_types.append("Dscvr (yearly only)")
    
    if enabled_types:
        log(f"  Enabled playlist types: {', '.join(enabled_types)}")
        log(f"  📌 Note: Top/Dscvr are created as yearly playlists only (no monthly). Vbz/Rpt removed.")
    else:
        log("  ⚠️  No playlist types enabled - check .env file")
        return {}
    
    # Load streaming history for Top/Vibes/OnRepeat/Discover playlists
    # NOTE: Streaming history comes from periodic Spotify exports and may lag behind API data.
    # API data (liked songs) is always more up-to-date than streaming history exports.
    # If streaming history is missing or incomplete, these playlist types will be empty or incomplete.
    from src.analysis.streaming_history import load_streaming_history
    history_df = load_streaming_history(DATA_DIR)
    if history_df is not None and not history_df.empty:
        # Ensure timestamp is datetime
        if 'timestamp' in history_df.columns:
            history_df['timestamp'] = pd.to_datetime(history_df['timestamp'], errors='coerce', utc=True)
        
        # Check data freshness - warn if streaming history is significantly behind
        # Streaming history comes from periodic exports, so it may lag behind API data
        if 'timestamp' in history_df.columns:
            try:
                latest_history = history_df['timestamp'].max()
                if pd.notna(latest_history):
                    # Convert to naive datetime for comparison if needed
                    if latest_history.tzinfo:
                        latest_naive = latest_history.replace(tzinfo=None)
                        now = datetime.now()
                    else:
                        latest_naive = latest_history
                        now = datetime.now()
                    
                    days_behind = (now - latest_naive).days
                    if days_behind > 30:
                        latest_str = latest_history.strftime('%Y-%m-%d') if hasattr(latest_history, 'strftime') else str(latest_history)
                        log(f"  ⚠️  Streaming history is {days_behind} days old (latest: {latest_str})")
                        log(f"      Recent months may be incomplete. Export new data for up-to-date playlists.")
            except Exception:
                pass  # Skip freshness check if there's an error
        
        log(f"  Loaded streaming history: {len(history_df):,} records")
    else:
        log("  ⚠️  No streaming history found - Discovery playlists will be empty")
        log("      Export streaming history data to enable these playlist types")
    
    # Load liked songs data for "Finds" playlists (API data only - never uses streaming history)
    playlist_tracks_path = DATA_DIR / "playlist_tracks.parquet"
    all_month_to_tracks = {}
    
    if playlist_tracks_path.exists():
        library = pd.read_parquet(playlist_tracks_path)
        liked = library[library["playlist_id"].astype(str) == LIKED_SONGS_PLAYLIST_ID].copy()
        
        if not liked.empty:
            # Parse timestamps
            added_col = None
            for col in ["added_at", "playlist_added_at", "track_added_at"]:
                if col in liked.columns:
                    added_col = col
                    break
            
            if added_col:
                liked[added_col] = pd.to_datetime(liked[added_col], errors="coerce", utc=True)
                liked["month"] = liked[added_col].dt.to_period("M").astype(str)
                
                # Handle both track_uri and track_id columns
                if "track_uri" in liked.columns:
                    liked["_uri"] = liked["track_uri"]
                else:
                    liked["_uri"] = liked["track_id"].map(_to_uri)
                
                # Build month -> tracks mapping for "Finds" playlists (API data only)
                for month, group in liked.groupby("month"):
                    uris = group["_uri"].dropna().tolist()
                    seen = set()
                    unique = [u for u in uris if not (u in seen or seen.add(u))]
                    all_month_to_tracks[month] = {"monthly": unique}
                
                log(f"  Loaded liked songs (API data) for 'Finds' playlists: {len(all_month_to_tracks)} month(s)")
        else:
            log("  ⚠️  No liked songs found in library data - 'Finds' playlists will be empty")
    else:
        log("  ⚠️  Library data not found - 'Finds' playlists will be empty (run full sync first)")
    
    # Get months for "Finds" playlists (API data only - liked songs)
    finds_months = set(all_month_to_tracks.keys())
    
    # Get months for other playlist types (streaming history)
    history_months = set()
    if history_df is not None and not history_df.empty:
        history_df['month'] = history_df['timestamp'].dt.to_period('M').astype(str)
        history_months = set(history_df['month'].unique())
    
    # For "Finds" playlists, only use months from API data (liked songs)
    # For Discovery playlists, use months from streaming history (Top/Vibes removed)
    # Combine for processing, but "Finds" will only use API data
    all_months = finds_months | history_months
    
    # Filter to only the last N months
    if all_months:
        sorted_months = sorted(all_months)
        recent_months = sorted_months[-keep_last_n_months:]
        older_months = [m for m in sorted_months if m not in recent_months]
        if older_months:
            log(f"📅 Keeping {len(recent_months)} recent months as monthly playlists: {', '.join(recent_months)}")
            log(f"📦 {len(older_months)} older months will be consolidated into yearly playlists")
            if finds_months:
                finds_recent = [m for m in recent_months if m in finds_months]
                log(f"   📌 'Finds' playlists will use API data (liked songs) for {len(finds_recent)} month(s)")
    else:
        recent_months = []
    
    if not recent_months:
        log("No months to process")
        return {}
    
    log(f"Processing {len(recent_months)} month(s) for all playlist types...")
    
    # Get existing playlists (cached)
    existing = get_existing_playlists(sp)
    user = get_user_info(sp)
    user_id = user["id"]
    
    # Define playlist types and their configurations
    # "Finds" playlists use API data (liked songs) only - never streaming history
    # Other playlists use streaming history data
    # Only include playlist types that are enabled in .env
    # NOTE: Dscvr is created as yearly playlists only (no monthly). Top/Vbz/Rpt removed.
    # Only "Finds" playlists are created monthly
    playlist_configs = []
    
    if ENABLE_MONTHLY:
        playlist_configs.append((
            "monthly", MONTHLY_NAME_TEMPLATE, "Liked songs", 
            lambda m: all_month_to_tracks.get(m, {}).get("monthly", [])  # API data only
        ))
    
    # Top/Vbz/Rpt/Dscvr are NOT created as monthly playlists - only yearly
    # They are created in consolidate_old_monthly_playlists() for all years with streaming history
    
    if not playlist_configs:
        log("⚠️  All playlist types are disabled in .env file. No playlists will be created.")
        return {}
    
    month_to_tracks = {}
    
    for month in sorted(recent_months):
        month_to_tracks[month] = {}
        
        for playlist_type, template, description, get_tracks_fn in playlist_configs:
            # Get tracks for this playlist type and month
            track_uris = get_tracks_fn(month)
            
            if not track_uris:
                continue
            
            month_to_tracks[month][playlist_type] = track_uris
            
            # Format playlist name (all types use monthly format for monthly playlists)
            name = format_playlist_name(template, month, playlist_type=playlist_type)
            
            # Check for duplicate
            if name in existing:
                pid = existing[name]
                already = get_playlist_tracks(sp, pid)
                to_add = [u for u in track_uris if u not in already]
                
                if to_add:
                    for chunk in _chunked(to_add, 50):
                        api_call(sp.playlist_add_items, pid, chunk)
                    if pid in _playlist_tracks_cache:
                        del _playlist_tracks_cache[pid]
                    log(f"  {name}: +{len(to_add)} tracks ({len(track_uris)} total)")
                    # Update description with genre tags
                    _update_playlist_description_with_genres(sp, user_id, pid, track_uris)
                else:
                    log(f"  {name}: up to date ({len(track_uris)} tracks)")
                    # Still update genre tags even if no new tracks (genres might have changed in data)
                    _update_playlist_description_with_genres(sp, user_id, pid, track_uris)
            else:
                # Calculate last date of the month for creation date reference
                from calendar import monthrange
                year, month_num = map(int, month.split("-"))
                last_day = monthrange(year, month_num)[1]
                created_at = datetime(year, month_num, last_day, 23, 59, 59)
                
                # Create playlist
                verbose_log(f"Creating new playlist '{name}' for {month} (type={playlist_type})...")
                pl = api_call(
                    sp.user_playlist_create,
                    user_id,
                    name,
                    public=False,
                    description=format_playlist_description(description, period=month, playlist_type=playlist_type),
                )
                pid = pl["id"]
                verbose_log(f"  Created playlist '{name}' with id {pid}")
                
                # Add tracks
                verbose_log(f"  Adding {len(track_uris)} tracks in chunks...")
                chunk_count = 0
                for chunk in _chunked(track_uris, 50):
                    chunk_count += 1
                    verbose_log(f"    Adding chunk {chunk_count} ({len(chunk)} tracks)...")
                    api_call(sp.playlist_add_items, pid, chunk)
                
                # Update description with genre tags
                _update_playlist_description_with_genres(sp, user_id, pid, track_uris)
                
                _invalidate_playlist_cache()
                verbose_log(f"  Invalidated playlist cache after creating new playlist")
                log(f"  {name}: created with {len(track_uris)} tracks")
    
    return month_to_tracks




@handle_errors(reraise=False, default_return=None, log_error=True)
def update_genre_split_playlists(sp: spotipy.Spotify, month_to_tracks: dict) -> None:
    """Update genre-split monthly playlists (HipHop, Dance, Other).
    
    Note: This function only ADDS tracks from liked songs. It never removes tracks.
    Manually added tracks are preserved and will remain in the playlists.
    """
    # Late imports from sync.py
    from .sync import (
        log, verbose_log, DATA_DIR, ENABLE_MONTHLY, ENABLE_MOST_PLAYED, ENABLE_DISCOVERY,
        LIKED_SONGS_PLAYLIST_ID, GENRE_MONTHLY_TEMPLATE, get_existing_playlists, get_user_info, get_playlist_tracks, api_call,
        _chunked, _update_playlist_description_with_genres, _playlist_tracks_cache,
        _parse_genres, _get_all_track_genres
    )
    if not month_to_tracks:
        return
    
    log("\n--- Genre-Split Playlists ---")
    
    # Load genre data
    track_artists = pd.read_parquet(DATA_DIR / "track_artists.parquet")
    artists = pd.read_parquet(DATA_DIR / "artists.parquet")
    
    artist_genres_map = artists.set_index("artist_id")["genres"].to_dict()
    
    # Build track -> genres mapping (tracks can have multiple genres)
    # Try to use stored track genres first
    track_to_genres = {}
    tracks_df = pd.read_parquet(DATA_DIR / "tracks.parquet")
    if "genres" in tracks_df.columns:
        # Use stored track genres
        for _, track_row in tracks_df.iterrows():
            track_id = track_row["track_id"]
            uri = f"spotify:track:{track_id}"
            stored_genres = _parse_genres(track_row.get("genres"))
            if stored_genres:
                split_genres = get_all_split_genres(stored_genres)
                if split_genres:
                    track_to_genres[uri] = split_genres
    
    # Fill in missing using artist data
    all_uris = set(u for uris in month_to_tracks.values() for u in uris)
    track_ids = {u.split(":")[-1] for u in all_uris if u.startswith("spotify:track:")}
    
    for track_id in track_ids:
        uri = f"spotify:track:{track_id}"
        if uri in track_to_genres:
            continue  # Already have from stored data
        
        # Get all genres from all artists on this track
        all_track_genres = _get_all_track_genres(track_id, track_artists, artist_genres_map)
        split_genres = get_all_split_genres(all_track_genres)
        if split_genres:
            track_to_genres[uri] = split_genres
    
    # Get existing playlists (cached)
    existing = get_existing_playlists(sp)
    user = get_user_info(sp)
    user_id = user["id"]
    
    for month, uris in sorted(month_to_tracks.items()):
        for genre in SPLIT_GENRES:
            # Tracks can match multiple genres, check if this genre is in the list
            genre_uris = [u for u in uris if genre in track_to_genres.get(u, [])]
            
            if not genre_uris:
                continue
            
            name = format_playlist_name(GENRE_MONTHLY_TEMPLATE, month, genre, playlist_type="genre_monthly")
            
            if name in existing:
                pid = existing[name]
                # Get existing tracks (includes both auto-added and manually added tracks)
                already = get_playlist_tracks(sp, pid)
                # Only add tracks that aren't already present (preserves manual additions)
                to_add = [u for u in genre_uris if u not in already]

                if to_add:
                    verbose_log(f"Adding {len(to_add)} tracks to playlist '{name}' (playlist_id={pid})")
                    chunk_count = 0
                    for chunk in _chunked(to_add, 50):
                        chunk_count += 1
                        verbose_log(f"  Adding chunk {chunk_count} ({len(chunk)} tracks)...")
                        api_call(sp.playlist_add_items, pid, chunk)
                    # Invalidate cache for this playlist since we added tracks
                    if pid in _playlist_tracks_cache:
                        del _playlist_tracks_cache[pid]
                        verbose_log(f"  Invalidated cache for playlist {pid}")
                    log(f"  {name}: +{len(to_add)} tracks (manually added tracks preserved)")
                    # Update description with genre tags (use all tracks in playlist)
                    _update_playlist_description_with_genres(sp, user_id, pid, None)
            else:
                pl = api_call(
                    sp.user_playlist_create,
                    user_id,
                    name,
                    public=False,
                    description=format_playlist_description(f"{genre} tracks", period=month, genre=genre, playlist_type="genre_monthly"),
                )
                pid = pl["id"]

                for chunk in _chunked(genre_uris, 50):
                    api_call(sp.playlist_add_items, pid, chunk)
                # Update description with genre tags
                _update_playlist_description_with_genres(sp, user_id, pid, genre_uris)
                # Invalidate playlist cache since we created a new playlist
                _invalidate_playlist_cache()
                log(f"  {name}: created with {len(genre_uris)} tracks")




def _remove_genre_from_track(tracks_df: pd.DataFrame, track_uri: str, genre_to_remove: str) -> bool:
    """Remove a genre tag from a track's stored genres.
    
    Args:
        tracks_df: DataFrame with tracks data (will be modified in place)
        track_uri: Track URI (e.g., "spotify:track:abc123")
        genre_to_remove: Genre name to remove from track
    
    Returns:
        True if genre was removed, False otherwise
    """
    from .sync import (
        log, verbose_log, DATA_DIR, ENABLE_MONTHLY, ENABLE_MOST_PLAYED, ENABLE_DISCOVERY,
        LIKED_SONGS_PLAYLIST_ID, get_playlist_tracks, api_call,
        _chunked, _update_playlist_description_with_genres, _playlist_tracks_cache
    )
    
    # Extract track_id from URI
    if not track_uri.startswith("spotify:track:"):
        return False
    track_id = track_uri.split(":")[-1]
    
    # Find the track in the dataframe
    track_mask = tracks_df["track_id"] == track_id
    if not track_mask.any():
        return False
    
    track_idx = tracks_df[track_mask].index[0]
    current_genres = _parse_genres(tracks_df.at[track_idx, "genres"])
    
    if not current_genres:
        return False
    
    # Remove the genre (case-insensitive comparison)
    genre_to_remove_lower = genre_to_remove.lower()
    updated_genres = [g for g in current_genres if g.lower() != genre_to_remove_lower]
    
    # Only update if something changed
    if len(updated_genres) != len(current_genres):
        tracks_df.at[track_idx, "genres"] = updated_genres if updated_genres else []
        return True
    
    return False


@handle_errors(reraise=False, default_return=None, log_error=True)
def update_master_genre_playlists(sp: spotipy.Spotify) -> None:
    """
    Update master genre playlists with tracks from liked songs.
    
    Runs on every sync and updates the partition incrementally:
    - New liked songs are categorized (using artist + track genres) and assigned to
      exactly one master genre playlist (or "Other" if unclassified).
    - Tracks that are no longer liked are removed from genre playlists so the
      partition stays in sync with the current liked library.
    
    Creates EXHAUSTIVE playlists that partition the entire library of liked songs
    by genre. Every liked song is in exactly one playlist; unliked tracks are
    removed so the partition reflects current likes only.
    
    Args:
        sp: Authenticated Spotify client
    
    Returns:
        None
    """
    # Late imports from sync.py
    from .sync import (
        log, verbose_log, DATA_DIR, ENABLE_MONTHLY, ENABLE_MOST_PLAYED, ENABLE_DISCOVERY,
        LIKED_SONGS_PLAYLIST_ID, GENRE_NAME_TEMPLATE,
        get_existing_playlists, get_user_info, get_playlist_tracks, api_call,
        _chunked, _update_playlist_description_with_genres, _playlist_tracks_cache,
        _parse_genres, _get_all_track_genres, _get_primary_artist_genres, _invalidate_playlist_cache
    )
    from collections import Counter
    log("\n--- Master Genre Playlists (Exhaustive Partitioning) ---")
    
    # Load data
    library = pd.read_parquet(DATA_DIR / "playlist_tracks.parquet")
    track_artists = pd.read_parquet(DATA_DIR / "track_artists.parquet")
    artists = pd.read_parquet(DATA_DIR / "artists.parquet")
    
    # Get liked songs
    liked = library[library["playlist_id"].astype(str) == LIKED_SONGS_PLAYLIST_ID]
    liked_ids = set(liked["track_id"])
    
    # Build URIs - ensure we have a set for fast lookup
    if "track_uri" in liked.columns:
        liked_uris = set(liked["track_uri"].dropna().tolist())
        liked_uris_list = list(liked_uris)  # Keep list version for iteration
    else:
        liked_uris_list = [f"spotify:track:{tid}" for tid in liked_ids]
        liked_uris = set(liked_uris_list)
    
    # Build genre mapping - tracks can have MULTIPLE broad genres
    # Use ONLY actual Spotify artist genres (lowercase, specific) - NO inferred genres
    # Stored track genres are split genres, not useful for broad classification
    uri_to_genres = {}  # Map URI to list of broad genres
    tracks_df = pd.read_parquet(DATA_DIR / "tracks.parquet")
    
    # Build artist genres map for fast lookup
    artist_genres_map = artists.set_index("artist_id")["genres"].to_dict()
    
    verbose_log(f"  Classifying genres for {len(liked_ids)} liked tracks (primary artist only for even distribution)...")
    
    # Count tracks with artist genres for debugging
    tracks_with_artist_genres = 0
    tracks_with_broad_genres = 0
    
    # Partition by PRIMARY ARTIST's genre only: one broad genre per track for even distribution.
    # Using all artists caused most tracks to match Hip-Hop first and pile into one playlist.
    for track_id in liked_ids:
        uri = f"spotify:track:{track_id}"
        
        # Primary artist's genres only (first artist on the track)
        primary_genres = _get_primary_artist_genres(track_id, track_artists, artist_genres_map)
        
        # Fallback: if primary has no genres, use stored track genres
        if not primary_genres and "genres" in tracks_df.columns:
            track_row = tracks_df[tracks_df["track_id"] == track_id]
            if not track_row.empty:
                stored = track_row["genres"].iloc[0]
                if stored is not None and (isinstance(stored, list) and stored or isinstance(stored, str) and str(stored).strip()):
                    primary_genres = [str(g).strip() for g in (stored if isinstance(stored, list) else [stored])]
        
        if primary_genres:
            tracks_with_artist_genres += 1
        
        # Map to exactly one broad genre (first match in GENRE_RULES order)
        broad_genre = get_broad_genre(primary_genres)
        if broad_genre:
            uri_to_genres[uri] = [broad_genre]
            tracks_with_broad_genres += 1
    
    verbose_log(f"  Tracks with artist genres: {tracks_with_artist_genres}/{len(liked_ids)} ({tracks_with_artist_genres/len(liked_ids)*100:.1f}%)")
    verbose_log(f"  Tracks with broad genres assigned: {tracks_with_broad_genres}/{len(liked_ids)} ({tracks_with_broad_genres/len(liked_ids)*100:.1f}%)")
    
    # Identify tracks without genre classification (for "Other" playlist)
    tracks_without_genres = liked_uris - set(uri_to_genres.keys())
    verbose_log(f"  Tracks without genre classification: {len(tracks_without_genres)} ({len(tracks_without_genres)/len(liked_uris)*100:.1f}%)")
    
    # Debug: Check a sample of tracks to see what genres they're getting
    if verbose_log and len(uri_to_genres) > 0:
        sample_tracks = list(uri_to_genres.items())[:10]
        verbose_log(f"  Sample track genres (primary artist, first 10):")
        for uri, genres in sample_tracks:
            track_id = uri.replace("spotify:track:", "")
            track_row = tracks_df[tracks_df["track_id"] == track_id]
            track_name = track_row["name"].iloc[0] if not track_row.empty else "Unknown"
            primary_genres = _get_primary_artist_genres(track_id, track_artists, artist_genres_map)
            verbose_log(f"    {track_name[:50]}: primary_artist_genres={primary_genres[:5]}, broad={genres}")
    
    # PARTITION APPROACH: Assign each track to exactly ONE playlist
    # If a track matches multiple genres, assign to the first in a fixed intuitive order
    # (GENRE_RULES order: Hip-Hop > R&B/Soul > Electronic > Rock > ... > Other)
    genre_counts = Counter()
    for genres_list in uri_to_genres.values():
        for genre in genres_list:
            genre_counts[genre] += 1
    
    # Fixed priority order (same as GENRE_RULES): only include genres that have tracks
    # "Other" is always last (catch-all for unclassified tracks)
    all_genres_with_tracks = [g for g in ALL_BROAD_GENRES if genre_counts.get(g, 0) > 0]
    if tracks_without_genres:
        all_genres_with_tracks.append("Other")
    
    # Assign each track to exactly ONE genre (first matching genre in priority order)
    uri_to_single_genre = {}  # Map URI to single assigned genre
    for uri, genres_list in uri_to_genres.items():
        if genres_list:
            # Assign to the highest priority genre (first in sorted list that track matches)
            for genre in all_genres_with_tracks:
                if genre in genres_list:
                    uri_to_single_genre[uri] = genre
                    break
    
    # Recalculate genre counts based on single assignments
    genre_counts_single = Counter(uri_to_single_genre.values())
    
    # Log genre distribution for debugging
    if verbose_log:
        verbose_log(f"  Genre distribution (all {len(all_genres_with_tracks)} genres): {dict(genre_counts.most_common())}")
        verbose_log(f"  Total liked tracks: {len(liked_uris)}, tracks with genres: {len(uri_to_genres)}")
        verbose_log(f"  Genre coverage: {len(uri_to_genres)/len(liked_uris)*100:.1f}% of tracks have genres")
        
        # Show breakdown by genre count (before single assignment)
        genre_size_distribution = Counter()
        for genres_list in uri_to_genres.values():
            genre_size_distribution[len(genres_list)] += 1
        verbose_log(f"  Tracks by genre count (before partition): {dict(sorted(genre_size_distribution.items()))}")
        
        # Show how many tracks were reassigned due to multiple genre matches
        tracks_with_multiple = sum(1 for genres_list in uri_to_genres.values() if len(genres_list) > 1)
        if tracks_with_multiple > 0:
            verbose_log(f"  Tracks matching multiple genres: {tracks_with_multiple} (assigned to highest priority genre)")
    
    log(f"  Creating playlists for {len(all_genres_with_tracks)} genre(s) (unique partition - each track in exactly one playlist)")
    if all_genres_with_tracks:
        for genre in all_genres_with_tracks:
            count = genre_counts_single.get(genre, len(tracks_without_genres) if genre == "Other" else 0)
            pct = (count / len(liked_uris) * 100) if len(liked_uris) > 0 else 0
            log(f"    • {genre}: {count} tracks ({pct:.1f}%)")
    
    # Get existing playlists (cached)
    existing = get_existing_playlists(sp)
    user = get_user_info(sp)
    user_id = user["id"]
    
    # Track if we need to save tracks_df at the end
    tracks_modified = False
    
    # Load previous playlist tracks from cache to detect removals
    # This allows us to compare what was in the playlist before vs now
    previous_playlist_tracks = {}  # {playlist_id: set of track URIs}
    if "playlist_id" in library.columns and "track_uri" in library.columns:
        # Check all genres (including "Other")
        genres_to_check = all_genres_with_tracks + (["Other"] if tracks_without_genres else [])
        for genre in genres_to_check:
            name = format_playlist_name(GENRE_NAME_TEMPLATE, genre=genre, playlist_type="genre_master")
            if name in existing:
                pid = existing[name]
                # Get tracks that were in this playlist from previous sync
                playlist_tracks_data = library[library["playlist_id"] == pid]
                if not playlist_tracks_data.empty and "track_uri" in playlist_tracks_data.columns:
                    previous_tracks = set(playlist_tracks_data["track_uri"].dropna().tolist())
                    previous_playlist_tracks[pid] = previous_tracks
    
    # Track which tracks are assigned to playlists (for validation)
    tracks_assigned_to_playlists = set()
    
    # Process all genre playlists (unique partition - each track in exactly one playlist)
    for genre in all_genres_with_tracks:
        # Get tracks assigned to THIS genre (single assignment, no duplicates)
        uris_should_be_in_playlist = set([u for u in liked_uris if uri_to_single_genre.get(u) == genre])
        if not uris_should_be_in_playlist:
            continue  # Skip if no tracks assigned to this genre
        
        tracks_assigned_to_playlists.update(uris_should_be_in_playlist)
        name = format_playlist_name(GENRE_NAME_TEMPLATE, genre=genre, playlist_type="genre_master")
        
        if name in existing:
            pid = existing[name]
            # Get existing tracks (includes both auto-added and manually added tracks)
            already_in_playlist = get_playlist_tracks(sp, pid)
            
            # Remove tracks that shouldn't be in this playlist (keep partition in sync with liked songs)
            # 1. Tracks no longer liked -> remove from partition
            # 2. Liked tracks assigned to a different genre -> move to correct playlist
            tracks_to_remove = []
            for track_uri in already_in_playlist:
                if track_uri not in liked_uris:
                    tracks_to_remove.append(track_uri)  # No longer liked
                else:
                    assigned_genre = uri_to_single_genre.get(track_uri)
                    if assigned_genre != genre:
                        tracks_to_remove.append(track_uri)  # Wrong genre playlist
            
            if tracks_to_remove:
                log(f"  {name}: Removing {len(tracks_to_remove)} track(s) (unliked or wrong genre)...")
                # Use safe removal with backup and validation
                from .data_protection import safe_remove_tracks_from_playlist
                success, backup_file = safe_remove_tracks_from_playlist(
                    sp, pid, name, tracks_to_remove,
                    create_backup=True,
                    validate_after=True
                )
                if not success:
                    log(f"  ⚠️  Warning: Track removal validation failed for {name}")
                    if backup_file:
                        log(f"  💾 Backup available: {backup_file.name}")
                else:
                    # Invalidate cache
                    if pid in _playlist_tracks_cache:
                        del _playlist_tracks_cache[pid]
                    # Re-fetch to get updated list
                    already_in_playlist = get_playlist_tracks(sp, pid, force_refresh=True)
            
            # Only add tracks that aren't already present (preserves manual additions)
            to_add = [u for u in uris_should_be_in_playlist if u not in already_in_playlist]

            # Check for removed tracks: tracks that were in playlist before but aren't now
            # These were manually removed, so remove the genre tag
            if pid in previous_playlist_tracks:
                previous_tracks = previous_playlist_tracks[pid]
                removed_tracks = previous_tracks - already_in_playlist
                
                if removed_tracks:
                    # Only remove genre tags for tracks that should have that genre based on current state
                    # This avoids removing genres from manually added tracks that don't match the genre
                    tracks_to_remove_genre = []
                    for removed_uri in removed_tracks:
                        # Only remove genre if the track currently has this genre in its stored tags
                        # or if it's a liked song (meaning it should match the genre)
                        if removed_uri in liked_uris:
                            tracks_to_remove_genre.append(removed_uri)
                    
                    if tracks_to_remove_genre:
                        log(f"  {name}: Detected {len(tracks_to_remove_genre)} manually removed track(s), removing genre tags...")
                        for removed_uri in tracks_to_remove_genre:
                            if _remove_genre_from_track(tracks_df, removed_uri, genre):
                                tracks_modified = True
                                # Also update uri_to_genres to reflect the change
                                if removed_uri in uri_to_genres:
                                    uri_to_genres[removed_uri] = [g for g in uri_to_genres[removed_uri] if g != genre]

            if to_add:
                for chunk in _chunked(to_add, 50):
                    api_call(sp.playlist_add_items, pid, chunk)
                # Invalidate cache for this playlist since we added tracks
                if pid in _playlist_tracks_cache:
                    del _playlist_tracks_cache[pid]
                log(f"  {name}: +{len(to_add)} tracks (manually added tracks preserved)")
                # Update description with genre tags (use all tracks in playlist)
                _update_playlist_description_with_genres(sp, user_id, pid, None)
            else:
                log(f"  {name}: up to date ({len(uris_should_be_in_playlist)} tracks)")
        else:
            verbose_log(f"Creating new playlist '{name}' for genre '{genre}'...")
            pl = api_call(
                sp.user_playlist_create,
                user_id,
                name,
                public=False,
                description=format_playlist_description("All liked songs", genre=genre, playlist_type="genre_master"),
            )
            pid = pl["id"]
            verbose_log(f"  Created playlist '{name}' with id {pid}, adding {len(uris_should_be_in_playlist)} tracks...")

            chunk_count = 0
            for chunk in _chunked(list(uris_should_be_in_playlist), 50):
                chunk_count += 1
                verbose_log(f"  Adding chunk {chunk_count} ({len(chunk)} tracks) to new playlist...")
                api_call(sp.playlist_add_items, pid, chunk)
            # Update description with genre tags
            _update_playlist_description_with_genres(sp, user_id, pid, list(uris_should_be_in_playlist))
            # Invalidate playlist cache since we created a new playlist
            _invalidate_playlist_cache()
            log(f"  {name}: created with {len(uris_should_be_in_playlist)} tracks")
    
    # Create/update "Other" playlist for tracks without genre classification
    # IMPORTANT: "Other" should ONLY contain tracks that are NOT in any other AJam playlist
    if tracks_without_genres:
        other_genre = "Other"
        name = format_playlist_name(GENRE_NAME_TEMPLATE, genre=other_genre, playlist_type="genre_master")
        
        # Build set of all tracks that are assigned to other genre playlists (unique partition)
        # This ensures "Other" only contains tracks NOT assigned to any genre playlist
        tracks_in_other_genre_playlists = set(uri_to_single_genre.keys())
        
        # Filter "Other" playlist tracks to only include those NOT assigned to any genre playlist
        # AND not in uri_to_genres (no genre classification)
        # This ensures "Other" only has tracks that truly don't belong in any genre playlist
        tracks_for_other = tracks_without_genres - tracks_in_other_genre_playlists
        tracks_assigned_to_playlists.update(tracks_for_other)
        
        if name in existing:
            pid = existing[name]
            already_in_playlist = get_playlist_tracks(sp, pid)
            
            # Remove tracks that shouldn't be in "Other" (keep partition in sync with liked songs)
            # 1. Tracks no longer liked -> remove from partition
            # 2. Liked tracks that now have genre classification (assigned to another playlist)
            tracks_to_remove = []
            for track_uri in already_in_playlist:
                if track_uri not in liked_uris:
                    tracks_to_remove.append(track_uri)  # No longer liked
                elif track_uri in uri_to_single_genre:
                    tracks_to_remove.append(track_uri)  # Now in a genre playlist
            
            if tracks_to_remove:
                log(f"  {name}: Removing {len(tracks_to_remove)} track(s) (unliked or now in genre playlist)...")
                from .data_protection import safe_remove_tracks_from_playlist
                success, backup_file = safe_remove_tracks_from_playlist(
                    sp, pid, name, tracks_to_remove,
                    create_backup=True,
                    validate_after=True
                )
                if not success:
                    log(f"  ⚠️  Warning: Track removal validation failed for {name}")
                    if backup_file:
                        log(f"  💾 Backup available: {backup_file.name}")
                else:
                    if pid in _playlist_tracks_cache:
                        del _playlist_tracks_cache[pid]
                    already_in_playlist = get_playlist_tracks(sp, pid, force_refresh=True)
            
            # Add tracks that should be in "Other" playlist (not in other playlists, no genre classification)
            to_add = [u for u in tracks_for_other if u not in already_in_playlist]
            
            if to_add:
                for chunk in _chunked(to_add, 50):
                    api_call(sp.playlist_add_items, pid, chunk)
                if pid in _playlist_tracks_cache:
                    del _playlist_tracks_cache[pid]
                log(f"  {name}: +{len(to_add)} tracks (only tracks not in other genre playlists)")
                _update_playlist_description_with_genres(sp, user_id, pid, None)
            else:
                log(f"  {name}: up to date ({len(tracks_for_other)} tracks, excluding {len(tracks_without_genres) - len(tracks_for_other)} in other playlists)")
        else:
            verbose_log(f"Creating new playlist '{name}' for unclassified tracks (not in other genre playlists)...")
            pl = api_call(
                sp.user_playlist_create,
                user_id,
                name,
                public=False,
                description=format_playlist_description("All liked songs", genre=other_genre, playlist_type="genre_master"),
            )
            pid = pl["id"]
            verbose_log(f"  Created playlist '{name}' with id {pid}, adding {len(tracks_for_other)} tracks (excluding {len(tracks_without_genres) - len(tracks_for_other)} in other playlists)...")

            chunk_count = 0
            for chunk in _chunked(list(tracks_for_other), 50):
                chunk_count += 1
                verbose_log(f"  Adding chunk {chunk_count} ({len(chunk)} tracks) to new playlist...")
                api_call(sp.playlist_add_items, pid, chunk)
            _update_playlist_description_with_genres(sp, user_id, pid, list(tracks_for_other))
            _invalidate_playlist_cache()
            log(f"  {name}: created with {len(tracks_for_other)} tracks (excluding {len(tracks_without_genres) - len(tracks_for_other)} already in other genre playlists)")
    
    # Validate unique partition coverage
    all_assigned_tracks = tracks_assigned_to_playlists
    missing_tracks = liked_uris - all_assigned_tracks
    
    if missing_tracks:
        log(f"  ⚠️  WARNING: {len(missing_tracks)} track(s) not assigned to any playlist!")
        if verbose_log:
            verbose_log(f"  Missing tracks (first 10): {list(missing_tracks)[:10]}")
    else:
        log(f"  ✅ Unique partition verified: All {len(liked_uris)} liked tracks are in exactly one playlist")
        
        # Verify no duplicates across playlists
        all_playlist_tracks = set()
        duplicate_tracks = set()
        for genre in all_genres_with_tracks + (["Other"] if tracks_without_genres else []):
            name = format_playlist_name(GENRE_NAME_TEMPLATE, genre=genre, playlist_type="genre_master")
            if name in existing:
                pid = existing[name]
                playlist_tracks = get_playlist_tracks(sp, pid)
                for track_uri in playlist_tracks:
                    if track_uri in liked_uris:  # Only check liked songs
                        if track_uri in all_playlist_tracks:
                            duplicate_tracks.add(track_uri)
                        all_playlist_tracks.add(track_uri)
        
        if duplicate_tracks:
            log(f"  ⚠️  WARNING: {len(duplicate_tracks)} track(s) appear in multiple playlists!")
            if verbose_log:
                verbose_log(f"  Duplicate tracks (first 10): {list(duplicate_tracks)[:10]}")
        else:
            log(f"  ✅ No duplicates: Each track appears in exactly one playlist")
    
    # Save tracks_df if it was modified
    if tracks_modified:
        tracks_path = DATA_DIR / "tracks.parquet"
        try:
            tracks_df.to_parquet(tracks_path, index=False, engine='pyarrow')
        except Exception:
            tracks_df.to_parquet(tracks_path, index=False)
        log(f"  ✅ Updated track genres after removals")


# ============================================================================
# DUPLICATE PLAYLIST DETECTION & DELETION
# ============================================================================


