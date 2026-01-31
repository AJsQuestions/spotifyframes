# 🎵 SpotiM8 v5.0.0

**Professional Spotify analytics platform** with **automated playlist management**, **CLI**, **dashboard**, and **streaming history integration**.

Turn your Spotify library into tidy DataFrames, analyze your listening habits, and automatically organize your music into smart playlists based on both your library and actual listening patterns.

## ✨ Features

- 📊 **Pandas DataFrames** - Your library as tidy, mergeable tables
- 📅 **3 Core Playlist Types** - Finds (liked songs), Top (most played), and Discovery (new tracks)
- 🎸 **Genre-Split Playlists** - Separate by HipHop, Dance, Other
- 🎵 **Master Genre Playlists** - Exhaustive all-time playlists that partition your entire library by genre
- 📈 **Streaming History Integration** - Analyze actual listening patterns from Spotify exports
- 🎯 **Most Played Playlists** - Monthly playlists based on actual listening data
- 🔍 **Discovery Playlists** - Track newly discovered music
- 🤖 **Daily Automation** - Local cron job updates playlists automatically
- 💾 **Local Cache** - Parquet files for fast offline access
- 🔄 **No Duplicates** - Smart deduplication on every run
- 📊 **Analysis Notebooks** - 5 demonstrative Jupyter notebooks for views and visualization
- ✨ **Rich Playlist Descriptions** - Auto-generated descriptions with statistics, genres, and Daylist-style mood tags (Chill, Energetic, Focus, etc.)
- 🏥 **Health Checks** - Identify empty playlists, duplicates, and organizational issues
- 🎨 **Playlist Organization** - Smart categorization and organization tools
- 🛡️ **Production-Grade** - Robust error handling, logging, and monitoring
- 🎨 **Creative Features** - Theme playlists, time capsules, smart mixing, and insights
- 📊 **Listening Insights** - Comprehensive reports on your listening habits and patterns
- 🔗 **Playlist Intelligence** - Similarity detection, merge suggestions, and health scores

## 📋 Requirements

- **Python 3.10+** (required - Python 3.9 and below are not supported)
- Spotify Developer Account (free)
- Spotify Premium (for some features)

**Note:** If you see an error like `Package 'spotim8' requires a different Python: 3.9.6 not in '>=3.10'`, you need to upgrade Python. Use `python3 --version` to check your version.

---

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/AJsQuestions/spotim8.git
cd spotim8

# Create virtual environment (requires Python 3.10+)
python3 --version  # Verify you have Python 3.10 or higher
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -e .
```

### 2. Spotify API Setup

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Log in with your Spotify account
3. Click **"Create app"**
4. Fill in:
   - **App name**: Spotim8 (or any name)
   - **App description**: Personal Spotify analytics
   - **Redirect URI**: `http://127.0.0.1:8888/callback` ⚠️ **Must match exactly**
   - Check **"I understand and agree..."**
5. Click **"Save"**
6. Copy your **Client ID** and **Client Secret** from Settings

### 3. Environment Configuration

Create a `.env` file in the project root:

```bash
cp env.example .env
```

Edit `.env` and add your credentials:

```bash
# Required
SPOTIPY_CLIENT_ID=your_client_id_here
SPOTIPY_CLIENT_SECRET=your_client_secret_here
SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback

# Optional: For automated runs (get via scripts/utils/get_token.py)
SPOTIPY_REFRESH_TOKEN=your_refresh_token_here

# Optional: Customize playlist naming
PLAYLIST_OWNER_NAME=AJ
PLAYLIST_PREFIX=Finds

# Optional: Email notifications (see Email Notifications section below)
# EMAIL_ENABLED=true
# EMAIL_SMTP_HOST=smtp.gmail.com
# EMAIL_SMTP_PORT=587
# EMAIL_SMTP_USER=your_email@gmail.com
# EMAIL_SMTP_PASSWORD=your_app_password
# EMAIL_TO=recipient@example.com
```

**Note:** The `.env` file only needs the required variables for basic functionality. All other settings have sensible defaults. See `env.example` for all available options.

### 4. Get Refresh Token (Recommended)

For automated runs without browser interaction:

```bash
source venv/bin/activate
python src/scripts/utils/get_token.py
```

This will open your browser for Spotify authorization and generate a refresh token.

### 5. First Sync

```bash
# Sync your library (first time can take 1-2+ hours for large libraries)
python src/scripts/automation/sync.py
```

---

## 🔧 Python API

```python
from src import Spotim8

# Initialize client
sf = Spotim8.from_env(progress=True)

# Sync your library
sf.sync(owned_only=True, include_liked_songs=True)

# Access your data
playlists = sf.playlists()      # All playlists
tracks = sf.tracks()            # All tracks
artists = sf.artists()          # Artists with genres
wide = sf.library_wide()        # Everything joined
```

See [examples/01_quickstart.py](examples/01_quickstart.py) for a complete example.

---

## 📓 Notebooks

| Notebook | Description |
|----------|-------------|
| `02_analyze_library.ipynb` | Visualize your listening habits and library statistics |
| `03_playlist_analysis.ipynb` | Genre analysis and playlist clustering |
| `04_analyze_listening_history.ipynb` | Analyze actual listening patterns from Spotify exports |
| `06_identify_redundant_playlists.ipynb` | Find and consolidate similar playlists |
| `07_analyze_crashes.ipynb` | Technical log analysis and crash detection |

Prerequisites: sync your library and (optional) streaming history via CLI or dashboard first. See `src/notebooks/README.md`.

### Playlist Generation

The sync script (CLI or dashboard) creates automated playlists:

**Playlist Types:**
- 📅 **Finds** - Liked songs: `{Owner}{Prefix}{Mon}{Year}` → e.g., `AJFndsDec25`
  - Monthly: `AJFndsDec25`, `AJFndsNov25`, etc.
  - Yearly: `AJFnds24` (consolidated from older months)
- 🎯 **Top** - Most played: `{Owner}Top{Mon}{Year}` → e.g., `AJTopDec25`
  - Requires streaming history data
- 🔍 **Discovery** - New tracks: `{Owner}Dscvr{Mon}{Year}` → e.g., `AJDscvrDec25`
  - Requires streaming history data
- 🎸 **Genre-Split Monthly** - `{Genre}{Prefix}{Mon}{Year}` → e.g., `HipHopFindsDec25`, `DanceFindsDec25`
  - Automatically created for Finds playlists
- 🎵 **Master Genre Playlists** - `{Owner}am{Genre}` → e.g., `AJamHip-Hop`, `AJamElectronic`, `AJamOther`
  - **Exhaustive partitioning**: Every liked song is guaranteed to be in at least one playlist
  - All-time playlists by genre (no threshold filtering - all genres with tracks get playlists)
  - Tracks without genre classification go into "Other" playlist
  - Tracks can appear in multiple playlists if they match multiple genres

**Automatic Consolidation:**
- Last 3 months kept as monthly playlists
- Older months automatically consolidated into yearly playlists (e.g., `AJFinds24`, `AJTop24`)

### Advanced Genre Classification

The project includes **multi-dimensional genre classification** using creative approaches beyond simple artist genre tags:

**Features:**
- 🎯 **Collaborative Filtering** - Infers genres from similar tracks (shared artists, same playlists)
- 🔗 **Playlist Co-occurrence** - Tracks appearing together frequently share genre signals
- 👥 **Artist Network Analysis** - Uses collaboration patterns to infer genres
- ⏰ **Temporal Patterns** - Genre evolution over time based on release years
- 🔀 **Genre Hybrids** - Discovers tracks that blend multiple genres (e.g., "Hip-Hop + Electronic")
- 📈 **Emerging Genres** - Identifies trending genres in your library over time
- 🎨 **Dynamic Discovery** - Learns genre patterns from your library and playlists

**Enable Genre Discovery Report:**
```bash
# Add to .env file:
ENABLE_GENRE_DISCOVERY=true
```

The genre discovery report (generated after sync) shows:
- Genre clusters in your library (K-means clustering)
- Hybrid genre combinations with example tracks
- Emerging genre trends (growth rates over time)
- Your genre preferences and diversity scores

---

## 🤖 Automation

### Sync Options

```bash
# Full sync + playlist update (default)
python src/scripts/automation/sync.py

# Or use the helper script (handles environment variables)
python src/scripts/automation/runner.py

# Skip sync, only update playlists (fast, uses existing data)
python src/scripts/automation/sync.py --skip-sync

# Sync only, don't update playlists
python src/scripts/automation/sync.py --sync-only

# Process all months, not just current month
python src/scripts/automation/sync.py --all-months
```

### Scheduled Automation (Cron)

Set up daily sync on Linux/Mac:

```bash
# Easy setup (recommended):
./src/scripts/automation/cron.sh
```

The cron job runs daily at 2:00 AM and logs to `logs/sync.log`.

See [docs/features/automation.md](docs/features/automation.md) for detailed automation setup and troubleshooting.

**Features:**
- ✅ Automatic log rotation (keeps last 3 backups)
- ✅ Prevents concurrent runs with lock file mechanism
- ✅ Dependency verification before execution
- ✅ Automatic cleanup on errors
- ✅ macOS permission handling

**Manual setup** (if needed):
```bash
crontab -e
# Add: 0 2 * * * /bin/bash /path/to/SPOTIM8/src/scripts/automation/cron_wrapper.sh
```

**Test the wrapper manually:**
```bash
/bin/bash src/scripts/automation/cron_wrapper.sh --skip-sync
```

### Email Notifications

Get email notifications after each sync run. Configure in your `.env` file:

**Gmail Setup:**
1. Enable 2-factor authentication on your Gmail account
2. Generate an [App Password](https://myaccount.google.com/apppasswords)
3. Add to `.env`:
   ```bash
   EMAIL_ENABLED=true
   EMAIL_SMTP_HOST=smtp.gmail.com
   EMAIL_SMTP_PORT=587
   EMAIL_SMTP_USER=your_email@gmail.com
   EMAIL_SMTP_PASSWORD=your_16_char_app_password
   EMAIL_TO=recipient@example.com
   ```

**Other Email Providers:**
- **Outlook/Hotmail**: `smtp-mail.outlook.com`, port `587`
- **Yahoo**: `smtp.mail.yahoo.com`, port `587`
- **Custom SMTP**: Use your provider's SMTP settings

**Note:** Email failures won't break the sync - notifications are non-blocking.

### Why Local Execution?

- ✅ **No timeouts** - Large libraries can sync for hours without interruption
- ✅ **Faster** - No CI/CD overhead, direct API access
- ✅ **Resumable** - Script supports checkpointing for interrupted syncs
- ✅ **Cost-free** - Uses your own machine, no CI minutes
- ✅ **Better debugging** - Direct access to logs and data files

---


## 📁 Data Tables

| Table | Description |
|-------|-------------|
| `playlists()` | Your playlists (including ❤️ Liked Songs) |
| `playlist_tracks()` | Track-playlist relationships with `added_at` |
| `tracks()` | Track metadata (name, duration, popularity) |
| `track_artists()` | Track-artist relationships |
| `artists()` | Artist info with genres |
| `library_wide()` | Everything joined together |

---

## 🎛️ CLI

The `spotim8` command-line interface provides quick access to common operations:

```bash
# Sync library
spotim8 refresh

# Check status
spotim8 status

# Export data
spotim8 export --table tracks --out tracks.parquet

# Market data (browse/search)
spotim8 market --kind new_releases --country US --limit 50 --out releases.parquet
```

For more advanced operations, use the Python API or scripts directly.

---

## 📂 Project Structure

```
SPOTIM8/
├── src/                          # Core Python package
│   ├── __init__.py               # Package exports
│   ├── core/                     # Core functionality
│   │   ├── client.py             # Main Spotim8 class (entry point)
│   │   ├── catalog.py            # Data caching layer (parquet storage)
│   │   └── cli.py                # Command line interface
│   ├── features/                 # Feature engineering
│   │   ├── features.py           # Feature engineering utilities
│   │   ├── genres.py             # Genre classification rules
│   │   └── genre_inference.py    # Genre inference engine
│   ├── analysis/                 # Analysis utilities
│   │   ├── analysis.py           # Library analysis utilities
│   │   └── streaming_history.py  # Streaming history integration
│   ├── data/                     # Data handling modules
│   │   ├── export.py             # Data export utilities
│   │   └── market.py             # Market data (browse/search)
│   ├── utils/                    # Utility functions
│   │   ├── ratelimit.py          # Rate limiting utilities
│   │   └── utils.py              # Helper functions
│   ├── notebooks/                # Jupyter notebooks for analysis
│   │   ├── 02_analyze_library.ipynb  # Visualize listening habits
│   │   ├── 03_playlist_analysis.ipynb # Genre analysis & clustering
│   │   ├── 04_analyze_listening_history.ipynb # Analyze listening patterns
│   │   ├── 06_identify_redundant_playlists.ipynb # Find similar playlists
│   │   ├── 07_analyze_crashes.ipynb  # Technical log analysis
│   │   └── notebook_helpers.py       # Shared notebook utilities
│   └── scripts/                  # Scripts organized by category
│       ├── automation/           # Automation and sync scripts
│       │   ├── sync.py           # Main sync & playlist update script
│       │   ├── runner.py         # Local sync runner wrapper
│       │   ├── cron_wrapper.sh   # Robust cron wrapper (lock files, log rotation)
│       │   ├── cron.sh           # Cron job setup helper
│       │   ├── check_cron.sh     # Cron diagnostic tool
│       │   └── email_notify.py   # Email notification service
│       ├── playlist/             # Playlist management scripts
│       │   ├── merge_playlists.py    # Merge two playlists
│       │   ├── merge_multiple_playlists.py # Merge multiple playlists
│       │   ├── merge_to_new_playlist.py # Merge to new playlist
│       │   ├── delete_playlists.py   # Delete playlists
│       │   ├── add_genre_tags_to_descriptions.py # Add genre tags
│       │   ├── update_all_playlist_descriptions.py # Update descriptions
│       │   └── playlist_helpers.py   # Shared playlist utilities
│       ├── common/                # Shared script utilities
│       │   ├── project_path.py   # Project root path utilities
│       │   ├── sync_helpers.py   # Sync helper functions
│       │   └── setup.py          # Script setup utilities
│       └── utils/                # Utility scripts
│           ├── get_token.py      # Get refresh token for automation
│           └── setup.py          # Initial setup helper
│
├── dashboard/                    # Streamlit dashboard (optional)
│   ├── app.py                    # Run: streamlit run dashboard/app.py
│   └── README.md                 # Dashboard setup
│
├── examples/                     # Example code
│   └── 01_quickstart.py          # Quick start example
│
├── tests/                        # Test suite
│   ├── test_client.py            # Client tests
│   └── test_import.py            # Import tests
│
├── data/                         # Cached parquet files (gitignored, user data)
│   ├── *.parquet                 # Library data cache (playlists, tracks, artists, etc.)
│   └── Spotify Account Data/     # Spotify export data (gitignored)
│
├── logs/                         # Log files (gitignored)
│   └── sync.log                  # Sync operation logs
│
├── README.md                     # This file - main documentation
├── docs/                         # Detailed documentation
│   ├── getting-started/         # Installation and setup guides
│   ├── features/                 # Feature documentation
│   ├── development/              # Development guides
│   └── reference/                # Reference documentation
├── LICENSE                       # MIT License
├── pyproject.toml                # Project configuration
└── env.example                   # Environment variables template
```

### Key Directories

- **`src/`**: Core library - main Python package (import as `from src import ...`)
- **`src/core/`**: Core functionality - client, catalog, CLI
- **`src/features/`**: Feature engineering - genres, inference
- **`src/analysis/`**: Analysis utilities - library analysis, streaming history
- **`src/data/`**: Data handling modules - export, market data
- **`src/utils/`**: Utility functions - rate limiting, helpers
- **`src/notebooks/`**: Analysis notebooks - run sequentially for full workflow
- **`src/scripts/automation/`**: Sync and automation - daily cron jobs
- **`src/scripts/playlist/`**: Playlist management - merge, delete, update playlists
- **`src/scripts/common/`**: Shared script utilities - path helpers, sync helpers
- **`src/scripts/utils/`**: Utility scripts - token setup, project setup
- **`examples/`**: Code examples - quick start templates
- **`tests/`**: Test suite - unit and integration tests
- **`data/`**: User data directory (gitignored) - synced library data, parquet files

---

## 🐛 Troubleshooting

### Virtual Environment Not Found

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

### Missing Credentials Error

Make sure your `.env` file exists and has:
- `SPOTIPY_CLIENT_ID`
- `SPOTIPY_CLIENT_SECRET`

### Authentication Issues

1. Make sure your redirect URI matches exactly: `http://127.0.0.1:8888/callback`
2. Get a fresh refresh token: `python src/scripts/utils/get_token.py`
3. Check that your Spotify app is not in "Development Mode" with restricted users (if using a free account)

### Sync Takes Too Long

- First sync always takes longest (hours for large libraries)
- Use `--skip-sync` to only update playlists without re-syncing:
  ```bash
  python src/scripts/automation/runner.py --skip-sync
  ```

### Check Logs

```bash
tail -f logs/sync.log
```

---

## 🔒 Security & Secrets

**Do NOT commit secrets** (client IDs, client secrets, refresh tokens) to this repository.

- Keep local credentials in a `.env` file and never commit it
- This repository already ignores `.env` and common secret files via `.gitignore`
- If you accidentally commit a secret, rotate it immediately (revoke the secret in the provider) and remove it from git history

---

## 🤝 Contributing

Thank you for your interest in contributing to Spotim8!

We welcome contributions! Please see [docs/development/contributing.md](docs/development/contributing.md) for detailed guidelines on:
- Development setup
- Code style and standards
- Testing requirements
- Pull request process
- Documentation guidelines

### Quick Start for Contributors

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests (install dev deps first: pip install -e ".[dev]")
pytest tests/

# Format code
black src/

# Lint code
ruff check src/
```

---

## 📝 Spotify API Notes

Spotify deprecated these endpoints for new apps (Nov 2024):
- ❌ Audio features (danceability, energy, etc.)
- ❌ Audio analysis
- ⚠️ Recommendations (may work for older apps)

This library focuses on what's still available.

---

## 📄 License

MIT - See [LICENSE](LICENSE) for details.

---

🎓 **Open Source Academic Project** - Built for learning and personal use.
