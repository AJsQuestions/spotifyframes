"""
Spotim8 CLI - Command line interface for Spotify data operations.
"""

from __future__ import annotations

import argparse

from .client import Spotim8
from .export import export_table


AVAILABLE_TABLES = [
    "playlists",
    "playlist_tracks", 
    "tracks",
    "track_artists",
    "artists",
    "library_wide",
]


def main():
    ap = argparse.ArgumentParser(
        prog="spotim8",
        description="Spotify -> pandas tables. Export your library as DataFrames.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    # Refresh command
    ap_refresh = sub.add_parser("refresh", help="Incrementally refresh cached tables.")
    ap_refresh.add_argument("--force", action="store_true", help="Force full refresh.")
    ap_refresh.add_argument("--owned-only", action="store_true", default=True,
                           help="Only sync playlists you own (default: True)")

    # Export command
    ap_export = sub.add_parser("export", help="Export a table to disk.")
    ap_export.add_argument("--table", required=True, choices=AVAILABLE_TABLES,
                           help="Which table to export.")
    ap_export.add_argument("--out", required=True, help="Output path (.parquet or .csv)")
    ap_export.add_argument("--force", action="store_true")

    # Status command
    ap_status = sub.add_parser("status", help="Show status of cached data.")

    # Market command
    ap_market = sub.add_parser("market", help="Market tables (browse/search).")
    ap_market.add_argument("--kind", required=True, 
                           choices=["new_releases", "categories", "category_playlists", 
                                   "search_tracks", "search_playlists"])
    ap_market.add_argument("--q", default="", help="Search query (for search_* kinds)")
    ap_market.add_argument("--category_id", default="", help="Category ID (for category_playlists)")
    ap_market.add_argument("--country", default="US", help="Country code (default: US)")
    ap_market.add_argument("--limit", type=int, default=100, help="Max results (default: 100)")
    ap_market.add_argument("--out", required=True, help="Output path (.parquet or .csv)")

    args = ap.parse_args()

    # Initialize client
    sf = Spotim8.from_env(progress=True)

    if args.cmd == "refresh":
        sf.sync(force=args.force, owned_only=args.owned_only)
        print("✅ Refresh complete")
        return

    if args.cmd == "status":
        sf.print_status()
        return

    if args.cmd == "export":
        if args.table == "library_wide":
            df = sf.library_wide(force=args.force)
        else:
            df = getattr(sf, args.table)(force=args.force)
        path = export_table(df, args.out)
        print(f"✅ Exported {len(df):,} rows to {path}")
        return

    if args.cmd == "market":
        m = sf.market
        if args.kind == "new_releases":
            df = m.new_releases(country=args.country, limit=args.limit)
        elif args.kind == "categories":
            df = m.categories(country=args.country, limit=min(args.limit, 50))
        elif args.kind == "category_playlists":
            if not args.category_id:
                raise SystemExit("Error: --category_id required for category_playlists")
            df = m.category_playlists(args.category_id, country=args.country, limit=min(args.limit, 50))
        elif args.kind == "search_tracks":
            if not args.q:
                raise SystemExit("Error: --q required for search_tracks")
            df = m.search_tracks(args.q, market=args.country, limit=args.limit)
        elif args.kind == "search_playlists":
            if not args.q:
                raise SystemExit("Error: --q required for search_playlists")
            df = m.search_playlists(args.q, limit=args.limit)
        else:
            raise SystemExit(f"Unknown kind: {args.kind}")
        
        path = export_table(df, args.out)
        print(f"✅ Exported {len(df):,} rows to {path}")


if __name__ == "__main__":
    main()
