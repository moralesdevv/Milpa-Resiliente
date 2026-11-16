"""SHA-256 y hashes lógicos deterministas (spec R3 §16, README §25).

R3 NO inventa hashes de entradas ausentes: las funciones fallan con ``MissingInputError`` que
nombra exactamente qué falta.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import pandas as pd

CHUNK = 1024 * 1024
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class MissingInputError(FileNotFoundError):
    """Falta una entrada requerida; el mensaje indica cuál."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise MissingInputError(f"No existe el archivo requerido: {path.name}")
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def is_sha256(value: str) -> bool:
    return bool(SHA256_RE.match(value))


def canonical_json(obj: Any) -> bytes:
    """JSON canónico: claves ordenadas, sin espacios, UTF-8, sin NaN."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def canonical_hash(obj: Any) -> str:
    """Hash de parámetros/configuración normalizados (``params_hash``, ``region_config_hash``)."""
    return sha256_bytes(canonical_json(obj))


def logical_dataframe_hash(df: pd.DataFrame, sort_keys: Sequence[str]) -> str:
    """Hash lógico: independiente del orden físico de filas/columnas y del formato de archivo.

    Las columnas se ordenan alfabéticamente, las filas por ``sort_keys``; valores nulos se
    serializan como ``null`` (nunca como 0).
    """
    missing = [k for k in sort_keys if k not in df.columns]
    if missing:
        raise ValueError(f"Columnas clave ausentes para el hash lógico: {missing}")
    cols = sorted(df.columns)
    ordered = df[cols].sort_values(list(sort_keys), kind="mergesort").reset_index(drop=True)
    h = hashlib.sha256()
    h.update(canonical_json(cols))
    for row in ordered.itertuples(index=False, name=None):
        h.update(canonical_json([None if pd.isna(v) else _plain(v) for v in row]))
        h.update(b"\n")
    return h.hexdigest()


def _plain(v: Any) -> Any:
    return v.item() if hasattr(v, "item") else (str(v) if hasattr(v, "isoformat") else v)


def data_hash(raw_sha256s: Iterable[str], curated_logical_hash: str) -> str:
    """README §25: hash de la lista ordenada de ``raw_sha256`` más el hash lógico del curado."""
    raws = sorted(raw_sha256s)
    for value in [*raws, curated_logical_hash]:
        if not is_sha256(value):
            raise ValueError("Hash SHA-256 inválido en la entrada de data_hash")
    return canonical_hash({"raw_sha256": raws, "curated_logical_sha256": curated_logical_hash})
