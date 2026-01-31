"""
Playlist rename helpers: old-prefix migration and yearly genre name fixes.

Handles migration from old prefix names to new configuration and fixes
incorrectly named yearly genre playlists.
"""

import spotipy

from .logger import log
from .settings import PREFIX_MONTHLY, PREFIX_MOST_PLAYED, PREFIX_DISCOVERY
from .catalog import (
    get_existing_playlists,
    get_user_info,
    _invalidate_playlist_cache,
)
from .api import api_call


def rename_playlists_with_old_prefixes(sp: spotipy.Spotify) -> None:
    """Rename playlists that use old prefixes to match new prefix configuration.

    Handles migration from old prefix names (e.g., "Auto", "AJAuto") to new
    prefix-based naming (e.g., "Finds", "AJFnds").
    """
    log("\n--- Renaming Playlists with Old Prefixes ---")

    existing = get_existing_playlists(sp, force_refresh=True)
    user = get_user_info(sp)
    user_id = user["id"]

    old_to_new = {}

    if PREFIX_MONTHLY != "Auto" and PREFIX_MONTHLY != "auto":
        old_to_new["Auto"] = PREFIX_MONTHLY
        old_to_new["auto"] = PREFIX_MONTHLY.lower()
        old_to_new["AUTO"] = PREFIX_MONTHLY.upper()

    if PREFIX_MOST_PLAYED != "Top":
        old_to_new["Top"] = PREFIX_MOST_PLAYED

    if PREFIX_DISCOVERY not in ["Discover", "Discovery", "Dscvr"]:
        old_to_new["Discover"] = PREFIX_DISCOVERY
        old_to_new["Discovery"] = PREFIX_DISCOVERY

    if not old_to_new:
        log("  ℹ️  No prefix changes detected - skipping rename")
        return

    renamed_count = 0

    for old_name, playlist_id in list(existing.items()):
        new_name = None

        for old_prefix, new_prefix in old_to_new.items():
            if old_prefix in old_name:
                prefix_start = old_name.find(old_prefix)
                if prefix_start == -1:
                    continue
                prefix_end = prefix_start + len(old_prefix)
                before_prefix = old_name[:prefix_start]
                suffix = old_name[prefix_end:]

                if old_prefix.isupper():
                    new_prefix_used = new_prefix.upper()
                elif old_prefix.islower():
                    new_prefix_used = new_prefix.lower()
                elif old_prefix[0].isupper():
                    new_prefix_used = (
                        new_prefix.title() if len(new_prefix) > 1 else new_prefix.upper()
                    )
                else:
                    new_prefix_used = new_prefix

                new_name = f"{before_prefix}{new_prefix_used}{suffix}"

                if new_name != old_name and new_name not in existing:
                    try:
                        api_call(
                            sp.user_playlist_change_details,
                            user_id,
                            playlist_id,
                            name=new_name,
                        )
                        log(f"  ✅ Renamed: '{old_name}' -> '{new_name}'")
                        renamed_count += 1
                        _invalidate_playlist_cache()
                        existing[new_name] = playlist_id
                        del existing[old_name]
                    except Exception as e:
                        log(f"  ⚠️  Failed to rename '{old_name}': {e}")
                elif new_name in existing:
                    log(
                        f"  ⚠️  Skipped '{old_name}' -> '{new_name}' (target name already exists)"
                    )
                break

    if renamed_count > 0:
        log(f"  ✅ Renamed {renamed_count} playlist(s)")
    else:
        log("  ℹ️  No playlists needed renaming")


def fix_incorrectly_named_yearly_genre_playlists(sp: spotipy.Spotify) -> None:
    """Fix yearly genre playlists that were incorrectly named using GENRE_MONTHLY_TEMPLATE.

    This fixes playlists that were created with the monthly template (which includes {mon})
    but should have been created with the yearly template.
    """
    log("\n--- Fixing Incorrectly Named Yearly Genre Playlists ---")

    existing = get_existing_playlists(sp, force_refresh=True)
    user = get_user_info(sp)
    user_id = user["id"]

    renamed_count = 0
    template_placeholders = ["{mon}", "{year}", "{prefix}", "{genre}", "{owner}"]

    for name, playlist_id in list(existing.items()):
        if any(ph in name for ph in template_placeholders):
            # Placeholder: would need genre/year extraction and format_yearly_playlist_name
            # to compute correct new name; skip for now to avoid incorrect renames
            log(f"  ⚠️  Skipping playlist with placeholder in name: {name}")
    if renamed_count > 0:
        log(f"  ✅ Fixed {renamed_count} playlist(s)")
