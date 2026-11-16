"""Lectura de la serie climática diaria curada de la zona (R1) desde el almacén de archivos."""

from __future__ import annotations

from typing import Any

import pandas as pd
import pyarrow as pa

from api.errors import ServiceUnavailable
from api.storage.parquet import MAX_PARQUET_BYTES

REQUIRED = {"precip_mm", "precip_source", "tmax_c", "tmin_c"}


def load_daily(store: Any, relative: str) -> pd.DataFrame:
    try:
        size = store.size(relative)
        if size > MAX_PARQUET_BYTES:
            raise ServiceUnavailable("La serie climática supera el tamaño permitido.")
        with store.open_read(relative) as stream:
            frame = pd.read_parquet(stream)
    except (OSError, ValueError, KeyError, pa.ArrowInvalid, pa.ArrowIOError) as exc:
        raise ServiceUnavailable(
            "No está disponible la serie climática curada de Jocotán.",
            hint="Se requiere data/curated/camotan_jocotan/daily.parquet.",
        ) from exc
    missing = sorted(REQUIRED - set(frame.columns))
    if missing:
        raise ServiceUnavailable(
            f"La serie climática no incluye los campos necesarios: {', '.join(missing)}."
        )
    if "obs_date" in frame.columns:
        frame.index = pd.to_datetime(frame.pop("obs_date"), errors="coerce")
    frame.index = pd.to_datetime(frame.index, errors="coerce").normalize()
    frame = frame.loc[frame.index.notna()].sort_index()
    return frame[~frame.index.duplicated(keep="last")]
