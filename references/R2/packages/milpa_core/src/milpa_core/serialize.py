"""Conversión a JSON (para Parquet/BD/API de R3). Sin E/S: devuelve estructuras de Python."""
from __future__ import annotations

import dataclasses
import math
from enum import Enum
from typing import Any

import numpy as np


def to_jsonable(x: Any) -> Any:
    if dataclasses.is_dataclass(x) and not isinstance(x, type):
        return {f.name: to_jsonable(getattr(x, f.name)) for f in dataclasses.fields(x) if not f.name.startswith("_")}
    if isinstance(x, Enum):
        return x.value
    if isinstance(x, dict):
        return {(k.value if isinstance(k, Enum) else str(k) if not isinstance(k, (str, int, float, bool)) else k): to_jsonable(v)
                for k, v in x.items()}
    if isinstance(x, (list, tuple, set, frozenset)):
        return [to_jsonable(v) for v in x]
    if isinstance(x, np.ndarray):
        return [to_jsonable(v) for v in x.tolist()]
    if isinstance(x, np.datetime64):
        return str(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        v = float(x)
        return None if math.isnan(v) or math.isinf(v) else v
    if isinstance(x, (np.bool_,)):
        return bool(x)
    return x
