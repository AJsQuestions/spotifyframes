#!/usr/bin/env python3
"""
Daily Spotify Playlist Automation Script

This script automatically:
1. Syncs new liked songs from Spotify
2. Updates monthly playlists with new tracks
3. Updates genre-split playlists
4. Updates master genre playlists

Run daily via cron or Task Scheduler:
    # Linux/Mac cron (every day at 2am):
    0 2 * * * /path/to/python /path/to/daily_update.py
    
    # Or run manually:
    python scripts/daily_update.py
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from collections import Counter

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ============================================================================
# CONFIGURATION - Set via environment variables
# ============================================================================

# Configurable via environment variables
OWNER_NAME = os.environ.get("PLAYLIST_OWNER_NAME", "")
PREFIX = os.environ.get("PLAYLIST_PREFIX", "Finds")

# Templates
MONTHLY_NAME_TEMPLATE = "{owner}{prefix}{mon}{year}"
GENRE_MONTHLY_TEMPLATE = "{genre}{prefix}{mon}{year}"
GENRE_NAME_TEMPLATE = "{owner}am{genre}"

# Genre split
SPLIT_GENRES = ["HipHop", "Dance", "Other"]

# Limits
MIN_TRACKS_FOR_GENRE = 20
MAX_GENRE_PLAYLISTS = 19

# ============================================================================

DATA_DIR = PROJECT_ROOT / "data"

MONTH_NAMES = {
    "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr",
    "05": "May", "06": "Jun", "07": "Jul", "08": "Aug",
    "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec"
}

GENRE_SPLIT_RULES = {
    "HipHop": ["hip hop", "rap", "trap", "drill", "grime", "crunk", "phonk", 
               "boom bap", "dirty south", "gangsta", "uk drill", "melodic rap",
               "conscious hip hop", "underground hip hop", "southern hip hop"],
    "Dance": ["electronic", "edm", "house", "techno", "trance", "dubstep", 
              "drum and bass", "ambient", "garage", "deep house", "minimal",
              "synthwave", "future bass", "electro", "dance", "electronica",
              "uk garage", "breakbeat", "hardstyle", "progressive house"]
}

GENRE_RULES = [
    (["hip hop", "rap", "trap", "drill", "grime", "crunk", "boom bap", "dirty south", "phonk"], "Hip-Hop"),
    (["r&b", "rnb", "soul", "neo soul", "funk", "motown", "disco"], "R&B/Soul"),
    (["electronic", "edm", "house", "techno", "trance", "dubstep", "drum and bass", "ambient"], "Electronic"),
    (["rock", "alternative", "grunge", "punk", "emo", "post-punk", "shoegaze"], "Rock"),
    (["metal", "heavy metal", "death metal", "black metal", "thrash"], "Metal"),
    (["indie", "indie rock", "indie pop", "lo-fi", "dream pop"], "Indie"),
    (["pop", "dance pop", "synth pop", "electropop"], "Pop"),
    (["latin", "reggaeton", "salsa", "bachata", "cumbia"], "Latin"),
    (["afrobeat", "k-pop", "reggae", "dancehall", "world"], "World"),
    (["jazz", "smooth jazz", "bebop", "swing"], "Jazz"),
    (["classical", "orchestra", "symphony", "opera"], "Classical"),
    (["country", "folk", "americana", "bluegrass"], "Country/Folk"),
]


def log(msg):
    """Print with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}")


def get_split_genre(genre_list):
    """Map to HipHop, Dance, or Other."""
    if not genre_list:
        return "Other"
    combined = " ".join(genre_list).lower()
    for genre_name, keywords in GENRE_SPLIT_RULES.items():
        if any(kw in combined for kw in keywords):
            return genre_name
    return "Other"


def get_broad_genre(genre_list):
    """Map to broad category."""
    if not genre_list:
        return None
    combined = " ".join(genre_list).lower()
    for keywords, category in GENRE_RULES:
        if any(kw in combined for kw in keywords):
            return category
    return None


def _chunked(seq, n=100):
    for i in range(0, len(seq), n):
        yield seq[i:i+n]


def _to_uri(x):
    x = str(x)
    if x.startswith("spotify:track:"):
        return x
    if len(x) >= 20 and ":" not in x:
        return f"spotify:track:{x}"
    return x


def get_existing_playlists(sp):
    """Get all user playlists."""
    mapping = {}
    offset = 0
    while True:
        page = sp.current_user_playlists(limit=50, offset=offset)
        for item in page.get("items", []):
            mapping[item["name"]] = item["id"]
        if not page.get("next"):
            break
        offset += 50
    return mapping


def get_playlist_tracks(sp, pid):
    """Get all track URIs in a playlist."""
    uris = set()
    offset = 0
    while True:
        page = sp.playlist_items(pid, fields="items(track(uri)),next", limit=100, offset=offset)
        for it in page.get("items", []):
            if it.get("track", {}).get("uri"):
                uris.add(it["track"]["uri"])
        if not page.get("next"):
            break
        offset += 100
    return uris


def format_month_name(template, month_str, genre=None):
    """Format playlist name from month string like '2025-01'."""
    parts = month_str.split("-")
    full_year = parts[0] if len(parts) >= 1 else ""
    month_num = parts[1] if len(parts) >= 2 else ""
    mon = MONTH_NAMES.get(month_num, month_num)
    year = full_year[2:] if len(full_year) == 4 else full_year
    
    return template.format(
        owner=OWNER_NAME,
        prefix=PREFIX,
        genre=genre or "",
        mon=mon,
        year=year
    )


def sync_liked_songs(sf):
    """Sync liked songs from Spotify."""
    log("Syncing liked songs...")
    
    from spotim8 import LIKED_SONGS_PLAYLIST_ID
    import pandas as pd
    
    # Load existing data
    library = pd.read_parquet(DATA_DIR / "playlist_tracks.parquet")
    
    # Get current liked songs from Spotify
    liked_ids = set()
    offset = 0
    while True:
        page = sf.sp.current_user_saved_tracks(limit=50, offset=offset)
        for item in page.get("items", []):
            track = item.get("track", {})
            if track.get("id"):
                liked_ids.add(track["id"])
        if not page.get("next"):
            break
        offset += 50
    
    # Filter to liked songs
    existing = library[library["playlist_id"].astype(str).str.contains(str(LIKED_SONGS_PLAYLIST_ID))]
    existing_ids = set(existing["track_id"])
    
    new_count = len(liked_ids - existing_ids)
    log(f"Found {len(liked_ids)} liked songs, {new_count} new")
    
    return new_count > 0


def update_monthly_playlists(sf, current_month_only=True):
    """Update monthly playlists."""
    import pandas as pd
    from spotim8 import LIKED_SONGS_PLAYLIST_ID
    
    log("Loading data...")
    library = pd.read_parquet(DATA_DIR / "playlist_tracks.parquet")
    
    # Get liked songs
    liked = library[library["playlist_id"].astype(str).str.contains(str(LIKED_SONGS_PLAYLIST_ID))].copy()
    
    if liked.empty:
        log("No liked songs found!")
        return
    
    # Parse timestamps
    added_col = None
    for col in ["added_at", "playlist_added_at", "track_added_at"]:
        if col in liked.columns:
            added_col = col
            break
    
    if not added_col:
        log("No timestamp column found!")
        return
    
    liked[added_col] = pd.to_datetime(liked[added_col], errors="coerce", utc=True)
    liked["month"] = liked[added_col].dt.to_period("M").astype(str)
    liked["_uri"] = liked["track_id"].map(_to_uri)
    
    # Build month -> tracks
    month_to_tracks = {}
    for m, g in liked.groupby("month"):
        uris = g["_uri"].dropna().tolist()
        seen = set()
        unique = [u for u in uris if not (u in seen or seen.add(u))]
        month_to_tracks[m] = unique
    
    # Filter to current month if needed
    if current_month_only:
        current = datetime.now().strftime("%Y-%m")
        month_to_tracks = {m: v for m, v in month_to_tracks.items() if m == current}
    
    if not month_to_tracks:
        log("No months to process")
        return
    
    log(f"Processing {len(month_to_tracks)} month(s)...")
    
    # Get existing playlists
    existing = get_existing_playlists(sf.sp)
    user_id = sf.sp.current_user()["id"]
    
    for month, uris in sorted(month_to_tracks.items()):
        if not uris:
            continue
        
        name = format_month_name(MONTHLY_NAME_TEMPLATE, month)
        
        if name in existing:
            pid = existing[name]
            already = get_playlist_tracks(sf.sp, pid)
            to_add = [u for u in uris if u not in already]
            
            if to_add:
                for chunk in _chunked(to_add, 100):
                    sf.sp.playlist_add_items(pid, chunk)
                log(f"  {name}: Added {len(to_add)} new tracks")
            else:
                log(f"  {name}: Already up to date")
        else:
            pl = sf.sp.user_playlist_create(
                user_id, name, public=False,
                description=f"Liked songs from {month}"
            )
            pid = pl["id"]
            
            for chunk in _chunked(uris, 100):
                sf.sp.playlist_add_items(pid, chunk)
            log(f"  {name}: Created with {len(uris)} tracks")
    
    return month_to_tracks


def update_genre_split_playlists(sf, month_to_tracks):
    """Update genre-split monthly playlists."""
    import pandas as pd
    import ast
    import numpy as np
    
    if not month_to_tracks:
        return
    
    log("Building genre mapping...")
    
    # Load data
    track_artists = pd.read_parquet(DATA_DIR / "track_artists.parquet")
    artists = pd.read_parquet(DATA_DIR / "artists.parquet")
    
    artist_genres_map = artists.set_index("artist_id")["genres"].to_dict()
    
    # Build track -> genre
    all_uris = set(u for uris in month_to_tracks.values() for u in uris)
    track_ids = {u.split(":")[-1] for u in all_uris if u.startswith("spotify:track:")}
    
    track_to_genre = {}
    for _, row in track_artists[track_artists["track_id"].isin(track_ids)].iterrows():
        tid = row["track_id"]
        uri = f"spotify:track:{tid}"
        
        if uri in track_to_genre:
            continue
        
        artist_genres = artist_genres_map.get(row["artist_id"], [])
        if isinstance(artist_genres, str):
            try:
                artist_genres = ast.literal_eval(artist_genres)
            except:
                artist_genres = [artist_genres]
        if isinstance(artist_genres, np.ndarray):
            artist_genres = list(artist_genres)
        
        track_to_genre[uri] = get_split_genre(artist_genres or [])
    
    # Get existing playlists
    existing = get_existing_playlists(sf.sp)
    user_id = sf.sp.current_user()["id"]
    
    for month, uris in sorted(month_to_tracks.items()):
        for genre in SPLIT_GENRES:
            genre_uris = [u for u in uris if track_to_genre.get(u) == genre]
            
            if not genre_uris:
                continue
            
            name = format_month_name(GENRE_MONTHLY_TEMPLATE, month, genre)
            
            if name in existing:
                pid = existing[name]
                already = get_playlist_tracks(sf.sp, pid)
                to_add = [u for u in genre_uris if u not in already]
                
                if to_add:
                    for chunk in _chunked(to_add, 100):
                        sf.sp.playlist_add_items(pid, chunk)
                    log(f"  {name}: Added {len(to_add)} new tracks")
            else:
                pl = sf.sp.user_playlist_create(
                    user_id, name, public=False,
                    description=f"{genre} tracks from {month}"
                )
                pid = pl["id"]
                
                for chunk in _chunked(genre_uris, 100):
                    sf.sp.playlist_add_items(pid, chunk)
                log(f"  {name}: Created with {len(genre_uris)} tracks")


def update_master_genre_playlists(sf):
    """Update master genre playlists with any new tracks."""
    import pandas as pd
    import ast
    import numpy as np
    from spotim8 import LIKED_SONGS_PLAYLIST_ID
    
    log("Updating master genre playlists...")
    
    # Load data
    library = pd.read_parquet(DATA_DIR / "playlist_tracks.parquet")
    track_artists = pd.read_parquet(DATA_DIR / "track_artists.parquet")
    artists = pd.read_parquet(DATA_DIR / "artists.parquet")
    
    # Get liked songs
    liked = library[library["playlist_id"].astype(str).str.contains(str(LIKED_SONGS_PLAYLIST_ID))]
    liked_ids = set(liked["track_id"])
    liked_uris = [f"spotify:track:{tid}" for tid in liked_ids]
    
    # Build genre mapping
    artist_genres_map = artists.set_index("artist_id")["genres"].to_dict()
    
    uri_to_genre = {}
    for _, row in track_artists[track_artists["track_id"].isin(liked_ids)].iterrows():
        tid = row["track_id"]
        uri = f"spotify:track:{tid}"
        
        if uri in uri_to_genre:
            continue
        
        artist_genres = artist_genres_map.get(row["artist_id"], [])
        if isinstance(artist_genres, str):
            try:
                artist_genres = ast.literal_eval(artist_genres)
            except:
                artist_genres = [artist_genres]
        if isinstance(artist_genres, np.ndarray):
            artist_genres = list(artist_genres)
        
        broad = get_broad_genre(artist_genres or [])
        if broad:
            uri_to_genre[uri] = broad
    
    # Count genres
    genre_counts = Counter(uri_to_genre.values())
    selected = [g for g, n in genre_counts.most_common(MAX_GENRE_PLAYLISTS) if n >= MIN_TRACKS_FOR_GENRE]
    
    # Get existing playlists
    existing = get_existing_playlists(sf.sp)
    user_id = sf.sp.current_user()["id"]
    
    for genre in selected:
        uris = [u for u in liked_uris if uri_to_genre.get(u) == genre]
        if not uris:
            continue
        
        name = GENRE_NAME_TEMPLATE.format(owner=OWNER_NAME, genre=genre)
        
        if name in existing:
            pid = existing[name]
            already = get_playlist_tracks(sf.sp, pid)
            to_add = [u for u in uris if u not in already]
            
            if to_add:
                for chunk in _chunked(to_add, 100):
                    sf.sp.playlist_add_items(pid, chunk)
                log(f"  {name}: Added {len(to_add)} new tracks")
        else:
            pl = sf.sp.user_playlist_create(
                user_id, name, public=False,
                description=f"All liked songs - {genre}"
            )
            pid = pl["id"]
            
            for chunk in _chunked(uris, 100):
                sf.sp.playlist_add_items(pid, chunk)
            log(f"  {name}: Created with {len(uris)} tracks")


def main():
    """Main automation function."""
    log("=" * 60)
    log("Starting daily Spotify playlist update")
    log("=" * 60)
    
    # Connect to Spotify
    try:
        from spotim8 import Spotim8
        from spotim8.catalog import CacheConfig
        
        DATA_DIR.mkdir(exist_ok=True)
        sf = Spotim8.from_env(progress=False, cache=CacheConfig(dir=DATA_DIR))
        log("Connected to Spotify")
    except Exception as e:
        log(f"ERROR: Could not connect to Spotify: {e}")
        log("Make sure SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, and SPOTIPY_REDIRECT_URI are set")
        sys.exit(1)
    
    try:
        # 1. Update monthly playlists (current month only)
        log("\n--- Monthly Playlists ---")
        month_to_tracks = update_monthly_playlists(sf, current_month_only=True)
        
        # 2. Update genre-split playlists
        if month_to_tracks:
            log("\n--- Genre-Split Playlists ---")
            update_genre_split_playlists(sf, month_to_tracks)
        
        # 3. Update master genre playlists
        log("\n--- Master Genre Playlists ---")
        update_master_genre_playlists(sf)
        
        log("\n" + "=" * 60)
        log("Daily update complete!")
        log("=" * 60)
        
    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
