"""
Market data interface for Spotify browse, search, and recommendations.
"""

from __future__ import annotations

from io import StringIO
from typing import Optional, Dict, List, Callable

import pandas as pd
import requests

from .ratelimit import rate_limited_call, DEFAULT_REQUEST_DELAY


class MarketFrames:
    """Market / population-ish signals built from Spotify browse + search + recommendations + charts ingestion."""

    def __init__(self, sp, progress=None, request_delay: float = DEFAULT_REQUEST_DELAY):
        self.sp = sp
        self.progress = progress
        self._request_delay = request_delay
    
    def _rate_limited(self, func: Callable, *args, **kwargs):
        """Wrapper for rate-limited API calls."""
        return rate_limited_call(func, *args, delay=self._request_delay, **kwargs)

    # ------------------ Browse ------------------
    def new_releases(self, country: str = "US", limit: int = 50) -> pd.DataFrame:
        out = []
        offset = 0
        while True:
            resp = self._rate_limited(self.sp.new_releases, country=country, limit=min(50, limit-offset), offset=offset)
            items = (resp.get("albums") or {}).get("items", [])
            for a in items:
                out.append({
                    "album_id": a.get("id"),
                    "album_name": a.get("name"),
                    "release_date": a.get("release_date"),
                    "album_type": a.get("album_type"),
                    "total_tracks": a.get("total_tracks"),
                    "popularity": a.get("popularity"),
                    "label": a.get("label"),
                    "artists": [x.get("name") for x in a.get("artists", [])],
                    "artist_ids": [x.get("id") for x in a.get("artists", [])],
                    "uri": a.get("uri"),
                })
            offset += len(items)
            if offset >= limit or not items:
                break
        return pd.DataFrame(out)

    def categories(self, country: str = "US", locale: str = "en_US", limit: int = 50) -> pd.DataFrame:
        out = []
        offset = 0
        while True:
            resp = self._rate_limited(self.sp.categories, country=country, locale=locale, limit=min(50, limit-offset), offset=offset)
            items = (resp.get("categories") or {}).get("items", [])
            for c in items:
                out.append({
                    "category_id": c.get("id"),
                    "name": c.get("name"),
                    "href": c.get("href"),
                })
            offset += len(items)
            if offset >= limit or not items:
                break
        return pd.DataFrame(out)

    def category_playlists(self, category_id: str, country: str = "US", limit: int = 50) -> pd.DataFrame:
        out = []
        offset = 0
        while True:
            resp = self._rate_limited(self.sp.category_playlists, category_id, country=country, limit=min(50, limit-offset), offset=offset)
            items = (resp.get("playlists") or {}).get("items", [])
            for p in items:
                owner = p.get("owner") or {}
                out.append({
                    "playlist_id": p.get("id"),
                    "name": p.get("name"),
                    "description": p.get("description"),
                    "snapshot_id": p.get("snapshot_id"),
                    "track_count": (p.get("tracks") or {}).get("total"),
                    "owner_id": owner.get("id"),
                    "owner_name": owner.get("display_name"),
                    "uri": p.get("uri"),
                    "category_id": category_id,
                    "country": country,
                })
            offset += len(items)
            if offset >= limit or not items:
                break
        return pd.DataFrame(out)

    # ------------------ Search ------------------
    def search_tracks(self, q: str, market: str = "US", limit: int = 200) -> pd.DataFrame:
        out = []
        offset = 0
        while True:
            resp = self._rate_limited(self.sp.search, q=q, type="track", market=market, limit=min(50, limit-offset), offset=offset)
            items = (resp.get("tracks") or {}).get("items", [])
            for t in items:
                album = t.get("album") or {}
                out.append({
                    "track_id": t.get("id"),
                    "track_name": t.get("name"),
                    "popularity": t.get("popularity"),
                    "duration_ms": t.get("duration_ms"),
                    "explicit": t.get("explicit"),
                    "album_id": album.get("id"),
                    "album_name": album.get("name"),
                    "release_date": album.get("release_date"),
                    "artist_ids": [a.get("id") for a in t.get("artists", [])],
                    "artists": [a.get("name") for a in t.get("artists", [])],
                    "uri": t.get("uri"),
                    "query": q,
                })
            offset += len(items)
            if offset >= limit or not items:
                break
        return pd.DataFrame(out)

    def search_playlists(self, q: str, limit: int = 200) -> pd.DataFrame:
        out = []
        offset = 0
        while True:
            resp = self._rate_limited(self.sp.search, q=q, type="playlist", limit=min(50, limit-offset), offset=offset)
            items = (resp.get("playlists") or {}).get("items", [])
            for p in items:
                owner = p.get("owner") or {}
                out.append({
                    "playlist_id": p.get("id"),
                    "name": p.get("name"),
                    "description": p.get("description"),
                    "snapshot_id": p.get("snapshot_id"),
                    "track_count": (p.get("tracks") or {}).get("total"),
                    "owner_id": owner.get("id"),
                    "owner_name": owner.get("display_name"),
                    "uri": p.get("uri"),
                    "query": q,
                })
            offset += len(items)
            if offset >= limit or not items:
                break
        return pd.DataFrame(out)

    # ------------------ Recommendations ------------------
    def recommendations(
        self,
        seed_tracks: Optional[List[str]] = None,
        seed_artists: Optional[List[str]] = None,
        seed_genres: Optional[List[str]] = None,
        target: Optional[Dict[str, float]] = None,
        limit: int = 100,
        market: str = "US",
    ) -> pd.DataFrame:
        seed_tracks = (seed_tracks or [])[:5]
        seed_artists = (seed_artists or [])[:5]
        seed_genres = (seed_genres or [])[:5]
        target = target or {}

        resp = self._rate_limited(
            self.sp.recommendations,
            seed_tracks=seed_tracks or None,
            seed_artists=seed_artists or None,
            seed_genres=seed_genres or None,
            limit=min(100, limit),
            market=market,
            **{f"target_{k}": v for k, v in target.items()},
        )
        rows = []
        for t in resp.get("tracks", []):
            album = t.get("album") or {}
            rows.append({
                "track_id": t.get("id"),
                "track_name": t.get("name"),
                "popularity": t.get("popularity"),
                "duration_ms": t.get("duration_ms"),
                "explicit": t.get("explicit"),
                "album_id": album.get("id"),
                "album_name": album.get("name"),
                "release_date": album.get("release_date"),
                "artist_ids": [a.get("id") for a in t.get("artists", [])],
                "artists": [a.get("name") for a in t.get("artists", [])],
                "uri": t.get("uri"),
                "seed_tracks": seed_tracks,
                "seed_artists": seed_artists,
                "seed_genres": seed_genres,
                "target": target,
                "market": market,
            })
        return pd.DataFrame(rows)

    # ------------------ Charts ingestion ------------------
    def charts_top200_from_csv(self, path: str) -> pd.DataFrame:
        """Ingest a chart CSV into a standard schema.

        Expected columns vary by source; we attempt to infer:
        - position/rank
        - track name
        - artist
        - streams
        - url/uri
        - date/region if present
        """
        df = pd.read_csv(path)
        cols = {c.lower().strip(): c for c in df.columns}
        # Common column patterns
        rank_col = cols.get("position") or cols.get("rank")
        track_col = cols.get("track name") or cols.get("track") or cols.get("title")
        artist_col = cols.get("artist") or cols.get("artist name")
        streams_col = cols.get("streams")
        url_col = cols.get("url") or cols.get("spotify url") or cols.get("uri")

        out = pd.DataFrame({
            "rank": df[rank_col] if rank_col else None,
            "track_name": df[track_col] if track_col else None,
            "artist_name": df[artist_col] if artist_col else None,
            "streams": df[streams_col] if streams_col else None,
            "url_or_uri": df[url_col] if url_col else None,
        })
        # Keep other metadata if exists
        for extra in ["date", "region", "chart", "trend", "peak rank", "weeks on chart"]:
            if extra in cols:
                out[extra.replace(" ", "_")] = df[cols[extra]]
        return out

    def charts_top200_best_effort_fetch(self, url: str, timeout: int = 20) -> pd.DataFrame:
        """Best-effort fetch for charts CSV/TSV from a URL. Use responsibly.

        If you have a local CSV, prefer charts_top200_from_csv.
        """
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        # Try CSV first, fallback to TSV
        content = r.text
        sep = "," if content.count(",") >= content.count("\t") else "\t"
        df = pd.read_csv(StringIO(content), sep=sep)
        # Save normalized
        return self.charts_top200_from_dataframe(df)

    def charts_top200_from_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        # helper for fetched charts
        tmp_path = None
        # reuse inference by writing to csv in memory
        cols = {c.lower().strip(): c for c in df.columns}
        rank_col = cols.get("position") or cols.get("rank")
        track_col = cols.get("track name") or cols.get("track") or cols.get("title")
        artist_col = cols.get("artist") or cols.get("artist name")
        streams_col = cols.get("streams")
        url_col = cols.get("url") or cols.get("spotify url") or cols.get("uri")
        out = pd.DataFrame({
            "rank": df[rank_col] if rank_col else None,
            "track_name": df[track_col] if track_col else None,
            "artist_name": df[artist_col] if artist_col else None,
            "streams": df[streams_col] if streams_col else None,
            "url_or_uri": df[url_col] if url_col else None,
        })
        for extra in ["date", "region", "chart", "trend", "peak rank", "weeks on chart"]:
            if extra in cols:
                out[extra.replace(" ", "_")] = df[cols[extra]]
        return out
