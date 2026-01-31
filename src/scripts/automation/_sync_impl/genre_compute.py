"""
Incremental track genre computation with smart caching.

Only re-infers genres for tracks that have changed (new tracks, playlists updated,
artists enhanced). Uses parallel processing when beneficial.
"""

import os
import sys
import multiprocessing as mp
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
from tqdm import tqdm

from src.features.genre_inference import (
    infer_genres_comprehensive,
    enhance_artist_genres_from_playlists,
)
from src.scripts.common.config_helpers import parse_bool_env

from .logger import log, verbose_log
from .settings import DATA_DIR, PARALLEL_MIN_TRACKS
from .tracks import _parse_genres


def compute_track_genres_incremental(stats: dict = None) -> None:
    """Compute and store track genres with smart caching.

    Only re-infers genres for tracks that have changed:
    - New tracks (not yet inferred)
    - Tracks in playlists that were updated
    - Tracks whose artists had genres enhanced
    """
    log("\n--- Computing Track Genres (Smart Caching) ---")

    try:
        tracks_path = DATA_DIR / "tracks.parquet"
        track_artists_path = DATA_DIR / "track_artists.parquet"
        artists_path = DATA_DIR / "artists.parquet"
        playlist_tracks_path = DATA_DIR / "playlist_tracks.parquet"
        playlists_path = DATA_DIR / "playlists.parquet"

        if not all(
            p.exists()
            for p in [
                tracks_path,
                track_artists_path,
                artists_path,
                playlist_tracks_path,
                playlists_path,
            ]
        ):
            log("  ⚠️  Missing required data files, skipping genre computation")
            return

        verbose_log(f"Loading parquet files from {DATA_DIR}...")
        try:
            verbose_log("  Attempting to load with pyarrow engine...")
            tracks = pd.read_parquet(tracks_path, engine="pyarrow")
            verbose_log(f"    Loaded tracks: {len(tracks):,} rows")
            track_artists = pd.read_parquet(track_artists_path, engine="pyarrow")
            verbose_log(f"    Loaded track_artists: {len(track_artists):,} rows")
            artists = pd.read_parquet(artists_path, engine="pyarrow")
            verbose_log(f"    Loaded artists: {len(artists):,} rows")
            playlist_tracks = pd.read_parquet(playlist_tracks_path, engine="pyarrow")
            verbose_log(f"    Loaded playlist_tracks: {len(playlist_tracks):,} rows")
            playlists = pd.read_parquet(playlists_path, engine="pyarrow")
            verbose_log(f"    Loaded playlists: {len(playlists):,} rows")
        except Exception as e:
            verbose_log(f"  PyArrow not available, using default engine: {e}")
            tracks = pd.read_parquet(tracks_path)
            track_artists = pd.read_parquet(track_artists_path)
            artists = pd.read_parquet(artists_path)
            playlist_tracks = pd.read_parquet(playlist_tracks_path)
            playlists = pd.read_parquet(playlists_path)

        if "genres" not in tracks.columns:
            tracks["genres"] = None

        tracks_needing_inference = set()

        def needs_genres(genres_val):
            if genres_val is None:
                return True
            if isinstance(genres_val, np.ndarray):
                return len(genres_val) == 0
            if isinstance(genres_val, list):
                return len(genres_val) == 0
            try:
                if pd.api.types.is_scalar(genres_val) and pd.isna(genres_val):
                    return True
            except (ValueError, TypeError):
                pass
            try:
                if hasattr(genres_val, "__len__"):
                    return len(genres_val) == 0
            except (TypeError, AttributeError):
                pass
            return True

        tracks_without_genres = tracks[tracks["genres"].apply(needs_genres)]
        tracks_needing_inference.update(tracks_without_genres["track_id"].tolist())

        if stats and stats.get("tracks_added", 0) > 0:
            playlist_track_ids = set(playlist_tracks["track_id"].unique())

            def has_valid_genres(genres_val):
                if genres_val is None or pd.isna(genres_val):
                    return False
                if isinstance(genres_val, list):
                    return len(genres_val) > 0
                return False

            tracks_with_genres = set(
                tracks[tracks["genres"].apply(has_valid_genres)]["track_id"].tolist()
            )
            new_track_ids = playlist_track_ids - tracks_with_genres
            tracks_needing_inference.update(new_track_ids)

        total_tracks = len(tracks)
        needs_inference = len(tracks_needing_inference)
        already_has_genres = total_tracks - needs_inference

        if needs_inference == 0:
            log(f"  ✅ All {total_tracks:,} tracks already have genres (smart cache hit)")
            return

        log(f"  📊 Genre status: {already_has_genres:,} cached, {needs_inference:,} need inference")

        if stats and (
            stats.get("playlists_updated", 0) > 0 or stats.get("tracks_added", 0) > 0
        ):
            tracks_with_genres_pct = (
                (already_has_genres / total_tracks * 100) if total_tracks > 0 else 0
            )
            if tracks_with_genres_pct < 90:
                artists_without_genres = artists[
                    artists["genres"].apply(
                        lambda g: g is None
                        or (isinstance(g, list) and len(g) == 0)
                        or (pd.api.types.is_scalar(g) and pd.isna(g))
                    )
                ]
                if len(artists_without_genres) > 500:
                    log(
                        f"  ⏭️  Skipping artist genre enhancement (too many artists without genres: {len(artists_without_genres):,})"
                    )
                else:
                    tqdm.write("  🔄 Enhancing artist genres from playlist patterns...")
                    artists_before = artists.copy()
                    artists_enhanced = enhance_artist_genres_from_playlists(
                        artists, track_artists, playlist_tracks, playlists
                    )
                    enhanced_artist_ids = set()
                    artists_dict_before = artists_before.set_index("artist_id")[
                        "genres"
                    ].to_dict()
                    artists_dict_after = artists_enhanced.set_index("artist_id")[
                        "genres"
                    ].to_dict()
                    for artist_id in artists_dict_after.keys():
                        old_genres = set(
                            _parse_genres(artists_dict_before.get(artist_id, []))
                        )
                        new_genres = set(
                            _parse_genres(artists_dict_after.get(artist_id, []))
                        )
                        if old_genres != new_genres:
                            enhanced_artist_ids.add(artist_id)
                    if enhanced_artist_ids:
                        artists_enhanced.to_parquet(artists_path, index=False)
                        artists = artists_enhanced
                        enhanced_track_ids = track_artists[
                            track_artists["artist_id"].isin(enhanced_artist_ids)
                        ]["track_id"].unique()
                        tracks_needing_inference.update(enhanced_track_ids)
                        tqdm.write(
                            f"  ✨ Enhanced {len(enhanced_artist_ids)} artists - re-inferring {len(enhanced_track_ids)} tracks"
                        )
                    else:
                        artists = artists_enhanced
            else:
                log(
                    f"  ⏭️  Skipping artist genre enhancement ({tracks_with_genres_pct:.1f}% tracks already have genres)"
                )
        else:
            log("  ⏭️  Skipping artist genre enhancement (no playlist changes)")

        tracks_to_process = tracks[
            tracks["track_id"].isin(tracks_needing_inference)
        ]

        if len(tracks_to_process) == 0:
            log("  ✅ All tracks up to date (smart cache hit)")
            return

        tqdm.write(f"  🔄 Inferring genres for {len(tracks_to_process):,} track(s)...")

        num_workers = int(
            os.environ.get("GENRE_INFERENCE_WORKERS", min(mp.cpu_count() or 4, 8))
        )
        use_parallel = parse_bool_env(
            "USE_PARALLEL_GENRE_INFERENCE", True
        ) and len(tracks_to_process) > PARALLEL_MIN_TRACKS

        track_data_list = [
            {
                "track_id": row.track_id,
                "track_name": getattr(row, "name", None),
                "album_name": getattr(row, "album_name", None),
            }
            for row in tracks_to_process.itertuples()
        ]

        inferred_genres_map = {}

        if use_parallel and num_workers > 1:
            tqdm.write(
                f"  🚀 Using {num_workers} parallel workers for genre inference..."
            )
            verbose_log(f"Parallel processing enabled with {num_workers} workers")

            def _process_track(track_data):
                try:
                    track_id = track_data["track_id"]
                    track_name = track_data["track_name"]
                    album_name = track_data["album_name"]
                    genres = infer_genres_comprehensive(
                        track_id=track_id,
                        track_name=track_name,
                        album_name=album_name,
                        track_artists=track_artists,
                        artists=artists,
                        playlist_tracks=playlist_tracks,
                        playlists=playlists,
                        mode="broad",
                    )
                    return (track_id, genres)
                except Exception:
                    return (track_data.get("track_id", ""), [])

            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = {
                    executor.submit(_process_track, td): td["track_id"]
                    for td in track_data_list
                }
                with tqdm(
                    total=len(track_data_list),
                    desc="  Inferring genres",
                    unit="track",
                    ncols=100,
                    leave=False,
                    file=sys.stderr,
                    dynamic_ncols=True,
                    mininterval=0.5,
                ) as pbar:
                    for future in as_completed(futures):
                        try:
                            track_id, genres = future.result(timeout=30)
                            inferred_genres_map[track_id] = genres
                        except Exception as e:
                            track_id = futures[future]
                            tqdm.write(
                                f"  ⚠️  Error inferring genres for {track_id}: {e}"
                            )
                            inferred_genres_map[track_id] = []
                        finally:
                            pbar.update(1)
        else:
            verbose_log(
                f"Sequential processing (parallel disabled or small batch: {len(track_data_list)} tracks)"
            )
            track_iterator = tracks_to_process.itertuples()
            if len(tracks_to_process) > 0:
                track_iterator = tqdm(
                    track_iterator,
                    total=len(tracks_to_process),
                    desc="  Inferring genres",
                    unit="track",
                    ncols=100,
                    leave=False,
                    file=sys.stderr,
                    dynamic_ncols=True,
                    mininterval=0.5,
                )
            for track_row in track_iterator:
                track_id = track_row.track_id
                track_name = getattr(track_row, "name", None)
                album_name = getattr(track_row, "album_name", None)
                try:
                    genres = infer_genres_comprehensive(
                        track_id=track_id,
                        track_name=track_name,
                        album_name=album_name,
                        track_artists=track_artists,
                        artists=artists,
                        playlist_tracks=playlist_tracks,
                        playlists=playlists,
                        mode="broad",
                    )
                    inferred_genres_map[track_id] = genres
                except Exception as e:
                    tqdm.write(
                        f"  ⚠️  Error inferring genres for {track_id}: {e}"
                    )
                    inferred_genres_map[track_id] = []

        if inferred_genres_map:
            tqdm.write("  💾 Updating track genres...")
            track_id_to_row_idx = {}
            for idx, track_id in tracks["track_id"].items():
                if track_id in inferred_genres_map:
                    track_id_to_row_idx[track_id] = idx
            for track_id, genres in inferred_genres_map.items():
                if track_id in track_id_to_row_idx:
                    tracks.at[track_id_to_row_idx[track_id], "genres"] = genres
            try:
                tracks.to_parquet(tracks_path, index=False, engine="pyarrow")
            except Exception:
                tracks.to_parquet(tracks_path, index=False)

        def has_valid_genre(g):
            if g is None:
                return False
            try:
                if pd.api.types.is_scalar(g) and pd.isna(g):
                    return False
                if isinstance(g, list):
                    return len(g) > 0
                if isinstance(g, (np.ndarray, pd.Series)):
                    return len(g) > 0
                return bool(g)
            except (ValueError, TypeError):
                return False

        tracks_with_genres_after = tracks["genres"].apply(has_valid_genre).sum()
        log(
            f"  ✅ Inferred genres for {len(inferred_genres_map):,} track(s) ({tracks_with_genres_after:,} total tracks with genres)"
        )

    except Exception as e:
        log(f"  ⚠️  Genre inference error (non-fatal): {e}")
        import traceback

        traceback.print_exc()
