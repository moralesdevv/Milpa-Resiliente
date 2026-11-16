"""T-I mínimo: serie con forma de curated/daily.parquet de R1 → adaptador → motor → payloads."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "milpa_core" / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from make_synthetic import make  # noqa: E402
from milpa_adapter import load_curated_daily  # noqa: E402
import r2_run  # noqa: E402


def test_adapter_reindexes_missing_days_as_nan(tmp_path):
    df = make()
    df = df.drop(index=[10, 11, 12])  # días ausentes en el archivo
    df2 = df.copy()
    df2["cell_id"] = "otra"
    f = tmp_path / "daily.csv"
    pd.concat([df, df2]).to_csv(f, index=False)
    s, info = load_curated_daily(f, "synthetic_0", "2021-01-01", "2025-12-31")
    assert info["cell_id"] == "synthetic_0"
    assert len(s.dates) == 1826 and np.isnan(s.precip_mm[10:13]).all()


def test_r2_run_writes_payloads(tmp_path):
    r2_run.main(["--synthetic", "--out", str(tmp_path)])
    for name in ("summary", "heatmap", "dekad_chart", "rank", "soil_voi", "report_model", "enums"):
        assert (tmp_path / f"{name}.json").exists(), name
    rank = json.loads((tmp_path / "rank.json").read_text())
    assert rank["status"] in ("ok", "insufficient") and rank["stability"]["interpretation_es"]
