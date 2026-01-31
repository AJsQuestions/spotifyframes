"""
Market (browse/search) DataFrames: new releases, categories, search.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import pandas as pd

if TYPE_CHECKING:
    import spotipy


def _rate_limited(sp: "spotipy.Spotify", delay: float, func, *args, **kwargs):
    """Call API with optional rate limiting."""
    from ..utils.ratelimit import rate_limited_call
    return rate_limited_call(func, *args, delay=delay, **kwargs)


class MarketFrames:
    """Pandas DataFrames for Spotify browse and search APIs."""

    def __init__(
        self,
        sp: "spotipy.Spotify",
        progress: bool = False,
        request_delay: float = 0.1,
    ):
        self._sp = sp
        self._progress = progress
        self._delay = request_delay

    def new_releases(
        self,
        country: str = "US",
        limit: int = 20,
    ) -> pd.DataFrame:
        """Browse new album releases as a DataFrame."""
        r = _rate_limited(
            self._sp,
            self._delay,
            self._sp.new_releases,
            country=country,
            limit=min(limit, 50),
        )
        items = (r.get("albums") or {}).get("items") or []
        rows = []
        for a in items:
            artists = a.get("artists") or []
            artist_names = ", ".join(ar.get("name", "") for ar in artists)
            rows.append({
                "album_id": a.get("id"),
                "name": a.get("name"),
                "release_date": a.get("release_date"),
                "album_type": a.get("album_type"),
                "total_tracks": a.get("total_tracks"),
                "artist_names": artist_names,
                "uri": a.get("uri"),
            })
        return pd.DataFrame(rows)

    def categories(
        self,
        country: str = "US",
        limit: int = 50,
    ) -> pd.DataFrame:
        """Browse categories as a DataFrame."""
        r = _rate_limited(
            self._sp,
            self._delay,
            self._sp.categories,
            country=country,
            limit=min(limit, 50),
        )
        items = (r.get("categories") or {}).get("items") or []
        rows = [{"id": c.get("id"), "name": c.get("name")} for c in items]
        return pd.DataFrame(rows)

    def category_playlists(
        self,
        category_id: str,
        country: str = "US",
        limit: int = 50,
    ) -> pd.DataFrame:
        """Playlists for a category as a DataFrame."""
        r = _rate_limited(
            self._sp,
            self._delay,
            self._sp.category_playlists,
            category_id,
            country=country,
            limit=min(limit, 50),
        )
        items = (r.get("playlists") or {}).get("items") or []
        rows = []
        for p in items:
            rows.append({
                "playlist_id": p.get("id"),
                "name": p.get("name"),
                "description": (p.get("description") or "")[:500],
                "tracks_total": (p.get("tracks") or {}).get("total"),
                "uri": p.get("uri"),
            })
        return pd.DataFrame(rows)

    def search_tracks(
        self,
        q: str,
        market: Optional[str] = "US",
        limit: int = 20,
    ) -> pd.DataFrame:
        """Search tracks; returns tidy DataFrame."""
        r = _rate_limited(
            self._sp,
            self._delay,
            self._sp.search,
            q,
            type="track",
            market=market,
            limit=min(limit, 50),
        )
        items = (r.get("tracks") or {}).get("items") or []
        rows = []
        for t in items:
            artists = t.get("artists") or []
            artist_names = ", ".join(ar.get("name", "") for ar in artists)
            album = t.get("album") or {}
            rows.append({
                "track_id": t.get("id"),
                "name": t.get("name"),
                "artist_names": artist_names,
                "album_name": album.get("name"),
                "release_date": album.get("release_date"),
                "duration_ms": t.get("duration_ms"),
                "popularity": t.get("popularity"),
                "uri": t.get("uri"),
            })
        return pd.DataFrame(rows)

    def search_playlists(
        self,
        q: str,
        limit: int = 20,
    ) -> pd.DataFrame:
        """Search playlists; returns tidy DataFrame."""
        r = _rate_limited(
            self._sp,
            self._delay,
            self._sp.search,
            q,
            type="playlist",
            limit=min(limit, 50),
        )
        items = (r.get("playlists") or {}).get("items") or []
        rows = []
        for p in items:
            rows.append({
                "playlist_id": p.get("id"),
                "name": p.get("name"),
                "description": (p.get("description") or "")[:500],
                "tracks_total": (p.get("tracks") or {}).get("total"),
                "uri": p.get("uri"),
            })
        return pd.DataFrame(rows)
