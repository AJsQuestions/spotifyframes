import unittest
from unittest.mock import MagicMock
import pandas as pd
from pathlib import Path
import shutil
import tempfile

from spotim8.core.client import Spotim8
from spotim8.core.catalog import CacheConfig

class TestSpotim8(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for cache
        self.test_dir = tempfile.mkdtemp()
        self.cache_config = CacheConfig(enabled=True, dir=Path(self.test_dir))
        
        # Mock Spotipy client
        self.mock_sp = MagicMock()
        self.sf = Spotim8(sp=self.mock_sp, cache=self.cache_config)

    def tearDown(self):
        # Remove temporary directory
        shutil.rmtree(self.test_dir)

    def test_init(self):
        self.assertIsInstance(self.sf, Spotim8)
        self.assertTrue(self.sf.catalog.cache.enabled)
        self.assertEqual(self.sf.catalog.cache.dir, Path(self.test_dir))

    def test_playlists_empty(self):
        # Mock empty playlists response
        self.mock_sp.current_user_playlists.return_value = {"items": [], "next": None}
        self.mock_sp.current_user_saved_tracks.return_value = {"total": 0}
        self.mock_sp.me.return_value = {"id": "test_user"}
        self.mock_sp.current_user.return_value = {"id": "test_user"}
        
        # Force fetch
        df = self.sf.playlists(force=True)
        
        # Should contain at least Liked Songs playlist
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["name"], "❤️ Liked Songs")
        self.assertTrue(df.iloc[0]["is_liked_songs"])

    def test_playlists_with_data(self):
        # Mock playlists response
        self.mock_sp.current_user_playlists.return_value = {
            "items": [{
                "id": "pl1",
                "name": "My Playlist",
                "description": "Desc",
                "public": True,
                "collaborative": False,
                "snapshot_id": "snap1",
                "tracks": {"total": 10},
                "owner": {"id": "test_user", "display_name": "Test User"},
                "uri": "spotify:playlist:pl1",
                "images": [{"url": "http://image.url"}]
            }],
            "next": None
        }
        self.mock_sp.current_user_saved_tracks.return_value = {"total": 5}
        self.mock_sp.me.return_value = {"id": "test_user"}
        self.mock_sp.current_user.return_value = {"id": "test_user"}
        
        # Force fetch
        df = self.sf.playlists(force=True)
        
        self.assertEqual(len(df), 2) # Liked songs + 1 playlist
        
        # Check Liked Songs
        liked = df[df["is_liked_songs"]]
        self.assertEqual(len(liked), 1)
        self.assertEqual(liked.iloc[0]["track_count"], 5)
        
        # Check regular playlist
        pl = df[~df["is_liked_songs"]]
        self.assertEqual(len(pl), 1)
        self.assertEqual(pl.iloc[0]["name"], "My Playlist")
        self.assertEqual(pl.iloc[0]["is_owned"], True)

    def test_cache_config(self):
        config = CacheConfig(dir="test_path")
        self.assertIsInstance(config.dir, Path)
        self.assertEqual(config.dir, Path("test_path"))

if __name__ == "__main__":
    unittest.main()
