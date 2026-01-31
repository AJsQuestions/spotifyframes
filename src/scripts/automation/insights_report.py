#!/usr/bin/env python3
"""
Generate Creative Insights Report

Creates a comprehensive, visually appealing report of your listening habits,
playlist organization, and recommendations.
"""

import argparse
import sys
from pathlib import Path

# Add project root to path (SPOTIM8 directory: automation -> scripts -> src -> project root)
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
import os

# Load environment
env_path = PROJECT_ROOT / ".env"
if env_path.exists():
    load_dotenv(env_path)

import pandas as pd
from src.scripts.automation.config import DATA_DIR
from src.scripts.automation.playlist_intelligence import (
    generate_listening_insights_report,
    find_similar_playlists,
    suggest_playlist_merge_candidates,
    calculate_playlist_health_score
)


def main():
    parser = argparse.ArgumentParser(
        description="Generate creative insights report for your Spotify library"
    )
    parser.add_argument(
        "--output",
        help="Output file path (default: print to stdout)"
    )
    parser.add_argument(
        "--similarity",
        type=float,
        default=0.3,
        help="Similarity threshold for finding similar playlists (0.0-1.0)"
    )
    parser.add_argument(
        "--health",
        action="store_true",
        help="Include playlist health scores"
    )
    
    args = parser.parse_args()
    
    # Load data
    playlists_path = DATA_DIR / "playlists.parquet"
    playlist_tracks_path = DATA_DIR / "playlist_tracks.parquet"
    tracks_path = DATA_DIR / "tracks.parquet"
    streaming_history_path = DATA_DIR / "streaming_history.parquet"
    
    if not all(p.exists() for p in [playlists_path, playlist_tracks_path, tracks_path]):
        print("❌ Data files not found. Run sync first!")
        return 1
    
    playlists_df = pd.read_parquet(playlists_path)
    playlist_tracks_df = pd.read_parquet(playlist_tracks_path)
    tracks_df = pd.read_parquet(tracks_path)
    
    streaming_history_df = None
    if streaming_history_path.exists():
        streaming_history_df = pd.read_parquet(streaming_history_path)
    
    # Generate report
    report = generate_listening_insights_report(
        playlists_df,
        playlist_tracks_df,
        tracks_df,
        streaming_history_df
    )
    
    # Add health scores if requested
    if args.health:
        report += "\n\n"
        report += "🏥 PLAYLIST HEALTH SCORES\n"
        report += "-" * 70 + "\n"
        
        owned_playlists = playlists_df[playlists_df.get("is_owned", False) == True]
        
        health_scores = []
        for _, playlist in owned_playlists.head(20).iterrows():  # Top 20
            score_data = calculate_playlist_health_score(
                playlist["playlist_id"],
                playlist_tracks_df,
                tracks_df
            )
            health_scores.append({
                "name": playlist["name"],
                "score": score_data["score"],
                "tracks": score_data["track_count"]
            })
        
        health_scores.sort(key=lambda x: x["score"], reverse=True)
        
        for item in health_scores:
            score_bar = "█" * (item["score"] // 5)
            report += f"   {item['name'][:40]:40s} {score_bar} {item['score']:3d}/100 ({item['tracks']} tracks)\n"
    
    # Output
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(report, encoding='utf-8')
        print(f"✅ Report saved to: {output_path}")
    else:
        print(report)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
