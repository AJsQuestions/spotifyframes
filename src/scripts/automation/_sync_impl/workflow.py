"""
Sync workflow: full library sync and export data sync.

Orchestrates spotim8 library sync, genre inference, and optional export data sync.
"""

import os
from pathlib import Path

import pandas as pd

from src import Spotim8, CacheConfig, set_response_cache, sync_all_export_data
from src.scripts.automation.error_handling import handle_errors
from src.scripts.common.config_helpers import parse_bool_env as _parse_bool_env

from .logger import log, verbose_log, timed_step
from .settings import DATA_DIR
from .genre_compute import compute_track_genres_incremental


@handle_errors(reraise=True, log_error=True)
def sync_full_library(force: bool = False) -> bool:
    """
    Sync full library using spotim8 - updates all parquet files.

    Uses incremental sync - only fetches playlists that have changed
    based on Spotify's snapshot_id mechanism.
    """
    log("\n--- Full Library Sync ---")

    try:
        api_cache_dir = DATA_DIR / ".api_cache"
        set_response_cache(api_cache_dir, ttl=3600)

        sf = Spotim8.from_env(
            progress=True,
            cache=CacheConfig(dir=DATA_DIR),
        )

        existing_status = sf.status()
        if existing_status.get("playlist_tracks_count", 0) > 0:
            log(f"📦 Found cached data from {existing_status.get('last_sync', 'unknown')}")
            log(f"   • {existing_status.get('playlists_count', 0):,} playlists")
            log(f"   • {existing_status.get('playlist_tracks_count', 0):,} playlist tracks")
            log(f"   • {existing_status.get('tracks_count', 0):,} unique tracks")
            log(f"   • {existing_status.get('artists_count', 0):,} artists")
            log("🔄 Running incremental sync (only changed playlists)...")
            verbose_log(f"Cache directory: {DATA_DIR}")
            verbose_log(f"API cache directory: {api_cache_dir}")
        else:
            log("📭 No cached data found - running full sync...")
            verbose_log(f"Cache directory: {DATA_DIR}")
            verbose_log(f"API cache directory: {api_cache_dir}")

        with timed_step("Spotify Library Sync (API calls)"):
            stats = sf.sync(
                force=force,
                owned_only=True,
                include_liked_songs=True,
            )

        with timed_step("Load All Playlists"):
            _ = sf.playlists(force=force)

        log(f"✅ Library sync complete: {stats}")

        if stats.get("playlists_updated", 0) > 0 or stats.get("tracks_added", 0) > 0:
            with timed_step("Regenerate Derived Tables"):
                log("🔧 Regenerating derived tables...")
                verbose_log(f"Stats: {stats}")
                verbose_log("Loading tracks table...")
                _ = sf.tracks()
                verbose_log("Loading artists table...")
                _ = sf.artists()
                verbose_log("Loading library_wide table...")
                _ = sf.library_wide()
                log("✅ All parquet files updated")
        else:
            log("✅ No changes detected - using cached derived tables")
            verbose_log(f"Stats: {stats}")

        if stats and stats.get("tracks_added", 0) == 0 and stats.get("playlists_updated", 0) == 0:
            log("  ⏭️  Skipping genre inference (no changes detected - using cached data)")
        else:
            with timed_step("Genre Inference Check"):
                try:
                    try:
                        verbose_log("Loading tracks.parquet with pyarrow engine...")
                        tracks_check = pd.read_parquet(DATA_DIR / "tracks.parquet", engine="pyarrow")
                        verbose_log(f"Loaded {len(tracks_check):,} tracks using pyarrow")
                    except Exception:
                        verbose_log("Loading tracks.parquet with default engine (pyarrow not available)...")
                        tracks_check = pd.read_parquet(DATA_DIR / "tracks.parquet")
                        verbose_log(f"Loaded {len(tracks_check):,} tracks using default engine")

                    tracks_needing = tracks_check[
                        tracks_check["genres"].apply(
                            lambda g: g is None
                            or (isinstance(g, list) and len(g) == 0)
                            or (pd.api.types.is_scalar(g) and pd.isna(g))
                        )
                    ]
                    if len(tracks_needing) == 0:
                        log("  ⏭️  Skipping genre inference (all tracks already have genres)")
                    else:
                        max_tracks_for_inference = int(
                            os.environ.get("MAX_TRACKS_FOR_INFERENCE", "10000")
                        )
                        enable_inference = _parse_bool_env("ENABLE_GENRE_INFERENCE", True)

                        if not enable_inference:
                            log("  ⏭️  Skipping genre inference (disabled via ENABLE_GENRE_INFERENCE)")
                        elif len(tracks_needing) > max_tracks_for_inference:
                            log(
                                f"  ⏭️  Skipping genre inference ({len(tracks_needing):,} tracks need inference - exceeds limit of {max_tracks_for_inference:,})"
                            )
                            log("      Set MAX_TRACKS_FOR_INFERENCE env var to increase limit")
                        else:
                            with timed_step("Genre Inference Processing"):
                                log(f"  🔄 Processing genre inference for {len(tracks_needing):,} tracks...")
                                compute_track_genres_incremental(stats)
                except Exception as e:
                    log(f"  ⏭️  Skipping genre inference (error: {e})")

        with timed_step("Sync Export Data"):
            try:
                log("  🔄 Starting export data sync...")
                sync_export_data()
                log("  ✅ Export data sync completed")
            except KeyboardInterrupt:
                log("  ⚠️  Export data sync interrupted by user")
                raise
            except Exception as e:
                log(f"  ⚠️  Export data sync error (non-fatal, continuing): {e}")
                import traceback
                log(traceback.format_exc())

        return True

    except Exception as e:
        log(f"ERROR: Full library sync failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def sync_export_data() -> bool:
    """
    Sync all Spotify export data (Account Data, Extended History, Technical Logs).
    """
    log("\n--- Export Data Sync ---")

    try:
        account_data_dir = DATA_DIR / "Spotify Account Data"
        extended_history_dir = DATA_DIR / "Spotify Extended Streaming History"
        technical_log_dir = DATA_DIR / "Spotify Technical Log Information"

        if not any(
            [
                account_data_dir.exists(),
                extended_history_dir.exists(),
                technical_log_dir.exists(),
            ]
        ):
            log("ℹ️  No export folders found - skipping export data sync")
            log(f"   Place export folders in {DATA_DIR} to enable:")
            log("   - Spotify Account Data/")
            log("   - Spotify Extended Streaming History/")
            log("   - Spotify Technical Log Information/")
            return True

        results = sync_all_export_data(
            account_data_dir=account_data_dir if account_data_dir.exists() else Path("/tmp"),
            extended_history_dir=extended_history_dir if extended_history_dir.exists() else Path("/tmp"),
            technical_log_dir=technical_log_dir if technical_log_dir.exists() else Path("/tmp"),
            data_dir=DATA_DIR,
            force=False,
        )

        log("\n📊 Export Data Sync Summary:")
        for key, value in results.items():
            if value is not None and value is not False:
                if isinstance(value, int):
                    log(f"   ✅ {key}: {value:,} records")
                else:
                    log(f"   ✅ {key}: synced")
            else:
                log(f"   ⚠️  {key}: not available")

        return True

    except Exception as e:
        log(f"❌ Export data sync failed: {e}")
        import traceback
        log(traceback.format_exc())
        return False
