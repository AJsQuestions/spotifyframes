"""
Mood inference for tracks and playlists.

Primary: Music2Emo on Spotify preview URLs (when available).
Fallback: Spotify Audio Features (valence, energy) when preview URLs are missing.
Note: Spotify restricted Audio Features and preview URLs for new apps (Nov 2024);
existing apps may still have access.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import List, Optional, Callable, Any

# Optional progress callback for sync: (processed_count, total_with_preview, from_cache_count) -> None
MoodProgressCallback = Optional[Callable[[int, int, int], None]]


def _mood_from_audio_features(features: dict) -> Optional[str]:
    """Map Spotify audio features (valence, energy) to a single mood label.
    Used when preview URLs are not available. Returns None if features invalid.
    """
    if not features or not isinstance(features, dict):
        return None
    v = features.get("valence")
    e = features.get("energy")
    if v is None or e is None:
        return None
    try:
        v, e = float(v), float(e)
    except (TypeError, ValueError):
        return None
    # Simple quadrant mapping (valence = happiness, energy = intensity)
    if e >= 0.6 and v >= 0.5:
        return "Energetic"
    if e >= 0.6 and v < 0.5:
        return "Intense"
    if e < 0.4 and v >= 0.5:
        return "Chill"
    if e < 0.4 and v < 0.5:
        return "Melancholic"
    if v >= 0.6:
        return "Happy"
    if e >= 0.5:
        return "Upbeat"
    return "Mellow"


def get_mood_counts_from_audio_features(
    track_ids: List[str],
    audio_features_list: List[Optional[dict]],
) -> Counter:
    """
    Build mood counts from Spotify Audio Features (valence/energy).
    Use when preview URLs are not available. Spotify may have restricted this API (Nov 2024).

    Args:
        track_ids: List of track IDs (same order as audio_features_list).
        audio_features_list: List of feature dicts from sp.audio_features(); None entries skipped.

    Returns:
        Counter of mood labels.
    """
    counts: Counter = Counter()
    for feat in audio_features_list:
        mood = _mood_from_audio_features(feat)
        if mood:
            counts[mood] += 1
    return counts


def get_mood_tags_for_playlist(
    track_uris: List[str],
    preview_urls: dict,
    max_tags: int = 5,
    min_count: int = 1,
    mood_cache_dir: Optional[Path] = None,
    audio_features_fallback: Optional[List[Optional[dict]]] = None,
) -> List[str]:
    """
    Get ordered list of mood tags for a playlist.

    Uses Music2Emo when preview_urls are available. If preview_urls are missing or
    Music2Emo returns nothing, uses audio_features_fallback (valence/energy -> mood)
    when provided. Otherwise returns an empty list.

    Args:
        track_uris: List of track URIs in the playlist.
        preview_urls: Dict track_uri -> preview_url (from Spotify API).
        max_tags: Maximum number of mood tags to return.
        min_count: Minimum count for a mood to be included.
        mood_cache_dir: Optional cache dir for Music2Emo results.
        audio_features_fallback: Optional list of feature dicts from sp.audio_features(track_ids)
            in same order as track_uris; used when preview URLs unavailable.

    Returns:
        List of mood strings, most common first (e.g. ["Chill", "Energetic", "Focus"]).
    """
    # 1) Try Music2Emo when we have preview URLs
    if preview_urls:
        counts = get_mood_counts_from_audio(track_uris, preview_urls, cache_dir=mood_cache_dir)
        if counts:
            ordered = [m for m, c in counts.most_common(max_tags * 2) if c >= min_count and m]
            if ordered:
                return ordered[:max_tags]
    # 2) Fallback: valence/energy from Audio Features (if provided and Spotify still returns them)
    if audio_features_fallback is not None and len(audio_features_fallback) > 0:
        counts = get_mood_counts_from_audio_features(
            [u.replace("spotify:track:", "").strip() for u in track_uris if u and "spotify:track:" in str(u)],
            audio_features_fallback,
        )
        if counts:
            ordered = [m for m, c in counts.most_common(max_tags * 2) if c >= min_count and m]
            if ordered:
                return ordered[:max_tags]
    return []


def get_mood_counts_from_audio(
    track_uris: List[str],
    preview_urls: dict,
    cache_dir: Optional[Path] = None,
    progress_callback: MoodProgressCallback = None,
) -> Optional[Counter]:
    """
    Infer moods from audio using Music2Emo (song-level only).

    Uses Spotify preview URLs only: downloads each preview to a temporary file,
    runs Music2Emo on it, then deletes the temp file. No local audio library
    or files are required. Results are cached by track_id.

    Args:
        track_uris: List of spotify:track: URIs.
        preview_urls: Dict mapping track_uri -> preview_url (from Spotify API).
        cache_dir: Optional path to cache mood results (JSON per track).
        progress_callback: Optional (processed, total_with_preview, from_cache) for logging.

    Returns:
        Counter of mood labels, or None if Music2Emo is not available.
    """
    try:
        from music2emo import Music2emo
    except ImportError:
        return None

    import json
    import os
    import tempfile
    import urllib.request

    cache_dir = Path(cache_dir) if cache_dir else None
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)

    def _cached_moods(track_id: str) -> Optional[List[str]]:
        if not cache_dir:
            return None
        cache_file = cache_dir / f"{track_id}.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("predicted_moods")
            except Exception:
                return None
        return None

    def _save_cached_moods(track_id: str, predicted_moods: List[str]) -> None:
        if not cache_dir:
            return
        cache_file = cache_dir / f"{track_id}.json"
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump({"predicted_moods": predicted_moods}, f)
        except Exception:
            pass

    def _download_and_predict(url: str, model) -> Optional[List[str]]:
        """Download Spotify preview URL to a temp file and run Music2Emo. No local audio needed."""
        fd, path = tempfile.mkstemp(suffix=".mp3")
        try:
            os.close(fd)
            urllib.request.urlretrieve(url, path)
            out = model.predict(path)
            return out.get("predicted_moods") if isinstance(out, dict) else None
        except Exception:
            return None
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    model = Music2emo()
    total = Counter()
    total_with_preview = sum(1 for u in track_uris if u and "spotify:track:" in str(u) and preview_urls.get(u))
    processed = 0
    from_cache = 0
    for uri in track_uris:
        if not uri or "spotify:track:" not in str(uri):
            continue
        track_id = uri.replace("spotify:track:", "").strip()
        url = preview_urls.get(uri) if isinstance(preview_urls.get(uri), str) else None
        if not url:
            continue
        processed += 1
        cached = _cached_moods(track_id)
        if cached is not None:
            from_cache += 1
            for m in cached:
                total[m] += 1
            if progress_callback and processed % 100 == 0:
                progress_callback(processed, total_with_preview, from_cache)
            continue
        moods = _download_and_predict(url, model)
        if isinstance(moods, list):
            _save_cached_moods(track_id, moods)
            for m in moods:
                if m:
                    total[m] += 1
        if progress_callback and processed % 100 == 0:
            progress_callback(processed, total_with_preview, from_cache)
    return total if total else None
