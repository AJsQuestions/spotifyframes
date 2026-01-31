"""
Sync track utilities: URIs, preview URLs, audio features, genre parsing.

Used by catalog/descriptions and by playlist_update for genre assignment.
"""

import ast
import spotipy

from . import settings
from . import api


def _to_uri(track_id: str) -> str:
    """Convert track ID to Spotify URI."""
    track_id = str(track_id)
    if track_id.startswith("spotify:track:"):
        return track_id
    if len(track_id) >= settings.MIN_TRACK_ID_LENGTH and ":" not in track_id:
        return f"spotify:track:{track_id}"
    return track_id


def _uri_to_track_id(track_uri: str) -> str:
    """Extract track ID from track URI."""
    if track_uri.startswith("spotify:track:"):
        return track_uri.replace("spotify:track:", "")
    return track_uri


def _parse_genres(genre_data) -> list:
    """Parse genre data from various formats (list, str, ndarray, etc.)."""
    if genre_data is None:
        return []
    try:
        import numpy as np
        if isinstance(genre_data, np.ndarray):
            return [str(g).strip() for g in genre_data if g is not None and str(g).strip()]
    except ImportError:
        pass
    if isinstance(genre_data, list):
        return [str(g).strip() for g in genre_data if g is not None and str(g).strip()]
    if isinstance(genre_data, str) and genre_data.strip():
        return [genre_data.strip()]
    try:
        if hasattr(genre_data, "__iter__") and not isinstance(genre_data, str):
            return [str(g).strip() for g in genre_data if g is not None and str(g).strip()]
    except Exception:
        pass
    try:
        return ast.literal_eval(genre_data)
    except (ValueError, SyntaxError):
        return [genre_data] if genre_data else []
    return []


def _get_preview_urls_for_tracks(sp: spotipy.Spotify, track_uris: list) -> dict:
    """
    Fetch preview_url for each track via Spotify API (batches of 50).
    Returns dict mapping track_uri -> preview_url (only entries with non-null preview_url).
    """
    from .api import _chunked

    if not track_uris:
        return {}
    track_ids = [_uri_to_track_id(u) for u in track_uris if u and "spotify:track:" in str(u)]
    track_ids = list(dict.fromkeys(track_ids))
    preview_urls = {}
    chunks = list(_chunked(track_ids, 50))
    for i, chunk in enumerate(chunks):
        try:
            resp = api.api_call(sp.tracks, chunk)
            n_in_chunk = 0
            for t in (resp.get("tracks") or []):
                if not t:
                    continue
                tid = t.get("id")
                url = t.get("preview_url")
                if tid and url:
                    preview_urls[f"spotify:track:{tid}"] = url
                    n_in_chunk += 1
            from . import logger
            logger.verbose_log(
                f"  Preview URLs: batch {i + 1}/{len(chunks)} ({len(chunk)} tracks) -> {n_in_chunk} with previews (total {len(preview_urls)})"
            )
        except Exception as e:
            from . import logger
            logger.verbose_log(f"  Failed to fetch preview URLs for chunk {i + 1}/{len(chunks)}: {e}")
    return preview_urls


def _get_audio_features_for_tracks(sp: spotipy.Spotify, track_uris: list) -> list:
    """
    Fetch Audio Features (valence, energy) for tracks via Spotify API (batches of 100).
    Returns list in same order as track_uris; None for missing/failed.
    """
    from .api import _chunked
    from . import logger

    if not track_uris:
        return []
    track_ids = [_uri_to_track_id(u) for u in track_uris if u and "spotify:track:" in str(u)]
    if not track_ids:
        return []
    out = []
    for chunk in _chunked(track_ids, 100):
        try:
            result = api.api_call(sp.audio_features, chunk)
            if result and isinstance(result, list):
                out.extend(result)
            else:
                out.extend([None] * len(chunk))
        except Exception as e:
            logger.verbose_log(f"  Audio features batch failed (API may be restricted): {e}")
            out.extend([None] * len(chunk))
    return out[: len(track_ids)]


def _get_all_track_genres(track_id: str, track_artists, artist_genres_map: dict) -> list:
    """Get all genres from all artists on a track."""
    track_artist_rows = track_artists[track_artists["track_id"] == track_id]
    all_genres = []
    for _, row in track_artist_rows.iterrows():
        artist_id = row["artist_id"]
        artist_genres = _parse_genres(artist_genres_map.get(artist_id, []))
        all_genres.extend(artist_genres)
    seen = set()
    unique_genres = []
    for genre in all_genres:
        if genre not in seen:
            seen.add(genre)
            unique_genres.append(genre)
    return unique_genres


def _get_primary_artist_genres(track_id: str, track_artists, artist_genres_map: dict) -> list:
    """Get genres from the primary (first) artist only for a track."""
    track_artist_rows = track_artists[track_artists["track_id"] == track_id]
    if track_artist_rows.empty:
        return []
    if "position" in track_artist_rows.columns:
        primary = track_artist_rows[track_artist_rows["position"] == 0]
        if primary.empty:
            primary = track_artist_rows.head(1)
    else:
        primary = track_artist_rows.head(1)
    artist_id = primary["artist_id"].iloc[0]
    return _parse_genres(artist_genres_map.get(artist_id, []))
