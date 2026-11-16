"""Adaptador de lectura Parquet para datos curados de R1 (spec R3 §8.5, §12.1, §14).

No implementa ingesta ni curación. No infiere columnas: cada ``ParquetContract`` declara lo que el
README integral propone y su estado de confirmación. Si el archivo falta, está corrupto o no
cumple el contrato, se lanza un error tipado (mapeado a 503 DATASET_UNAVAILABLE/INCOMPATIBLE).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from api.errors import ApiError, ErrorCode
from api.storage.object_store import ObjectStore, StoragePathError

MAX_PARQUET_BYTES = 512 * 1024 * 1024  # tope defensivo de lectura (configurable por llamada)
ContractStatus = Literal[
    "proposed_pending_r1_confirmation", "confirmed_by_r1", "confirmed_by_delivered_files"
]
_ZONE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_+-]{0,63}$")


class DatasetUnavailable(ApiError):
    status, code, title = 503, ErrorCode.DATASET_UNAVAILABLE, "Dataset no disponible"


class DatasetIncompatible(ApiError):
    status, code, title = (
        503,
        ErrorCode.DATASET_INCOMPATIBLE,
        "Dataset incompatible con el contrato",
    )


class DatasetIntegrityError(ApiError):
    status, code, title = (
        500,
        ErrorCode.INTEGRITY_CHECK_FAILED,
        "Falló la verificación de integridad",
    )


@dataclass(frozen=True)
class ParquetContract:
    """Columnas mínimas exigidas. ``status`` deja explícito si R1 ya las confirmó."""

    name: str
    key: tuple[str, ...]
    required_columns: tuple[str, ...]
    status: ContractStatus = "proposed_pending_r1_confirmation"


# Contrato ZONAL de los archivos que entrega R1 (references/Milpa-Resiliente-R1, `curate`): una serie
# ponderada por zona, SIN ``cell_id`` (el README §13.7 propone clave por celda; ADR-018 registra la
# diferencia). ``cell_id`` es opcional: si un archivo lo trae, entra en la clave de ordenación.
# Solo claves y columnas de las que depende R3; el resto se transporta tal cual.
COVERAGE_CONTRACT = ParquetContract(
    name="coverage",
    key=("variable", "year"),
    required_columns=("variable", "year", "n_expected", "n_valid", "pct_missing"),
    status="confirmed_by_delivered_files",
)
DEKAD_CONTRACT = ParquetContract(
    name="dekad",
    key=("year", "dekad"),
    required_columns=("year", "dekad", "p_mm", "et0_mm", "n_days", "n_valid_days"),
    status="confirmed_by_delivered_files",
)
DAILY_CONTRACT = ParquetContract(
    name="daily",
    key=("obs_date",),
    required_columns=("obs_date", "precip_mm", "et0_mm", "qc_flags"),
    status="confirmed_by_delivered_files",
)


def curated_path(zone: str, name: Literal["daily", "dekad", "coverage"]) -> str:
    if not _ZONE_RE.match(zone):
        raise StoragePathError("Identificador de zona no válido para ruta de archivo")
    return f"curated/{zone}/{name}.parquet"


class ParquetDatasetReader:
    def __init__(self, store: ObjectStore, *, max_bytes: int = MAX_PARQUET_BYTES) -> None:
        self.store = store
        self.max_bytes = max_bytes

    def read(
        self,
        relative: str,
        contract: ParquetContract,
        *,
        expected_sha256: str | None = None,
        columns: list[str] | None = None,
    ) -> pd.DataFrame:
        try:
            if not self.store.exists(relative):
                raise DatasetUnavailable(
                    f"El dataset '{contract.name}' no está disponible (pendiente de R1).",
                    hint="Ver docs/integration/R1_DATA_CONTRACT.md",
                )
            if self.store.size(relative) > self.max_bytes:
                raise DatasetIncompatible("El archivo excede el tamaño máximo de lectura")
            if expected_sha256 is not None and self.store.sha256(relative) != expected_sha256:
                raise DatasetIntegrityError(
                    "El hash SHA-256 del dataset no coincide con el esperado"
                )
            with self.store.open_read(relative) as fh:
                pf = pq.ParquetFile(fh)
                present = set(pf.schema_arrow.names)
                missing = [c for c in contract.required_columns if c not in present]
                if missing:
                    raise DatasetIncompatible(
                        f"Faltan columnas exigidas por el contrato '{contract.name}': {missing}",
                        hint=f"estado del contrato: {contract.status}",
                    )
                use = columns if columns is not None else list(present)
                unknown = [c for c in use if c not in present]
                if unknown:
                    raise DatasetIncompatible(f"Columnas solicitadas inexistentes: {unknown}")
                return pd.DataFrame(pf.read(columns=use).to_pandas())
        except StoragePathError as exc:
            raise DatasetUnavailable("Ruta de dataset no válida") from exc
        except (pa.ArrowInvalid, pa.ArrowIOError, OSError) as exc:
            raise DatasetIncompatible("El archivo Parquet es ilegible o está corrupto") from exc


def write_parquet_deterministic(
    store: ObjectStore, relative: str, df: pd.DataFrame, sort_keys: list[str]
) -> str:
    """Escribe Parquet con orden fijo de filas/columnas (README §25) sin sobrescribir.

    Solo reordena y serializa lo recibido (no calcula nada científico). Devuelve el SHA-256.
    """
    ordered = df[sorted(df.columns)].sort_values(sort_keys, kind="mergesort").reset_index(drop=True)
    table = pa.Table.from_pandas(ordered, preserve_index=False)
    sink = pa.BufferOutputStream()
    pq.write_table(table, sink, compression="zstd", use_dictionary=False, write_statistics=False)
    return store.write_bytes(relative, sink.getvalue().to_pybytes(), overwrite=False)
