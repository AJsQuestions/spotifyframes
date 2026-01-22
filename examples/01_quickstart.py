#!/usr/bin/env python3
"""
Spotim8 Quickstart Example

Before running, set environment variables:
    export SPOTIPY_CLIENT_ID="your_client_id"
    export SPOTIPY_CLIENT_SECRET="your_client_secret"
    export SPOTIPY_REDIRECT_URI="http://127.0.0.1:8888/callback"
"""

from src import Spotim8, build_all_features

# Initialize client
sf = Spotim8.from_env(progress=True)

# Sync your library (incremental - only fetches changes)
sf.sync(owned_only=True, include_liked_songs=True)

# Show what data we have
sf.print_status()

# Access individual tables
playlists = sf.playlists()
tracks = sf.tracks()
artists = sf.artists()

print(f"\n📊 Your Library:")
print(f"   • {len(playlists)} playlists")
print(f"   • {len(tracks):,} unique tracks")
print(f"   • {len(artists):,} unique artists")

# Get the wide table (everything joined)
wide = sf.library_wide()
print(f"\n📋 Library wide table: {len(wide):,} rows × {len(wide.columns)} columns")

# Build features for analysis/ML
features = build_all_features(wide)
print(f"\n🔧 Feature matrix: {features.shape}")
print(features.head())
