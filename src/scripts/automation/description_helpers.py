"""
Playlist Description Helper Functions

Extracted from sync.py to improve code organization.
Handles description formatting, sanitization, genre tag addition, and mood tags (Daylist-style).
"""

import re
from typing import List, Optional
from collections import Counter

from src.scripts.automation.config import (
    SPOTIFY_MAX_DESCRIPTION_LENGTH,
    SPOTIFY_MAX_GENRE_TAGS,
    SPOTIFY_MAX_GENRE_TAG_LENGTH,
    DESCRIPTION_TRUNCATE_MARGIN,
    ENABLE_MOOD_TAGS,
    MOOD_MAX_TAGS,
    DESCRIPTION_TOP_GENRES,
)


def sanitize_description(description: str, max_length: int = SPOTIFY_MAX_DESCRIPTION_LENGTH) -> str:
    """
    Sanitize and truncate playlist description (generic helper).
    For API submission use sanitize_description_for_api().
    """
    if description is None:
        return ""
    description = str(description)
    description = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', description)
    if len(description) > max_length:
        if "\n" in description:
            lines = description.split("\n")
            if len(lines[0]) <= max_length - DESCRIPTION_TRUNCATE_MARGIN:
                remaining = max_length - len(lines[0]) - 5
                if remaining > 0:
                    truncated_rest = "\n".join(lines[1:])[:remaining]
                    description = f"{lines[0]}\n{truncated_rest}..."
                else:
                    description = lines[0][:max_length - 3] + "..."
            else:
                description = description[:max_length - 3] + "..."
        else:
            description = description[:max_length - 3] + "..."
    return description


def _strip_emoji_and_problematic(s: str) -> str:
    """Remove emoji, zero-width chars, and other symbols that can trigger 400 from Spotify."""
    import unicodedata
    out = []
    for c in s:
        cat = unicodedata.category(c)
        # Skip control and format (e.g. zero-width) and private use
        if cat.startswith("C") or cat == "Cf" or cat == "Co":
            continue
        cp = ord(c)
        # Skip variation selectors (can break emoji sequences; remove whole thing)
        if 0xFE00 <= cp <= 0xFE0F:
            continue
        # Skip symbol/other in emoji/symbol blocks (So with high codepoint = emoji)
        if cat == "So" and cp >= 0x1F300:
            continue
        # Skip modifier letters/symbols in emoji range (e.g. skin tone)
        if cat == "Sk" and cp >= 0x1F3FB and cp <= 0x1F3FF:
            continue
        out.append(c)
    return "".join(out)


def sanitize_description_for_api(description: str, max_length: int = SPOTIFY_MAX_DESCRIPTION_LENGTH) -> str:
    """
    Harden playlist description for Spotify API (avoid 400 Bad Request).

    - Normalizes Unicode to NFC
    - Strips control chars, null bytes, emoji, zero-width chars
    - Truncates to max_length (300) with safe boundary
    - Ensures valid UTF-8 (replaces invalid sequences)

    Args:
        description: Raw description text
        max_length: Spotify limit (300)

    Returns:
        Sanitized string safe for user_playlist_change_details(description=...)
    """
    if description is None:
        return ""
    import unicodedata
    s = str(description)
    # Normalize to NFC (canonical form) so Spotify accepts it
    s = unicodedata.normalize("NFC", s)
    # Remove emoji and other symbols that often cause 400
    s = _strip_emoji_and_problematic(s)
    # Remove control characters and null bytes (keep \\n and \\t)
    s = re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]", "", s)
    # Replace \\r so we don't send \\r\\n (some APIs reject \\r)
    s = s.replace("\r", "")
    # Truncate to limit before encoding so we never exceed 300 bytes
    if len(s) > max_length:
        lines = s.split("\n")
        if lines and len(lines[0]) <= max_length - 10:
            rest = "\n".join(lines[1:])
            keep = max_length - len(lines[0]) - 5
            if keep > 0 and len(rest) > keep:
                s = lines[0] + "\n" + rest[:keep] + "..."
            else:
                s = lines[0][: max_length - 3] + "..."
        else:
            s = s[: max_length - 3] + "..."
    if len(s) > max_length:
        s = s[:max_length]
    # Ensure valid UTF-8 (Spotify expects UTF-8)
    s = s.encode("utf-8", errors="replace").decode("utf-8")
    return s


def format_genre_tags(
    specific_genres_counter: Counter,
    broad_genres_counter: Counter,
    max_tags: int = SPOTIFY_MAX_GENRE_TAGS,
    max_length: int = SPOTIFY_MAX_GENRE_TAG_LENGTH
) -> str:
    """
    Format genre tags for playlist description.
    
    Prioritizes broad genres and shows the most common genres from tracks in the playlist.
    
    Args:
        specific_genres_counter: Counter of specific genres (subgenres)
        broad_genres_counter: Counter of broad genres
        max_tags: Maximum number of tags to include
        max_length: Maximum length of tag string
    
    Returns:
        Formatted genre tag string showing most common genres
    """
    from src.scripts.automation.sync import _get_genre_emoji
    
    # Prioritize broad genres (most common first)
    # Get top broad genres sorted by frequency
    top_broad = broad_genres_counter.most_common(max_tags)
    
    # Build tag string from most common broad genres
    tags = []
    for genre, count in top_broad:
        emoji = _get_genre_emoji(genre)
        tags.append(f"{emoji} {genre}")
    
    # If we have space and no broad genres, fallback to specific genres
    top_specific = specific_genres_counter.most_common(max_tags) if not tags else []
    if not tags and top_specific:
        for genre, count in top_specific:
            emoji = _get_genre_emoji(genre)
            tags.append(f"{emoji} {genre}")
    
    tag_str = " • ".join(tags[:max_tags])
    
    # Truncate if too long
    if len(tag_str) > max_length:
        tag_str = tag_str[:max_length - 10] + "..."
    
    return tag_str


def add_genre_tags_to_description(
    current_description: str,
    track_uris: List[str],
    max_tags: int = SPOTIFY_MAX_GENRE_TAGS
) -> str:
    """
    Add genre tags to playlist description.
    
    Args:
        current_description: Current playlist description
        track_uris: List of track URIs in the playlist
        max_tags: Maximum number of genre tags to add
    
    Returns:
        Description with genre tags added
    """
    from src.scripts.automation.sync import _get_genres_from_track_uris
    
    # Get genres from tracks
    specific_genres_counter, broad_genres_counter = _get_genres_from_track_uris(track_uris)
    
    # Format genre tags
    genre_tags = format_genre_tags(specific_genres_counter, broad_genres_counter, max_tags=max_tags)
    
    if not genre_tags:
        return current_description
    
    # Add genre tags section
    if current_description:
        # Check if genres section already exists
        if "Genres:" in current_description or any(emoji in current_description for emoji in ["🎤", "🎧", "💃", "💜", "🎸", "🎶", "🎷"]):
            # Replace existing genre section
            lines = current_description.split("\n")
            new_lines = []
            skip_until_newline = False
            for line in lines:
                if "Genres:" in line or any(emoji in line for emoji in ["🎤", "🎧", "💃", "💜", "🎸", "🎶", "🎷"]):
                    skip_until_newline = True
                    new_lines.append(f"Genres: {genre_tags}")
                elif skip_until_newline and line.strip() == "":
                    skip_until_newline = False
                    new_lines.append(line)
                elif not skip_until_newline:
                    new_lines.append(line)
            result = "\n".join(new_lines)
        else:
            # Append genre tags
            result = f"{current_description}\n\nGenres: {genre_tags}"
    else:
        result = f"Genres: {genre_tags}"

    # Optionally add mood tags (Daylist-style)
    if ENABLE_MOOD_TAGS and track_uris:
        result = add_mood_tags_to_description(result, track_uris, max_tags=MOOD_MAX_TAGS)
    return result


def format_mood_tags(mood_list: List[str], max_tags: int = 5, max_length: int = 120) -> str:
    """
    Format mood labels as a tag string for playlist description (e.g. "Chill • Energetic • Focus").

    Args:
        mood_list: List of mood strings (e.g. from get_mood_tags_for_playlist).
        max_tags: Maximum number of tags to include.
        max_length: Maximum length of tag string.

    Returns:
        Formatted string like "Chill • Energetic • Focus".
    """
    if not mood_list:
        return ""
    tags = mood_list[:max_tags]
    tag_str = " • ".join(tags)
    if len(tag_str) > max_length:
        tag_str = tag_str[:max_length - 10] + "..."
    return tag_str


def add_mood_tags_to_description(
    current_description: str,
    track_uris: List[str],
    max_tags: int = 5,
    preview_urls: Optional[dict] = None,
    mood_cache_dir: Optional[str] = None,
) -> str:
    """
    Add mood tags (Music2Emo song-level only) to playlist description.

    When preview_urls are provided, uses Music2Emo. If not provided, skips mood line.

    Args:
        current_description: Current description text (may already include Genres: ...).
        track_uris: List of track URIs in the playlist.
        max_tags: Maximum number of mood tags to add.
        preview_urls: Dict track_uri -> preview_url (required for mood).
        mood_cache_dir: Optional cache dir for Music2Emo.

    Returns:
        Description with "Moods: ..." added or updated when preview_urls provided.
    """
    if not preview_urls:
        return current_description
    from pathlib import Path
    from src.features.mood_inference import get_mood_tags_for_playlist

    cache_path = Path(mood_cache_dir) if mood_cache_dir else None
    mood_list = get_mood_tags_for_playlist(
        track_uris, preview_urls, max_tags=max_tags, mood_cache_dir=cache_path
    )
    if not mood_list:
        return current_description

    mood_tags = format_mood_tags(mood_list, max_tags=max_tags)
    mood_line = f"Moods: {mood_tags}"

    # Replace or append mood section
    if "Moods:" in current_description:
        lines = current_description.split("\n")
        new_lines = []
        skip_until_newline = False
        for line in lines:
            if "Moods:" in line:
                skip_until_newline = True
                new_lines.append(mood_line)
            elif skip_until_newline and line.strip() == "":
                skip_until_newline = False
                new_lines.append(line)
            elif not skip_until_newline:
                new_lines.append(line)
        return "\n".join(new_lines)
    if current_description:
        return f"{current_description}\n{mood_line}"
    return mood_line


def build_simple_description(
    base_line: str,
    track_uris: List[str],
    max_genre_tags: int = None,
    max_mood_tags: int = None,
    preview_urls: Optional[dict] = None,
    mood_cache_dir: Optional[str] = None,
    audio_features_fallback: Optional[list] = None,
) -> str:
    """
    Build playlist description as: short log line + top genres + mood tags only.

    Used for all playlists (including AJ automated). No rich statistics.
    Mood: Music2Emo when preview_urls provided; else valence/energy fallback when audio_features_fallback provided.

    Args:
        base_line: First line (e.g. "Liked songs from Jan 2025 (automatically updated)" or playlist name).
        track_uris: List of track URIs in the playlist.
        max_genre_tags: Max genre tags (default DESCRIPTION_TOP_GENRES).
        max_mood_tags: Max mood tags (default MOOD_MAX_TAGS).
        preview_urls: Dict track_uri -> preview_url for Music2Emo (required for mood when no fallback).
        mood_cache_dir: Optional path to cache Music2Emo results.
        audio_features_fallback: Optional list of sp.audio_features() dicts (same order as track_uris) for mood when no preview URLs.

    Returns:
        Description string: base_line + "\\n\\nGenres: ..." + "\\nMoods: ..."
    """
    if max_genre_tags is None:
        max_genre_tags = DESCRIPTION_TOP_GENRES
    if max_mood_tags is None:
        max_mood_tags = MOOD_MAX_TAGS

    from pathlib import Path
    from src.scripts.automation.sync import _get_genres_from_track_uris
    from src.features.mood_inference import get_mood_tags_for_playlist

    specific_genres_counter, broad_genres_counter = _get_genres_from_track_uris(track_uris)
    genre_tags = format_genre_tags(
        specific_genres_counter, broad_genres_counter,
        max_tags=max_genre_tags, max_length=SPOTIFY_MAX_GENRE_TAG_LENGTH
    )
    cache_path = Path(mood_cache_dir) if mood_cache_dir else None
    mood_list = []
    if ENABLE_MOOD_TAGS:
        mood_list = get_mood_tags_for_playlist(
            track_uris,
            preview_urls or {},
            max_tags=max_mood_tags,
            mood_cache_dir=cache_path,
            audio_features_fallback=audio_features_fallback,
        )
    mood_tags = format_mood_tags(mood_list, max_tags=max_mood_tags) if mood_list else ""

    parts = [base_line.strip()]
    if genre_tags:
        parts.append(f"Genres: {genre_tags}")
    if mood_tags:
        parts.append(f"Moods: {mood_tags}")
    return "\n".join(parts)
