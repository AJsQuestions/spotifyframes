#!/usr/bin/env python3
"""
Creative Features CLI

Interactive command-line interface for creative playlist features.
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

import spotipy
from src.scripts.common.api_helpers import get_spotify_client, get_user_info
from src.scripts.automation.creative_features import (
    generate_theme_playlist,
    create_time_capsule_playlist,
    create_on_this_day_playlist,
    smart_mix_playlists
)


def main():
    parser = argparse.ArgumentParser(
        description="Creative playlist features and tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate a workout playlist
  python src/scripts/automation/creative_cli.py theme workout

  # Create a time capsule from 2020
  python src/scripts/automation/creative_cli.py time-capsule 2020

  # Create "on this day" playlist (1 year ago)
  python src/scripts/automation/creative_cli.py on-this-day

  # Smart mix of playlists
  python src/scripts/automation/creative_cli.py mix "Playlist1" "Playlist2" --name "Mixed Playlist"
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Theme playlist
    theme_parser = subparsers.add_parser("theme", help="Generate theme-based playlist")
    theme_parser.add_argument("theme", choices=["workout", "study", "chill", "party", "roadtrip"],
                             help="Theme for the playlist")
    theme_parser.add_argument("--tracks", type=int, default=50, help="Number of tracks (default: 50)")
    
    # Time capsule
    capsule_parser = subparsers.add_parser("time-capsule", help="Create time capsule playlist")
    capsule_parser.add_argument("year", type=int, help="Year for the time capsule")
    capsule_parser.add_argument("--tracks", type=int, default=50, help="Number of tracks (default: 50)")
    
    # On this day
    otd_parser = subparsers.add_parser("on-this-day", help="Create 'on this day' playlist")
    otd_parser.add_argument("--years-ago", type=int, default=1, help="Years ago to look back (default: 1)")
    
    # Smart mix
    mix_parser = subparsers.add_parser("mix", help="Smart mix of playlists")
    mix_parser.add_argument("playlists", nargs="+", help="Playlist names to mix")
    mix_parser.add_argument("--name", required=True, help="Name for the mixed playlist")
    mix_parser.add_argument("--strategy", choices=["balanced", "weighted", "shuffled", "chronological"],
                           default="balanced", help="Mixing strategy (default: balanced)")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Get Spotify client
    try:
        sp = get_spotify_client(__file__)
        user = get_user_info(sp)
        print(f"✅ Authenticated as: {user.get('display_name', 'Unknown')}\n")
    except Exception as e:
        print(f"❌ Failed to authenticate: {e}")
        return 1
    
    # Execute command
    try:
        if args.command == "theme":
            result = generate_theme_playlist(sp, args.theme, args.tracks)
            if result:
                print(f"\n✅ Theme playlist created successfully!")
            else:
                print(f"\n⚠️  Failed to create theme playlist")
        
        elif args.command == "time-capsule":
            result = create_time_capsule_playlist(sp, args.year, args.tracks)
            if result:
                print(f"\n✅ Time capsule playlist created successfully!")
            else:
                print(f"\n⚠️  Failed to create time capsule playlist")
        
        elif args.command == "on-this-day":
            result = create_on_this_day_playlist(sp, years_ago=args.years_ago)
            if result:
                print(f"\n✅ 'On this day' playlist created successfully!")
            else:
                print(f"\n⚠️  Failed to create 'on this day' playlist")
        
        elif args.command == "mix":
            result = smart_mix_playlists(sp, args.playlists, args.name, args.strategy)
            if result:
                print(f"\n✅ Mixed playlist created successfully!")
            else:
                print(f"\n⚠️  Failed to create mixed playlist")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
