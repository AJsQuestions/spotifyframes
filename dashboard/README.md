# Spotim8 Dashboard

Minimal Streamlit GUI for sync, reports, and playlist operations.

## Run

```bash
# From project root (with dashboard deps installed)
pip install -e ".[dashboard]"
streamlit run dashboard/app.py
```

## Sections

- **Overview** — Data directory, parquet files, library status
- **Sync** — Full sync + update, update only, or sync only (with verbose/force)
- **Reports** — Health check, listening insights, genre discovery
- **Playlist ops** — Update all descriptions, add genre tags; CLI hints for merge/delete

Ensure `.env` is configured (Spotify credentials, etc.) in the project root.
