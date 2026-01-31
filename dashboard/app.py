"""
Spotim8 Dashboard — minimal GUI for sync, reports, and playlist operations.

Run: streamlit run dashboard/app.py
Requires: pip install -e ".[dashboard]"
"""

import os
import subprocess
import sys
from pathlib import Path

# Resolve project root and load .env before any spotim8 imports
def _bootstrap():
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    env = root / ".env"
    if env.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env)
        except ImportError:
            pass
    return root

PROJECT_ROOT = _bootstrap()

import streamlit as st

st.set_page_config(
    page_title="Spotim8",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Minimal custom CSS for a clean, modern look
st.markdown("""
<style>
    .stApp { max-width: 1200px; margin: 0 auto; }
    h1 { font-weight: 600; letter-spacing: -0.02em; }
    h2, h3 { font-weight: 500; }
    .metric-card { padding: 1rem; border-radius: 8px; background: var(--background-secondary); margin-bottom: 0.5rem; }
    .success-box { padding: 0.75rem 1rem; border-radius: 6px; background: #0d3b0d; color: #b8e6b8; }
    .output-box { font-family: ui-monospace, monospace; font-size: 0.85rem; white-space: pre-wrap; }
</style>
""", unsafe_allow_html=True)

def _run_script(script_path: str, args: list[str], cwd: Path) -> tuple[str, int]:
    """Run a Python script; return (stdout+stderr, returncode)."""
    cmd = [sys.executable, script_path] + args
    try:
        r = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=600,
        )
        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        combined = (out + "\n" + err).strip() or "(no output)"
        return combined, r.returncode
    except subprocess.TimeoutExpired:
        return "Command timed out after 10 minutes.", -1
    except Exception as e:
        return f"Error: {e}", -1

def _data_status():
    """Show data directory and parquet file status."""
    try:
        from src.scripts.automation.config import DATA_DIR
    except Exception:
        DATA_DIR = PROJECT_ROOT / "data"
    st.subheader("Data directory")
    st.code(str(DATA_DIR), language=None)
    if not DATA_DIR.exists():
        st.info("Data directory does not exist yet. Run a full sync to create it.")
        return
    parquets = list(DATA_DIR.glob("*.parquet"))
    if not parquets:
        st.info("No parquet files yet. Run a full sync.")
        return
    cols = st.columns(min(4, len(parquets)))
    for i, p in enumerate(parquets[:8]):
        with cols[i % 4]:
            try:
                n = len(__import__("pandas").read_parquet(p))
                st.metric(p.name, f"{n:,} rows")
            except Exception:
                st.metric(p.name, "—")
    try:
        from src import Spotim8, CacheConfig
        sf = Spotim8.from_env(progress=False, cache=CacheConfig(dir=DATA_DIR))
        status = sf.status()
        st.subheader("Library status")
        st.json(status)
    except Exception as e:
        st.caption(f"Status unavailable: {e}")

def _sync_page():
    st.subheader("Sync & playlist updates")
    st.caption("Sync library to parquet files and/or update playlists (monthly, genre-split, master genre, descriptions).")
    mode = st.radio("Mode", ["Full sync + update", "Update only (skip sync)", "Sync only (no playlists)"], horizontal=True)
    verbose = st.checkbox("Verbose", value=False)
    force = st.checkbox("Force full sync", value=False) if "sync" in mode.lower() else False
    sync_script = PROJECT_ROOT / "src" / "scripts" / "automation" / "sync.py"
    if not sync_script.exists():
        st.error("Sync script not found.")
        return
    args = []
    if "Update only" in mode:
        args.append("--skip-sync")
    elif "Sync only" in mode:
        args.append("--sync-only")
    if verbose:
        args.append("--verbose")
    if force:
        args.append("--force")
    if st.button("Run", type="primary", key="sync_run"):
        with st.spinner("Running…"):
            out, code = _run_script(str(sync_script), args, PROJECT_ROOT)
        st.subheader("Output")
        st.code(out, language="text")
        if code == 0:
            st.success("Completed successfully.")
        else:
            st.warning(f"Exit code: {code}")

def _reports_page():
    st.subheader("Reports")
    st.caption("Health check, listening insights, and genre discovery.")
    script_dir = PROJECT_ROOT / "src" / "scripts" / "automation"
    report_type = st.selectbox(
        "Report",
        ["Health check", "Listening insights", "Genre discovery"],
        key="report_type",
    )
    if report_type == "Genre discovery":
        # Genre discovery has no CLI; run in-process
        if st.button("Run report", type="primary", key="report_run"):
            try:
                from src.scripts.automation.config import DATA_DIR
                from src.scripts.automation.genre_enhancement import generate_genre_discovery_report
                import pandas as pd
                playlists_path = DATA_DIR / "playlists.parquet"
                playlist_tracks_path = DATA_DIR / "playlist_tracks.parquet"
                tracks_path = DATA_DIR / "tracks.parquet"
                track_artists_path = DATA_DIR / "track_artists.parquet"
                artists_path = DATA_DIR / "artists.parquet"
                streaming_path = DATA_DIR / "streaming_history.parquet"
                if not all(p.exists() for p in [playlists_path, playlist_tracks_path, tracks_path, track_artists_path, artists_path]):
                    st.warning("Data files missing. Run a full sync first.")
                else:
                    with st.spinner("Generating…"):
                        playlists_df = pd.read_parquet(playlists_path)
                        playlist_tracks_df = pd.read_parquet(playlist_tracks_path)
                        tracks_df = pd.read_parquet(tracks_path)
                        track_artists_df = pd.read_parquet(track_artists_path)
                        artists_df = pd.read_parquet(artists_path)
                        streaming_df = pd.read_parquet(streaming_path) if streaming_path.exists() else None
                        report = generate_genre_discovery_report(
                            tracks_df, track_artists_df, artists_df,
                            playlist_tracks_df, playlists_df, streaming_df,
                        )
                    st.subheader("Output")
                    st.text(report)
                    st.success("Done.")
            except Exception as e:
                st.exception(e)
        return
    scripts = {
        "Health check": (script_dir / "health_check.py", ["--empty", "--stale"]),
        "Listening insights": (script_dir / "insights_report.py", []),
    }
    target, report_args = scripts[report_type]
    if not target.exists():
        st.error(f"Script not found: {target}")
        return
    if st.button("Run report", type="primary", key="report_run"):
        with st.spinner("Running…"):
            out, code = _run_script(str(target), report_args, PROJECT_ROOT)
        st.subheader("Output")
        st.code(out, language="text")
        if code == 0:
            st.success("Done.")
        else:
            st.caption(f"Exit code: {code}")

def _playlist_ops_page():
    st.subheader("Playlist operations")
    st.caption("Update descriptions, add genre tags. Merge/delete via scripts.")
    script_playlist = PROJECT_ROOT / "src" / "scripts" / "playlist"
    # Update all descriptions
    update_desc = script_playlist / "update_all_playlist_descriptions.py"
    if update_desc.exists():
        if st.button("Update all playlist descriptions", key="update_desc"):
            with st.spinner("Updating…"):
                out, code = _run_script(str(update_desc), [], PROJECT_ROOT)
            st.code(out, language="text")
            st.success("Done." if code == 0 else f"Exit code: {code}")
    # Add genre tags
    add_genre = script_playlist / "add_genre_tags_to_descriptions.py"
    if add_genre.exists():
        if st.button("Add genre tags to descriptions", key="add_genre"):
            with st.spinner("Running…"):
                out, code = _run_script(str(add_genre), [], PROJECT_ROOT)
            st.code(out, language="text")
            st.success("Done." if code == 0 else f"Exit code: {code}")
    st.divider()
    st.caption("Merge / delete playlists: use CLI from project root:")
    st.code("python src/scripts/playlist/merge_multiple_playlists.py ...\npython src/scripts/playlist/delete_playlists.py ...", language="bash")

def _overview_page():
    st.subheader("Overview")
    _data_status()

def main():
    st.title("🎵 Spotim8")
    st.caption("Sync, reports, and playlist operations")
    sidebar = st.sidebar
    sidebar.title("Spotim8")
    page = sidebar.radio(
        "Section",
        ["Overview", "Sync", "Reports", "Playlist ops"],
        label_visibility="collapsed",
    )
    if page == "Overview":
        _overview_page()
    elif page == "Sync":
        _sync_page()
    elif page == "Reports":
        _reports_page()
    else:
        _playlist_ops_page()

if __name__ == "__main__":
    main()
