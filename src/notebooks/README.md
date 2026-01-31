# Analysis Notebooks

Demonstrative notebooks for **views, analysis, and visualization** only. Sync and automation are handled by CLI or the dashboard.

**Prerequisites:** Sync your library first (CLI: `python src/scripts/automation/sync.py` or use the Streamlit dashboard). Data lives in `data/` (under the SPOTIM8 project root).

| Notebook | Description |
|----------|-------------|
| `02_analyze_library.ipynb` | Library overview, stats, top artists/genres, popularity, release year, hidden gems |
| `03_playlist_analysis.ipynb` | Genre breakdown per playlist, similarity clustering, taste profile |
| `04_analyze_listening_history.ipynb` | Listening patterns, streaming history, search/discovery |
| `06_identify_redundant_playlists.ipynb` | Redundant playlists, overlap, consolidation suggestions |
| `07_analyze_crashes.ipynb` | Playback errors, crash patterns |

Each notebook: setup path → load data (function) → analysis & visualization (function calls).
