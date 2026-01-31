"""
Mood inference during sync (Music2Emo).

Precomputes mood for liked tracks and fills the mood cache so description
updates can use cached results. Uses Spotify preview URLs only.
"""

import spotipy

from .logger import log, verbose_log
from .settings import get_sync_data_dir, LIKED_SONGS_PLAYLIST_ID
from .tracks import _get_preview_urls_for_tracks


def run_mood_inference_on_sync(sp: spotipy.Spotify) -> None:
    """
    Run Music2Emo mood inference during sync: precompute mood for liked tracks
    and fill the mood cache so description updates can use cached results.
    Uses Spotify preview URLs only; no local audio files required.
    """
    log("  Mood inference: checking Music2Emo and data...")
    try:
        from src.features.mood_inference import get_mood_counts_from_audio
    except ImportError:
        log("  Mood inference: skipped (Music2Emo not installed)")
        verbose_log("  Install music2emo to enable song-level mood inference")
        return
    sync_data_dir = get_sync_data_dir()
    pt_path = sync_data_dir / "playlist_tracks.parquet"
    if not pt_path.exists():
        log(f"  Mood inference: skipped (playlist_tracks.parquet not found at {pt_path})")
        return
    import pandas as _pd
    library = _pd.read_parquet(pt_path)
    liked = library[library["playlist_id"].astype(str) == LIKED_SONGS_PLAYLIST_ID]
    if liked.empty:
        log("  Mood inference: skipped (no liked tracks in library)")
        return
    if "track_uri" in liked.columns:
        track_uris = liked["track_uri"].dropna().unique().tolist()
    else:
        track_uris = [f"spotify:track:{tid}" for tid in liked["track_id"].dropna().unique().tolist()]
    if not track_uris:
        log("  Mood inference: skipped (no track URIs)")
        return
    log(f"  Mood inference: {len(track_uris):,} liked tracks; fetching preview URLs from Spotify...")
    verbose_log(f"  Fetching preview URLs in batches of 50 (total {len(track_uris):,} tracks)...")
    preview_urls = _get_preview_urls_for_tracks(sp, track_uris)
    n_with_preview = len(preview_urls)
    if not preview_urls:
        log("  Mood inference: skipped (no preview URLs returned by Spotify for liked tracks)")
        verbose_log("  Many tracks do not have 30s previews; mood tags will be empty until previews exist")
        return
    log(f"  Mood inference: {n_with_preview:,} tracks have previews; running Music2Emo (cache: {sync_data_dir / '.mood_cache'})...")
    verbose_log(f"  Music2Emo will download previews, run model, and cache results per track")
    mood_cache_dir = sync_data_dir / ".mood_cache"

    def _mood_progress(processed: int, total: int, from_cache: int) -> None:
        verbose_log(f"  Mood inference progress: {processed:,}/{total:,} tracks ({from_cache:,} from cache)")

    get_mood_counts_from_audio(
        track_uris, preview_urls, cache_dir=mood_cache_dir, progress_callback=_mood_progress
    )
    log(f"  Mood inference: complete (cache at {mood_cache_dir})")
    verbose_log(f"  Description updates will use cached moods for playlists containing these tracks")
