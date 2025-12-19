# 🎵 SpotifyFrames

A **pandas-first** interface to Spotify Web API with **automated playlist management**.

Turn your Spotify library into tidy DataFrames, analyze your listening habits, and automatically organize your music into smart playlists.

## ✨ Features

- 📊 **Pandas DataFrames** - Your library as tidy, mergeable tables
- 📅 **Monthly Playlists** - Auto-create playlists like `AJFindsDec25`
- 🎸 **Genre-Split Playlists** - Separate by HipHop, Dance, Other
- 🎵 **Master Genre Playlists** - All-time playlists by genre
- 🤖 **Daily Automation** - GitHub Actions updates playlists automatically
- 💾 **Local Cache** - Parquet files for fast offline access
- 🔄 **No Duplicates** - Smart deduplication on every run

## 🚀 Quick Start

```bash
# Clone the repo
git clone https://github.com/AJsQuestions/spotifyframes.git
cd spotifyframes

# Install
pip install -e .

# Set credentials
export SPOTIPY_CLIENT_ID="your_client_id"
export SPOTIPY_CLIENT_SECRET="your_client_secret"
export SPOTIPY_REDIRECT_URI="http://127.0.0.1:8888/callback"
```

## 📓 Notebooks

| Notebook | Description |
|----------|-------------|
| `01_sync_data.ipynb` | Download and cache your Spotify library |
| `02_analyze_library.ipynb` | Visualize your listening habits |
| `03_playlist_analysis.ipynb` | Genre analysis and playlist clustering |
| `04_liked_songs_monthly_playlists.ipynb` | **Create all automated playlists** |

### Notebook 04: Playlist Generator

Creates **194+ playlists** automatically:

```
📅 Monthly Playlists (51):
   AJFindsSep21, AJFindsOct21, ... AJFindsDec25

🎸 Genre-Split Monthly (137):
   HipHopFindsDec25, DanceFindsDec25, OtherFindsDec25

🎵 Master Genre Playlists (7):
   AJamHip-Hop, AJamElectronic, AJamR&B/Soul, ...
```

**Configuration:**
```python
OWNER_NAME = "AJ"
PREFIX = "Finds"
MONTHLY_NAME_TEMPLATE = "{owner}{prefix}{mon}{year}"  # → AJFindsDec25
SPLIT_GENRES = ["HipHop", "Dance", "Other"]
DRY_RUN = True  # Set False to create playlists
```

## 🤖 Daily Automation (GitHub Actions)

Playlists update automatically every day at 2am UTC.

### Setup:
1. Push to GitHub
2. Run `python scripts/get_refresh_token.py` to get your refresh token
3. Add these secrets to your repo (Settings → Secrets → Actions):
   - `SPOTIPY_CLIENT_ID`
   - `SPOTIPY_CLIENT_SECRET`
   - `SPOTIPY_REDIRECT_URI`
   - `SPOTIPY_REFRESH_TOKEN`

### Manual trigger:
Actions → Daily Spotify Playlist Update → Run workflow

## 📊 Dashboard

A Dash web app for interactive analysis:

```bash
cd dashboard
pip install -r requirements.txt
python app.py
# Open http://127.0.0.1:8050
```

Features:
- Library overview with stats
- Artist and genre analysis
- Playlist clustering
- Similar playlist discovery

## 🔧 Python API

```python
from spotifyframes import SpotifyFrames

sf = SpotifyFrames.from_env(progress=True)

# Sync your library
sf.sync(owned_only=True, include_liked_songs=True)

# Access your data
playlists = sf.playlists()      # All playlists
tracks = sf.tracks()            # All tracks
artists = sf.artists()          # Artists with genres
wide = sf.library_wide()        # Everything joined
```

## 📁 Data Tables

| Table | Description |
|-------|-------------|
| `playlists()` | Your playlists (including ❤️ Liked Songs) |
| `playlist_tracks()` | Track-playlist relationships with `added_at` |
| `tracks()` | Track metadata (name, duration, popularity) |
| `track_artists()` | Track-artist relationships |
| `artists()` | Artist info with genres |
| `library_wide()` | Everything joined together |

## 🎛️ CLI

```bash
# Sync library
spotifyframes refresh

# Check status
spotifyframes status

# Export data
spotifyframes export --table tracks --out tracks.parquet
```

## 📂 Project Structure

```
spotifyframes/
├── notebooks/
│   ├── 01_sync_data.ipynb
│   ├── 02_analyze_library.ipynb
│   ├── 03_playlist_analysis.ipynb
│   ├── 04_liked_songs_monthly_playlists.ipynb
│   └── lib.py                    # Shared utilities
├── dashboard/
│   ├── app.py                    # Dash web app
│   └── assets/styles.css
├── scripts/
│   ├── daily_update.py           # Local automation
│   ├── sync_and_update.py        # GitHub Actions script
│   └── get_refresh_token.py      # Get token for CI/CD
├── .github/workflows/
│   └── daily_update.yml          # GitHub Actions workflow
├── spotifyframes/                # Core library
└── data/                         # Cached parquet files
```

## 📋 Requirements

- Python 3.9+
- Spotify Developer Account
- Spotify Premium (for some features)

## 🔒 Spotify API Notes

Spotify deprecated these endpoints for new apps (Nov 2024):
- ❌ Audio features (danceability, energy, etc.)
- ❌ Audio analysis
- ⚠️ Recommendations (may work for older apps)

This library focuses on what's still available.

## 📄 License

MIT

---

Made with 🎵 by [AJ](https://github.com/AJsQuestions)
