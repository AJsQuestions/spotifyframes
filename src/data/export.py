"""
Export DataFrames to disk (parquet or CSV by path extension).
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

import pandas as pd


def export_table(df: pd.DataFrame, path: Union[str, Path]) -> Path:
    """Write DataFrame to path; format inferred from extension (.parquet or .csv).

    Args:
        df: DataFrame to write.
        path: Output path (.parquet or .csv).

    Returns:
        Resolved Path that was written.
    """
    p = Path(path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    suffix = (p.suffix or "").lower()
    if suffix == ".parquet":
        df.to_parquet(p, index=False)
    elif suffix == ".csv":
        df.to_csv(p, index=False)
    else:
        # Default to parquet
        if not p.suffix:
            p = p.with_suffix(".parquet")
        df.to_parquet(p, index=False)
    return p
