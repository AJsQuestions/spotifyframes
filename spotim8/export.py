from __future__ import annotations
from pathlib import Path
import pandas as pd

def export_table(df: pd.DataFrame, out: str) -> str:
    p = Path(out)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.suffix.lower() in [".parquet", ".pq"]:
        df.to_parquet(p, index=False)
    elif p.suffix.lower() == ".csv":
        df.to_csv(p, index=False)
    else:
        # default parquet
        df.to_parquet(p.with_suffix(".parquet"), index=False)
        return str(p.with_suffix(".parquet"))
    return str(p)
