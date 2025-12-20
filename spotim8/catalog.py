from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any
import json
import pandas as pd


def _default_data_dir() -> Path:
    """Default to ./data in the current working directory."""
    return Path.cwd() / "data"


@dataclass
class CacheConfig:
    enabled: bool = True
    dir: Path = field(default_factory=_default_data_dir)
    fmt: str = "parquet"  # parquet or csv
    compress: bool = True
    
    def __post_init__(self):
        # Convert string paths to Path objects
        if isinstance(self.dir, str):
            self.dir = Path(self.dir)

class DataCatalog:
    """Stores cached tables + metadata (snapshots, pull timestamps)."""

    def __init__(self, cache: CacheConfig):
        self.cache = cache
        if self.cache.enabled:
            self.cache.dir.mkdir(parents=True, exist_ok=True)
        self._memo: Dict[str, pd.DataFrame] = {}

    def _meta_path(self) -> Path:
        return self.cache.dir / "catalog_meta.json"

    def load_meta(self) -> dict:
        if not self.cache.enabled:
            return {}
        p = self._meta_path()
        if not p.exists():
            return {}
        return json.loads(p.read_text(encoding="utf-8"))

    def save_meta(self, meta: dict) -> None:
        if not self.cache.enabled:
            return
        self._meta_path().write_text(json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")

    def table_path(self, key: str) -> Path:
        return self.cache.dir / f"{key}.{self.cache.fmt}"

    def load(self, key: str) -> Optional[pd.DataFrame]:
        if key in self._memo:
            return self._memo[key]
        if not self.cache.enabled:
            return None
        p = self.table_path(key)
        if not p.exists():
            return None
        if self.cache.fmt == "parquet":
            df = pd.read_parquet(p)
        else:
            df = pd.read_csv(p)
        self._memo[key] = df
        return df

    def save(self, key: str, df: pd.DataFrame) -> pd.DataFrame:
        self._memo[key] = df
        if not self.cache.enabled:
            return df
        p = self.table_path(key)
        if self.cache.fmt == "parquet":
            df.to_parquet(p, index=False)
        else:
            df.to_csv(p, index=False)
        return df

    def clear(self) -> None:
        self._memo.clear()
