# Sync implementation package

Internal implementation for Spotify sync automation. **Use the public API via `from src.scripts.automation.sync import ...`**; this package is not part of the public API.

## Layout

| Module | Responsibility |
|--------|----------------|
| **settings** | Data dir, env overrides, re-export of config constants |
| **logger** | Timestamped log, verbose log, step banners, timed steps, log buffer for email |
| **api** | Spotify client, rate-limited `api_call`, `_chunked` for batching |
| **catalog** | Playlist/track/user caches, `get_existing_playlists`, `get_playlist_tracks`, `get_user_info`, `_load_genre_data` |
| **tracks** | URI helpers, preview URLs, audio features, genre parsing, primary-artist genres |
| **descriptions** | Genre tags from track URIs, emoji, format tags, `_update_playlist_description_with_genres` |

## Design

- **Single source of config**: `settings` re-exports from `src.scripts.automation.config` and overrides `DATA_DIR` from env.
- **No circular imports**: `sync.py` imports from `_sync_impl` and re-exports; other automation modules import from `sync`, not from `_sync_impl`.
- **Testability**: API and catalog can be mocked by replacing imports in tests.
