#!/usr/bin/env python3
"""
Export parquet data to JSON for local web development.

This creates JSON files that the spotim8_app can load directly,
avoiding the need to fetch from Spotify API during development.

Usage:
    python scripts/export_for_web.py
"""

import json
import pandas as pd
from pathlib import Path

# Paths
DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUT_DIR = Path(__file__).parent.parent / "spotim8_app" / "public" / "dev-data"


def safe_json_value(val):
    """Convert pandas/numpy values to JSON-safe types."""
    if pd.isna(val):
        return None
    if hasattr(val, 'tolist'):  # numpy array
        return val.tolist()
    if hasattr(val, 'item'):  # numpy scalar
        return val.item()
    return val


def df_to_records(df: pd.DataFrame) -> list:
    """Convert DataFrame to list of dicts with JSON-safe values."""
    records = []
    for _, row in df.iterrows():
        record = {k: safe_json_value(v) for k, v in row.items()}
        records.append(record)
    return records


def export_playlists():
    """Export playlists data."""
    path = DATA_DIR / "playlists.parquet"
    if not path.exists():
        print(f"⚠️  {path} not found, skipping")
        return []
    
    df = pd.read_parquet(path)
    playlists = []
    
    for _, row in df.iterrows():
        playlists.append({
            "id": row.get("playlist_id") or row.get("id"),
            "name": row.get("name", "Unknown"),
            "description": row.get("description", ""),
            "images": [{"url": row.get("image_url", "")}] if row.get("image_url") else [],
            "tracks": {"total": int(row.get("track_count", 0))},
            "owner": {
                "id": row.get("owner_id", ""),
                "display_name": row.get("owner_name", ""),
            },
            "public": bool(row.get("public", True)),
        })
    
    print(f"✅ Exported {len(playlists)} playlists")
    return playlists


def export_tracks():
    """Export tracks with artist info."""
    tracks_path = DATA_DIR / "tracks.parquet"
    track_artists_path = DATA_DIR / "track_artists.parquet"
    playlist_tracks_path = DATA_DIR / "playlist_tracks.parquet"
    
    if not tracks_path.exists():
        print(f"⚠️  {tracks_path} not found, skipping")
        return [], {}
    
    tracks_df = pd.read_parquet(tracks_path)
    
    # Load track-artist relationships
    artist_map = {}  # track_id -> list of artists
    if track_artists_path.exists():
        ta_df = pd.read_parquet(track_artists_path)
        for _, row in ta_df.iterrows():
            tid = row.get("track_id")
            if tid not in artist_map:
                artist_map[tid] = []
            artist_map[tid].append({
                "id": row.get("artist_id", ""),
                "name": row.get("artist_name", "Unknown"),
            })
    
    # Load playlist-track relationships  
    playlist_map = {}  # track_id -> set of playlist_ids
    if playlist_tracks_path.exists():
        pt_df = pd.read_parquet(playlist_tracks_path)
        for _, row in pt_df.iterrows():
            tid = row.get("track_id")
            pid = row.get("playlist_id")
            if tid not in playlist_map:
                playlist_map[tid] = set()
            playlist_map[tid].add(pid)
    
    tracks = []
    track_playlist_map = {}  # For the web app format
    
    for _, row in tracks_df.iterrows():
        track_id = row.get("track_id") or row.get("id")
        
        # Get album image
        album_image = row.get("album_image_url") or row.get("image_url", "")
        
        track = {
            "id": track_id,
            "name": row.get("name", "Unknown"),
            "popularity": int(row.get("popularity", 0)),
            "duration_ms": int(row.get("duration_ms", 0)),
            "album": {
                "id": row.get("album_id", ""),
                "name": row.get("album_name", "Unknown"),
                "release_date": str(row.get("release_date", "")),
                "images": [{"url": album_image}] if album_image else [],
            },
            "artists": artist_map.get(track_id, [{"id": "", "name": "Unknown"}]),
            "external_urls": {"spotify": f"https://open.spotify.com/track/{track_id}"},
        }
        tracks.append(track)
        
        # Build playlist mapping
        if track_id in playlist_map:
            track_playlist_map[track_id] = list(playlist_map[track_id])
    
    print(f"✅ Exported {len(tracks)} tracks")
    return tracks, track_playlist_map


def export_artists():
    """Export artists with genres."""
    path = DATA_DIR / "artists.parquet"
    if not path.exists():
        print(f"⚠️  {path} not found, skipping")
        return {}
    
    df = pd.read_parquet(path)
    artists = {}
    
    for _, row in df.iterrows():
        artist_id = row.get("artist_id") or row.get("id")
        genres = row.get("genres", [])
        if isinstance(genres, str):
            try:
                genres = json.loads(genres)
            except:
                genres = [g.strip() for g in genres.split(",") if g.strip()]
        
        artists[artist_id] = {
            "id": artist_id,
            "name": row.get("name", "Unknown"),
            "genres": genres if isinstance(genres, list) else [],
            "popularity": int(row.get("popularity", 0)),
            "followers": {"total": int(row.get("followers", 0))},
            "images": [{"url": row.get("image_url", "")}] if row.get("image_url") else [],
        }
    
    print(f"✅ Exported {len(artists)} artists")
    return artists


def main():
    print("🎵 Exporting Spotim8 data for web development...\n")
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Export all data
    playlists = export_playlists()
    tracks, track_playlist_map = export_tracks()
    artists = export_artists()
    
    # Create combined data file for the web app
    web_data = {
        "playlists": playlists,
        "tracks": tracks,
        "trackPlaylistMap": track_playlist_map,
        "artists": artists,
        "exportedAt": pd.Timestamp.now().isoformat(),
    }
    
    output_path = OUTPUT_DIR / "library.json"
    with open(output_path, "w") as f:
        json.dump(web_data, f)
    
    # Calculate size
    size_mb = output_path.stat().st_size / 1024 / 1024
    
    print(f"\n✨ Export complete!")
    print(f"   📁 {output_path}")
    print(f"   📊 {len(playlists)} playlists, {len(tracks)} tracks, {len(artists)} artists")
    print(f"   💾 {size_mb:.2f} MB")
    print(f"\n💡 The web app will auto-detect this file in dev mode.")


if __name__ == "__main__":
    main()

