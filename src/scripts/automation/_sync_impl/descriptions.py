"""
Sync playlist descriptions: genre tags, mood, and API update.

Uses description_helpers for build_simple_description and sanitization.
"""

from collections import Counter
import spotipy

from . import settings
from . import logger
from . import api
from . import catalog
from . import tracks


def _get_genre_emoji(genre: str) -> str:
    """Get emoji for a genre."""
    genre_lower = genre.lower()
    emoji_map = {
        "hip-hop": "🎤", "electronic": "🎧", "dance": "💃",
        "r&b/soul": "💜", "r&b": "💜", "soul": "💜",
        "rock": "🎸", "pop": "🎶", "jazz": "🎷",
        "country/folk": "🌾", "country": "🌾", "folk": "🌾",
        "classical": "🎻", "metal": "⚡", "blues": "🎹",
        "latin": "🎊", "world": "🌍", "indie": "🎨", "alternative": "🎵",
        "hiphop": "🎤", "trap": "🎧", "house": "🏠", "techno": "⚡",
        "dubstep": "🔊", "rap": "🎤", "funk": "🎺", "disco": "🪩",
        "reggae": "☀️", "punk": "🤘", "gospel": "✨",
    }
    if genre_lower in emoji_map:
        return emoji_map[genre_lower]
    for key, emoji in emoji_map.items():
        if key in genre_lower or genre_lower in key:
            return emoji
    return "🎵"


def _get_genres_from_track_uris(track_uris: list) -> tuple:
    """Get genres from a list of track URIs using cached data. Returns (specific_genres_counter, broad_genres_counter)."""
    from src.features.genres import get_all_broad_genres

    track_artists, artists = catalog._load_genre_data()
    if track_artists is None or artists is None:
        return Counter(), Counter()

    track_ids = [tracks._uri_to_track_id(uri) for uri in track_uris]
    track_artists_subset = track_artists[track_artists["track_id"].isin(track_ids)]
    if len(track_artists_subset) == 0:
        return Counter(), Counter()

    track_to_artists = {}
    for _, row in track_artists_subset.iterrows():
        track_id = row["track_id"]
        artist_id = row["artist_id"]
        if track_id not in track_to_artists:
            track_to_artists[track_id] = []
        track_to_artists[track_id].append(artist_id)

    all_artist_ids = track_artists_subset["artist_id"].unique()
    artists_subset = artists[artists["artist_id"].isin(all_artist_ids)]
    artist_genres_map = {}
    for _, row in artists_subset.iterrows():
        artist_id = row["artist_id"]
        genres_list = row["genres"]
        try:
            if genres_list is None:
                artist_genres_map[artist_id] = []
            elif isinstance(genres_list, (list, tuple)):
                artist_genres_map[artist_id] = list(genres_list) if genres_list else []
            elif hasattr(genres_list, "__iter__") and not isinstance(genres_list, str):
                artist_genres_map[artist_id] = list(genres_list) if list(genres_list) else []
            else:
                artist_genres_map[artist_id] = []
        except (TypeError, ValueError, AttributeError):
            artist_genres_map[artist_id] = []

    specific_genres_counter = Counter()
    broad_genres_counter = Counter()
    for track_id, artist_ids in track_to_artists.items():
        track_genres = set()
        for artist_id in artist_ids:
            track_genres.update(artist_genres_map.get(artist_id, []))
        specific_genres_counter.update(track_genres)
        broad_genres = get_all_broad_genres(list(track_genres))
        broad_genres_counter.update(broad_genres)
    return specific_genres_counter, broad_genres_counter


def _format_genre_tags(
    specific_genres_counter,
    broad_genres_counter,
    max_tags: int = None,
    max_length: int = None,
) -> str:
    """Format genre counters as a tag string for playlist description."""
    if max_tags is None:
        max_tags = settings.SPOTIFY_MAX_GENRE_TAGS
    if max_length is None:
        max_length = settings.SPOTIFY_MAX_GENRE_TAG_LENGTH
    if not specific_genres_counter and not broad_genres_counter:
        return ""
    combined_items = []
    all_genre_names = set(broad_genres_counter.keys()) | set(specific_genres_counter.keys())
    for genre in all_genre_names:
        total_count = max(broad_genres_counter.get(genre, 0), specific_genres_counter.get(genre, 0))
        combined_items.append((genre, total_count))
    combined_items.sort(key=lambda x: (-x[1], x[0]))
    unique_genres = [g for g, _ in combined_items]
    total_genres = len(unique_genres)
    if total_genres > max_tags:
        unique_genres = unique_genres[:max_tags]
        remaining = total_genres - max_tags
        genre_tags = [f"{_get_genre_emoji(g)} {g}" for g in unique_genres]
        tag_str = ", ".join(genre_tags) + f" (+{remaining} more)"
    else:
        genre_tags = [f"{_get_genre_emoji(g)} {g}" for g in unique_genres]
        tag_str = ", ".join(genre_tags)
    if len(tag_str) > max_length:
        tag_str = tag_str[: max_length - 10] + "..."
    return tag_str


def _add_genre_tags_to_description(
    current_description: str, track_uris: list, max_tags: int = None
) -> str:
    """Add genre tags to description via description_helpers."""
    from src.scripts.automation.description_helpers import add_genre_tags_to_description
    if max_tags is None:
        max_tags = settings.SPOTIFY_MAX_GENRE_TAGS
    return add_genre_tags_to_description(current_description, track_uris, max_tags=max_tags)


def _update_playlist_description_with_genres(
    sp: spotipy.Spotify, user_id: str, playlist_id: str, track_uris: list = None
) -> bool:
    """Update playlist description with short log line + top genres + mood tags."""
    from src.scripts.automation.description_helpers import (
        build_simple_description,
        sanitize_description_for_api,
    )

    try:
        pl = api.api_call(sp.playlist, playlist_id, fields="description,name")
        current_description = pl.get("description", "") or ""
        playlist_name = pl.get("name", "Unknown")

        if track_uris is None:
            track_uris = list(catalog.get_playlist_tracks(sp, playlist_id, force_refresh=False))
        if not track_uris:
            return False

        preview_urls = tracks._get_preview_urls_for_tracks(sp, track_uris)
        mood_cache_dir = settings.get_sync_data_dir() / ".mood_cache"
        logger.verbose_log(
            f"  Description '{playlist_name}': {len(track_uris)} tracks, {len(preview_urls)} with preview URLs for mood"
        )

        audio_features_fallback = None
        if len(preview_urls) < len(track_uris):
            audio_features_fallback = tracks._get_audio_features_for_tracks(sp, track_uris)
            n_with = sum(1 for f in (audio_features_fallback or []) if f and f.get("valence") is not None)
            if n_with:
                logger.verbose_log(f"  Audio features fallback: {n_with} tracks with valence/energy")

        lines = (current_description or "").strip().split("\n")
        base_line = (lines[0].strip() if lines and lines[0].strip() else "") or playlist_name

        new_description = build_simple_description(
            base_line,
            track_uris,
            max_genre_tags=settings.DESCRIPTION_TOP_GENRES,
            max_mood_tags=settings.MOOD_MAX_TAGS,
            preview_urls=preview_urls,
            mood_cache_dir=str(mood_cache_dir),
            audio_features_fallback=audio_features_fallback,
        )

        new_description = sanitize_description_for_api(
            new_description or "",
            max_length=settings.SPOTIFY_MAX_DESCRIPTION_LENGTH,
        )
        if len(new_description) > settings.SPOTIFY_MAX_DESCRIPTION_LENGTH:
            logger.verbose_log(
                f"  Warning: Description for '{playlist_name}' still {len(new_description)} chars after sanitize, hard truncating"
            )
            new_description = new_description[: settings.SPOTIFY_MAX_DESCRIPTION_LENGTH]

        if not new_description.strip():
            logger.verbose_log(f"  Skipping description update for '{playlist_name}' (description would be empty)")
            return False

        if new_description != current_description:
            try:
                new_description.encode("utf-8")
                api.api_call(
                    sp.user_playlist_change_details,
                    user_id,
                    playlist_id,
                    description=new_description,
                )
                logger.verbose_log(f"  ✅ Updated description for playlist '{playlist_name}' ({len(new_description)} chars)")
                return True
            except UnicodeEncodeError as e:
                logger.verbose_log(f"  ⚠️  Invalid encoding in description for '{playlist_name}': {e}")
                new_description = new_description.encode("utf-8", errors="replace").decode("utf-8")
                try:
                    api.api_call(
                        sp.user_playlist_change_details,
                        user_id,
                        playlist_id,
                        description=new_description[: settings.SPOTIFY_MAX_DESCRIPTION_LENGTH],
                    )
                    logger.verbose_log(f"  ✅ Updated description for playlist '{playlist_name}' after encoding fix")
                    return True
                except Exception as e2:
                    logger.verbose_log(f"  ❌ Failed to update description after encoding fix: {e2}")
                    return False
            except Exception as api_error:
                logger.verbose_log(f"  ❌ Failed to update description via API: {api_error}")
                logger.verbose_log(f"  Description length: {len(new_description)}, preview: {new_description[:100]}...")
                logger.verbose_log(f"  Description repr (first 200): {repr(new_description[:200])}")
                return False
        return False
    except Exception as e:
        logger.verbose_log(f"  Failed to update description: {e}")
        return False
