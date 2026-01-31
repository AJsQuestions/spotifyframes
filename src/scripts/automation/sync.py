#!/usr/bin/env python3
"""
Unified Spotify Sync & Playlist Update

This script:
1. Syncs your Spotify library to local parquet files using src (optional)
2. Consolidates old monthly playlists into yearly genre-split playlists
3. Updates monthly playlists with liked songs (last 3 months only)
4. Updates genre-split monthly playlists (HipHop, Dance, Other)
5. Updates master genre playlists (incremental on every sync: new liked songs are
   categorized and assigned to exactly one master genre playlist; unliked tracks
   are removed so the partition stays in sync)

IMPORTANT: For monthly/yearly playlists, this script only ADDS tracks; it never
removes tracks, and manually added tracks are preserved. Master genre playlists
(AJam) are an exception: they are kept in sync with your current liked library,
so unliked tracks are removed from them and new liked songs are added to exactly
one genre playlist on every sync.

DATA PROTECTION: All destructive operations (track removal, playlist deletion) are
protected with automatic backups and verification to prevent data loss. Backups are
stored in data/.backups/ and can be restored if needed.

The script automatically loads environment variables from .env file if python-dotenv
is installed and a .env file exists in the project root.

Usage:
    python src/scripts/automation/sync.py              # Full sync + update
    python src/scripts/automation/sync.py --skip-sync  # Update only (fast, uses existing data)
    python src/scripts/automation/sync.py --sync-only  # Sync only, no playlist changes
    python src/scripts/automation/sync.py --all-months # Process all months, not just current

Environment Variables (set in .env file or environment):
    Required:
        SPOTIPY_CLIENT_ID       - Spotify app client ID
        SPOTIPY_CLIENT_SECRET   - Spotify app client secret
    
    Optional:
        SPOTIPY_REDIRECT_URI    - Redirect URI (default: http://127.0.0.1:8888/callback)
        SPOTIPY_REFRESH_TOKEN   - Refresh token for headless/CI auth
        PLAYLIST_OWNER_NAME     - Prefix for playlist names (default: "AJ")
        PLAYLIST_PREFIX         - Month playlist prefix (default: "Finds")
        
        Email Notifications (optional):
        EMAIL_ENABLED           - Enable email notifications (true/false)
        EMAIL_SMTP_HOST         - SMTP server (e.g., smtp.gmail.com)
        EMAIL_SMTP_PORT         - SMTP port (default: 587)
        EMAIL_SMTP_USER         - SMTP username
        EMAIL_SMTP_PASSWORD     - SMTP password (use app password for Gmail)
        EMAIL_TO                - Recipient email address
        EMAIL_FROM              - Sender email (defaults to EMAIL_SMTP_USER)
        EMAIL_SUBJECT_PREFIX    - Subject prefix (default: "[Spotify Sync]")

Run locally or via cron:
    # Direct run (loads .env automatically):
    python src/scripts/automation/sync.py
    
    # Via wrapper (for cron):
    python src/scripts/automation/runner.py
    
    # Linux/Mac cron (every day at 2am):
    0 2 * * * cd /path/to/spotim8 && /path/to/venv/bin/python src/scripts/automation/runner.py
"""

import argparse
import os
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", message=".*urllib3.*OpenSSL.*", category=UserWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")
warnings.filterwarnings("ignore", category=UserWarning, message=".*Converting to PeriodArray.*")

try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

# Canonical project root (SPOTIM8 directory) and path setup
from src.scripts.common.project_path import get_project_root
PROJECT_ROOT = get_project_root(__file__)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if DOTENV_AVAILABLE:
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)

# Spotim8 client/sync used inside _sync_impl.workflow; re-exported below for backward compat.
# Import genre classification functions from shared module
from src.features.genres import (
    SPLIT_GENRES,
    get_split_genre, get_broad_genre,
    get_all_split_genres, get_all_broad_genres
)

# Import comprehensive genre inference
from src.features.genre_inference import (
    infer_genres_comprehensive,
    enhance_artist_genres_from_playlists
)

# Import configuration from config module
from src.scripts.automation.config import *

# Import formatting utilities from formatting module
from src.scripts.automation.formatting import format_playlist_name, format_playlist_description, format_yearly_playlist_name

# Import playlist operations from extracted modules
from src.scripts.automation.playlist_creation import create_or_update_playlist
from src.scripts.automation.playlist_update import update_monthly_playlists, update_genre_split_playlists, update_master_genre_playlists
from src.scripts.automation.playlist_consolidation import consolidate_old_monthly_playlists, delete_old_monthly_playlists, delete_duplicate_playlists

# Import standardized API wrapper
from src.scripts.common.api_wrapper import api_call as standard_api_call, safe_api_call

# Import error handling decorators
from src.scripts.automation.error_handling import handle_errors, retry_on_error, get_logger as get_error_logger

# Import common API helpers
from src.scripts.common.api_helpers import api_call as api_call_helper, chunked as chunked_helper

# Import email notification module
try:
    import importlib.util
    email_notify_path = Path(__file__).parent / "email_notify.py"
    if email_notify_path.exists():
        spec = importlib.util.spec_from_file_location("email_notify", email_notify_path)
        email_notify = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(email_notify)
        send_email_notification = email_notify.send_email_notification
        is_email_enabled = email_notify.is_email_enabled
        EMAIL_AVAILABLE = True
    else:
        EMAIL_AVAILABLE = False
except Exception:
    EMAIL_AVAILABLE = False


# ============================================================================
# SYNC IMPLEMENTATION (SaaS-grade: config, API, catalog, tracks, descriptions)
# ============================================================================
from src.scripts.automation._sync_impl import (
    DATA_DIR,
    get_sync_data_dir,
    LIKED_SONGS_PLAYLIST_ID,
    SPOTIFY_API_PAGINATION_LIMIT,
    API_RATE_LIMIT_MAX_RETRIES,
    MIN_TRACK_ID_LENGTH,
    KEEP_MONTHLY_MONTHS,
    OWNER_NAME,
    BASE_PREFIX,
    ENABLE_MONTHLY,
    ENABLE_MOST_PLAYED,
    ENABLE_DISCOVERY,
    PREFIX_MONTHLY,
    PREFIX_GENRE_MONTHLY,
    PREFIX_YEARLY,
    PREFIX_GENRE_MASTER,
    PREFIX_MOST_PLAYED,
    PREFIX_DISCOVERY,
    MONTHLY_NAME_TEMPLATE,
    GENRE_NAME_TEMPLATE,
    GENRE_MONTHLY_TEMPLATE,
    DATE_FORMAT,
    SEPARATOR_MONTH,
    SEPARATOR_PREFIX,
    CAPITALIZATION,
    MONTH_NAMES_SHORT,
    MONTH_NAMES_MEDIUM,
    MONTH_NAMES,
    DESCRIPTION_TEMPLATE,
    DESCRIPTION_TOP_GENRES,
    SPOTIFY_MAX_DESCRIPTION_LENGTH,
    SPOTIFY_MAX_GENRE_TAGS,
    SPOTIFY_MAX_GENRE_TAG_LENGTH,
    MOOD_MAX_TAGS,
    DEFAULT_DISCOVERY_TRACK_LIMIT,
    log,
    verbose_log,
    log_step_banner,
    timed_step,
    set_verbose,
    get_log_buffer,
    api_call,
    get_spotify_client,
    _chunked,
    get_existing_playlists,
    get_playlist_tracks,
    get_user_info,
    _invalidate_playlist_cache,
    _load_genre_data,
    _playlist_cache,
    _playlist_tracks_cache,
    _to_uri,
    _uri_to_track_id,
    _get_preview_urls_for_tracks,
    _get_audio_features_for_tracks,
    _parse_genres,
    _get_all_track_genres,
    _get_primary_artist_genres,
    _get_genres_from_track_uris,
    _get_genre_emoji,
    _format_genre_tags,
    _add_genre_tags_to_description,
    _update_playlist_description_with_genres,
    run_mood_inference_on_sync,
    compute_track_genres_incremental,
    sync_full_library,
    sync_export_data,
    rename_playlists_with_old_prefixes,
    fix_incorrectly_named_yearly_genre_playlists,
    get_most_played_tracks,
    get_time_based_tracks,
    get_repeat_tracks,
    get_discovery_tracks,
)
# Wire genre_inference log callback
import src.features.genre_inference as genre_inference_module
genre_inference_module._log_fn = log

# Re-export for backward compatibility
from src.scripts.common.config_helpers import parse_bool_env as _parse_bool_env
_data_dir_env = os.environ.get("SPOTIM8_DATA_DIR") or os.environ.get("DATA_DIR")


# Workflow functions (run_mood_inference_on_sync, compute_track_genres_incremental, sync_full_library,
# sync_export_data, rename_playlists_with_old_prefixes, fix_incorrectly_named_yearly_genre_playlists,
# get_most_played_tracks, get_time_based_tracks, get_repeat_tracks, get_discovery_tracks) are imported
# from _sync_impl above. Removed duplicate definitions for SaaS-grade single source of truth.

def main():
    # Load environment variables from .env file if available
    if DOTENV_AVAILABLE:
        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            load_dotenv(env_path)
    
    # Clear log buffer at start
    get_log_buffer().clear()
    
    parser = argparse.ArgumentParser(
        description="Sync Spotify library and update playlists",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/spotify_sync.py              # Full sync + update
    python scripts/spotify_sync.py --skip-sync  # Update only (fast)
    python scripts/spotify_sync.py --sync-only  # Sync only, no playlist changes
    python scripts/spotify_sync.py --all-months # Process all months
    python scripts/spotify_sync.py --verbose    # Enable detailed logging
    python scripts/spotify_sync.py -v --skip-sync  # Verbose mode + skip sync
        """
    )
    parser.add_argument(
        "--skip-sync", action="store_true",
        help="Skip data sync, use existing parquet files (faster for local runs)"
    )
    parser.add_argument(
        "--sync-only", action="store_true",
        help="Only sync data, don't update playlists"
    )
    parser.add_argument(
        "--all-months", action="store_true",
        help="Process all months (deprecated: now uses last 3 months by default)"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable verbose logging for detailed debugging information"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Force full sync without using cache (re-fetch all data)"
    )
    args = parser.parse_args()
    
    set_verbose(args.verbose)
    if args.verbose:
        verbose_log("Verbose logging enabled - detailed output will be shown")
    
    log("=" * 60)
    log("Spotify Sync & Playlist Update")
    log("=" * 60)
    log(f"Data directory: {DATA_DIR}")
    if _data_dir_env:
        verbose_log(f"  (from SPOTIM8_DATA_DIR / DATA_DIR env)")
    else:
        verbose_log(f"  (default: project/data). Set SPOTIM8_DATA_DIR to use another path.")
    
    success = False
    error = None
    summary = {}
    
        # Authenticate
    try:
        verbose_log("Initializing Spotify client...")
        sp = get_spotify_client()
        verbose_log("Fetching user info...")
        user = get_user_info(sp)
        log(f"Authenticated as: {user['display_name']} ({user['id']})")
        verbose_log(f"User details: email={user.get('email', 'N/A')}, followers={user.get('followers', {}).get('total', 'N/A')}, product={user.get('product', 'N/A')}")
    except Exception as e:
        log(f"ERROR: Authentication failed: {e}")
        verbose_log(f"Authentication error details: {type(e).__name__}: {str(e)}")
        if args.verbose:
            import traceback
            verbose_log(f"Traceback:\n{traceback.format_exc()}")
        error = e
        _send_email_notification(False, error=error)
        sys.exit(1)
    
    try:
        verbose_log(f"Configuration: skip_sync={args.skip_sync}, sync_only={args.sync_only}, all_months={args.all_months}")
        verbose_log(f"Environment: KEEP_MONTHLY_MONTHS={KEEP_MONTHLY_MONTHS}, OWNER_NAME={OWNER_NAME}, BASE_PREFIX={BASE_PREFIX}")
        
        # -------------------------------------------------------------------------
        # PHASE 1: DATA SYNC
        # -------------------------------------------------------------------------
        if not args.skip_sync:
            log("")
            log(">>> PHASE 1: DATA SYNC <<<")
            verbose_log("Starting full library sync (library + playlists + tracks + artists)...")
            with timed_step("Full Library Sync"):
                # Full library sync using spotim8 (includes liked songs and artists)
                sync_success = sync_full_library(force=args.force)
                summary["sync_completed"] = "Yes" if sync_success else "No"
                verbose_log(f"Sync completed: success={sync_success}")
        else:
            verbose_log("Skipping data sync (--skip-sync flag set)")
        
        # -------------------------------------------------------------------------
        # PHASE 2: PLAYLIST UPDATES
        # -------------------------------------------------------------------------
        if not args.sync_only:
            log("")
            log(">>> PHASE 2: PLAYLIST UPDATES <<<")
            verbose_log("Starting playlist update phase (rename, consolidate, monthly, genre, descriptions)...")
            with timed_step("Rename Playlists with Old Prefixes"):
                # Rename playlists with old prefixes (runs first, before other updates)
                rename_playlists_with_old_prefixes(sp)
            
            with timed_step("Fix Incorrectly Named Yearly Genre Playlists"):
                # Fix yearly genre playlists that were created with wrong template
                fix_incorrectly_named_yearly_genre_playlists(sp)
            
            with timed_step("Consolidate Old Monthly Playlists"):
                # Consolidate old monthly playlists into yearly (runs first)
                # Consolidates anything older than the last N months (default: 3)
                consolidate_old_monthly_playlists(sp, keep_last_n_months=KEEP_MONTHLY_MONTHS)
            
            with timed_step("Delete Old Monthly Playlists"):
                # Delete old monthly playlists (including genre-split)
                delete_old_monthly_playlists(sp)
            
            with timed_step("Update Monthly Playlists"):
                # Update monthly playlists (only last N months, default: 3)
                month_to_tracks = update_monthly_playlists(
                    sp, keep_last_n_months=KEEP_MONTHLY_MONTHS
                )
                if month_to_tracks:
                    summary["months_processed"] = len(month_to_tracks)
            
            # Update genre-split playlists
            if month_to_tracks:
                with timed_step("Update Genre-Split Playlists"):
                    update_genre_split_playlists(sp, month_to_tracks)
            
            with timed_step("Update Master Genre Playlists"):
                # Update master genre playlists
                update_master_genre_playlists(sp)
            
            with timed_step("Run mood inference (Music2Emo)"):
                # Precompute mood for liked tracks so description updates use cache
                run_mood_inference_on_sync(sp)
            
            with timed_step("Update All Playlist Descriptions"):
                # Update descriptions (short log line + top genres + mood) for all owned playlists
                # Use same data dir as sync (playlists.parquet location)
                try:
                    import pandas as _pd
                    sync_data_dir = get_sync_data_dir()
                    playlists_path = sync_data_dir / "playlists.parquet"
                    if not playlists_path.exists():
                        log(f"  playlists.parquet not found at {playlists_path}; skipping description updates")
                    else:
                        log(f"  Using playlists from {playlists_path}")
                        playlists_df = _pd.read_parquet(playlists_path)
                        owned = playlists_df[playlists_df.get("is_owned", False) == True]
                        n_owned = len(owned)
                        log(f"  Updating descriptions for {n_owned} owned playlist(s)...")
                        for idx, (_, row) in enumerate(owned.iterrows()):
                            pid = row.get("id")
                            if pid:
                                verbose_log(f"  Description update {idx + 1}/{n_owned}: playlist_id={pid}")
                                _update_playlist_description_with_genres(sp, user["id"], pid, None)
                        log(f"  Description updates complete ({n_owned} playlists processed)")
                except Exception as e:
                    log(f"  Update all descriptions failed (non-fatal): {e}")
                    verbose_log(f"  Exception: {type(e).__name__}: {e}")
            
            # Optional: Run health check if enabled
            if _parse_bool_env("ENABLE_HEALTH_CHECK", False):
                with timed_step("Playlist Health Check"):
                    try:
                        from .playlist_organization import get_playlist_organization_report, print_organization_report
                        import pandas as pd
                        
                        playlists_df = pd.read_parquet(DATA_DIR / "playlists.parquet")
                        playlist_tracks_df = pd.read_parquet(DATA_DIR / "playlist_tracks.parquet")
                        tracks_df = pd.read_parquet(DATA_DIR / "tracks.parquet")
                        
                        owned_playlists = playlists_df[playlists_df.get("is_owned", False) == True].copy()
                        report = get_playlist_organization_report(
                            owned_playlists, playlist_tracks_df, tracks_df
                        )
                        print_organization_report(report)
                    except Exception as e:
                        verbose_log(f"  Health check failed (non-fatal): {e}")
            
            # Optional: Generate insights report if enabled
            if _parse_bool_env("ENABLE_INSIGHTS_REPORT", False):
                with timed_step("Generating Insights Report"):
                    try:
                        from .playlist_intelligence import generate_listening_insights_report
                        import pandas as pd
                        
                        playlists_df = pd.read_parquet(DATA_DIR / "playlists.parquet")
                        playlist_tracks_df = pd.read_parquet(DATA_DIR / "playlist_tracks.parquet")
                        tracks_df = pd.read_parquet(DATA_DIR / "tracks.parquet")
                        
                        streaming_history_df = None
                        streaming_path = DATA_DIR / "streaming_history.parquet"
                        if streaming_path.exists():
                            streaming_history_df = pd.read_parquet(streaming_path)
                        
                        report = generate_listening_insights_report(
                            playlists_df,
                            playlist_tracks_df,
                            tracks_df,
                            streaming_history_df
                        )
                        log("\n" + report)
                    except Exception as e:
                        verbose_log(f"  Insights report failed (non-fatal): {e}")
            
            # Optional: Generate genre discovery report if enabled
            if _parse_bool_env("ENABLE_GENRE_DISCOVERY", False):
                with timed_step("Genre Discovery Analysis"):
                    try:
                        from .genre_enhancement import generate_genre_discovery_report
                        import pandas as pd
                        
                        tracks_df = pd.read_parquet(DATA_DIR / "tracks.parquet")
                        track_artists_df = pd.read_parquet(DATA_DIR / "track_artists.parquet")
                        artists_df = pd.read_parquet(DATA_DIR / "artists.parquet")
                        playlist_tracks_df = pd.read_parquet(DATA_DIR / "playlist_tracks.parquet")
                        playlists_df = pd.read_parquet(DATA_DIR / "playlists.parquet")
                        
                        streaming_history_df = None
                        streaming_path = DATA_DIR / "streaming_history.parquet"
                        if streaming_path.exists():
                            streaming_history_df = pd.read_parquet(streaming_path)
                        
                        report = generate_genre_discovery_report(
                            tracks_df,
                            track_artists_df,
                            artists_df,
                            playlist_tracks_df,
                            playlists_df,
                            streaming_history_df
                        )
                        log("\n" + report)
                    except Exception as e:
                        verbose_log(f"  Genre discovery failed (non-fatal): {e}")
        
        log("\n" + "=" * 60)
        log("✅ Complete!")
        log("=" * 60)
        success = True
        
    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        error_trace = traceback.format_exc()
        log(error_trace)
        error = e
        success = False
    
    finally:
        # Send email notification
        _send_email_notification(success, summary=summary, error=error)
        
        if not success:
            sys.exit(1)


def _send_email_notification(success: bool, summary: dict = None, error: Exception = None):
    """Helper to send email notification with captured logs."""
    if not EMAIL_AVAILABLE:
        log("  ℹ️  Email notifications not available (email_notify.py not found)")
        return
    
    if not is_email_enabled():
        log("  ℹ️  Email notifications disabled (EMAIL_ENABLED not set to true)")
        return
    
    log_output = "\n".join(get_log_buffer())
    
    try:
        log("  📧 Sending email notification...")
        email_sent = send_email_notification(
            success=success,
            log_output=log_output,
            summary=summary or {},
            error=error
        )
        if email_sent:
            log("  ✅ Email notification sent successfully")
        else:
            log("  ⚠️  Email notification failed (check email configuration)")
    except Exception as e:
        # Don't fail the sync if email fails
        log(f"  ⚠️  Email notification error (non-fatal): {e}")
        import traceback
        log(traceback.format_exc())


if __name__ == "__main__":
    main()

