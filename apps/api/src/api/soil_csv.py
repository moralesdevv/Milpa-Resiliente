"""Validación del CSV de suelo (R3-F10). Contrato ``SOIL_CSV_V1`` (README integral, apartado 9).

El formato lo fija la especificación («CSV de suelo», ancho, UTF-8, punto decimal) y el paquete de
R1 lo ejemplifica con ``suelo.csv``. Columnas::

  parcel_code,sample_date,depth_from_cm,depth_to_cm,lab,ph,ph_method,om_pct,om_method,
  sand_pct,silt_pct,clay_pct,texture_method,cec_cmol_kg,cec_method,
  effective_root_depth_cm,awc_mm_per_m,awc_method

Reglas de la especificación: una fila por muestra; cada propiedad es opcional y una celda vacía
es «no medido», nunca cero; cada propiedad con valor exige su método; ``ph`` en [3, 10];
``sand + silt + clay = 100 ± 2``; fecha no futura. Los rangos y métodos aceptados salen del
catálogo ``ref.soil_property`` (R1), no de este módulo.

Decisiones de R3 donde el texto no dice nada (ver ADR-010 y ``docs/integration/R1_DATA_CONTRACT.md``):
  * ``parcel_code`` debe coincidir con el ``code`` de la parcela destino (como hace el cargador de
    R1); si no, la fila se rechaza. La representatividad se deriva de eso (``parcela``): el CSV no
    trae esa columna.
  * ``effective_root_depth_cm`` no tiene columna de método; se usa el método ``declarado/medido``
    del catálogo (convención de R1).
  * Si hay alguna columna de textura con valor, deben estar las tres.
  * Las columnas de texto libre rechazan valores que empiecen por ``= + - @`` o tabulador/retorno
    (inyección de fórmulas al abrir el archivo en una hoja de cálculo).

Los mensajes de error NO repiten valores del archivo (pueden ser datos privados).
"""

from __future__ import annotations

import csv
import io
import math
from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd
import pandera.pandas as pa

from api.errors import ApiError, ErrorCode

CONTRACT = "SOIL_CSV_V1"
MAX_ROWS = 5_000
MAX_COLUMNS = 64
MAX_CELL_LEN = 200
REPRESENTATIVENESS_FROM_PARCEL_MATCH = "parcela"
EFFECTIVE_DEPTH_METHOD = "declarado/medido"
TEXTURE_SUM_TOLERANCE = 2.0

FIXED_REQUIRED = ("parcel_code", "sample_date", "depth_from_cm", "depth_to_cm")
FIXED_OPTIONAL = ("lab",)
# código de propiedad del catálogo -> (columna de valor, columna de método | None)
PROPERTY_COLUMNS: dict[str, tuple[str, str | None]] = {
    "ph": ("ph", "ph_method"),
    "organic_matter": ("om_pct", "om_method"),
    "sand": ("sand_pct", "texture_method"),
    "silt": ("silt_pct", "texture_method"),
    "clay": ("clay_pct", "texture_method"),
    "cec": ("cec_cmol_kg", "cec_method"),
    "effective_depth": ("effective_root_depth_cm", None),
    "awc": ("awc_mm_per_m", "awc_method"),
}
_TEXTURE = ("sand", "silt", "clay")
_VALUE_COLUMNS = {v for v, _ in PROPERTY_COLUMNS.values()}
_METHOD_COLUMNS = {m for _, m in PROPERTY_COLUMNS.values() if m}
_TEXT_COLUMNS = ("parcel_code", "lab", *sorted(_METHOD_COLUMNS))
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
_DATE_RE = r"^\d{4}-\d{2}-\d{2}$"
_INT_RE = r"^\d{1,4}$"


class CsvValidationFailed(ApiError):
    status, code, title = 422, ErrorCode.CSV_VALIDATION_FAILED, "El CSV de suelo no es válido"


@dataclass(frozen=True)
class PropertySpec:
    code: str
    unit: str
    valid_min: float | None
    valid_max: float | None
    accepted_methods: tuple[str, ...]


@dataclass(frozen=True)
class MeasurementRow:
    code: str
    value: float
    unit: str
    method: str


@dataclass(frozen=True)
class AcceptedRow:
    line: int
    sampled_at: date
    lab: str | None
    depth_from_cm: int
    depth_to_cm: int
    representativeness: str
    measurements: tuple[MeasurementRow, ...]


def _err(row: int | None, column: str | None, code: str, msg: str) -> dict[str, Any]:
    loc: list[str | int] = ["csv"]
    if row is not None:
        loc.append(row)
    if column is not None:
        loc.append(column)
    return {"loc": loc, "msg": msg, "code": code}


def decode_csv(raw: bytes) -> str:
    if b"\x00" in raw:
        raise CsvValidationFailed(
            errors=[_err(None, None, "encoding", "El archivo contiene bytes nulos")]
        )
    try:
        return raw.decode("utf-8-sig")  # tolera BOM de Excel; UTF-8 estricto
    except UnicodeDecodeError as exc:
        raise CsvValidationFailed(
            errors=[_err(None, None, "encoding", "El archivo debe estar codificado en UTF-8")]
        ) from exc


def _read_table(text: str) -> tuple[list[str], list[list[str]]]:
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        rows = list(reader)
    except csv.Error as exc:
        raise CsvValidationFailed(errors=[_err(None, None, "format", "CSV mal formado")]) from exc
    rows = [r for r in rows if any(c.strip() for c in r)]  # ignora líneas vacías
    if not rows:
        raise CsvValidationFailed(errors=[_err(None, None, "empty", "El archivo está vacío")])
    header = [h.strip() for h in rows[0]]
    return header, rows[1:]


def _check_header(header: list[str]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    if len(header) > MAX_COLUMNS:
        errors.append(_err(None, None, "too_many_columns", f"Máximo {MAX_COLUMNS} columnas"))
    if len(set(header)) != len(header):
        errors.append(_err(None, None, "duplicate_column", "Hay columnas duplicadas"))
    for col in FIXED_REQUIRED:
        if col not in header:
            errors.append(_err(None, col, "missing_column", "Falta una columna obligatoria"))
    allowed = set(FIXED_REQUIRED) | set(FIXED_OPTIONAL) | _VALUE_COLUMNS | _METHOD_COLUMNS
    for col in header:
        if col not in allowed:
            errors.append(_err(None, col[:64], "unknown_column", "Columna no reconocida"))
    if not any(c in _VALUE_COLUMNS for c in header):
        errors.append(
            _err(None, None, "no_property", "No hay ninguna columna de propiedad de suelo")
        )
    return errors


_STRUCTURE = pa.DataFrameSchema(
    {
        "parcel_code": pa.Column(str, pa.Check.str_length(1, 64), nullable=False),
        "sample_date": pa.Column(str, pa.Check.str_matches(_DATE_RE), nullable=False),
        "depth_from_cm": pa.Column(str, pa.Check.str_matches(_INT_RE), nullable=False),
        "depth_to_cm": pa.Column(str, pa.Check.str_matches(_INT_RE), nullable=False),
        "lab": pa.Column(str, pa.Check.str_length(0, 120), nullable=True, required=False),
    },
    strict=False,
)


def _structural_errors(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Validación estructural por fila/columna con pandera (sin devolver los valores)."""
    try:
        _STRUCTURE.validate(df, lazy=True)
    except pa.errors.SchemaErrors as exc:
        out = []
        for _, fc in exc.failure_cases.iterrows():
            idx = fc["index"]
            if pd.isna(idx):
                continue
            col = str(fc["column"])
            out.append(_err(int(idx) + 1, col, "invalid_value", "Valor con formato no válido"))
        return out
    return []


def _formula_errors(df: pd.DataFrame) -> list[dict[str, Any]]:
    out = []
    for col in _TEXT_COLUMNS:
        if col not in df.columns:
            continue
        for i, v in enumerate(df[col].tolist(), start=1):
            if str(v).startswith(_FORMULA_PREFIXES):
                out.append(
                    _err(i, col, "formula_injection", "El texto no puede comenzar con = + - @")
                )
    return out


def parse_soil_csv(
    raw: bytes,
    catalog: dict[str, PropertySpec],
    *,
    today: date,
    parcel_code: str | None,
    max_rows: int = MAX_ROWS,
) -> list[AcceptedRow]:
    """Valida el CSV completo; si hay cualquier error lanza ``CsvValidationFailed`` (todo o nada).

    ``parcel_code`` es el código de la parcela destino: toda fila debe llevar ese mismo código.
    """
    header, body = _read_table(decode_csv(raw))
    errors = _check_header(header)
    if len(body) > max_rows:
        errors.append(_err(None, None, "too_many_rows", f"Máximo {max_rows} filas de datos"))
    if parcel_code is None:
        errors.append(
            _err(None, "parcel_code", "target_parcel_without_code", "La parcela no tiene código")
        )
    if errors:
        raise CsvValidationFailed(errors=errors)

    df = pd.DataFrame(
        [[c.strip() for c in (r + [""] * len(header))[: len(header)]] for r in body],
        columns=header,
        dtype=str,
    )
    for i, r in enumerate(body, start=1):
        if len(r) != len(header):
            errors.append(
                _err(i, None, "column_count", "Número de columnas distinto al encabezado")
            )
        elif any(len(c) > MAX_CELL_LEN for c in r):
            errors.append(
                _err(i, None, "cell_too_long", f"Celda de más de {MAX_CELL_LEN} caracteres")
            )
    errors += _structural_errors(df)
    errors += _formula_errors(df)
    bad_rows = {e["loc"][1] for e in errors if len(e["loc"]) > 1 and isinstance(e["loc"][1], int)}
    accepted: list[AcceptedRow] = []
    for i, raw_rec in enumerate(df.to_dict("records"), start=1):
        rec = {str(k): str(v) for k, v in raw_rec.items()}
        if i in bad_rows:
            continue
        row, row_errors = _semantic_row(i, rec, catalog, today, parcel_code)
        errors += row_errors
        if row is not None:
            accepted.append(row)
    if errors:
        raise CsvValidationFailed(errors=sorted(errors, key=_row_key))
    return accepted


def _numeric(
    i: int, column: str, raw: str, spec: PropertySpec
) -> tuple[float | None, dict[str, Any] | None]:
    try:
        value = float(raw)
    except ValueError:
        return None, _err(i, column, "not_numeric", "El valor no es numérico")
    if not math.isfinite(value):
        return None, _err(i, column, "not_finite", "El valor debe ser finito")
    if (spec.valid_min is not None and value < spec.valid_min) or (
        spec.valid_max is not None and value > spec.valid_max
    ):
        msg = f"Fuera del rango válido [{spec.valid_min}, {spec.valid_max}]"
        return None, _err(i, column, "out_of_range", msg)
    return value, None


def _measurement(
    i: int, code: str, rec: dict[str, str], catalog: dict[str, PropertySpec]
) -> tuple[MeasurementRow | None, list[dict[str, Any]]]:
    """Valida una propiedad de una fila. ``None`` sin error = celda vacía (no medido)."""
    value_col, method_col = PROPERTY_COLUMNS[code]
    raw_value = rec.get(value_col, "")
    raw_method = rec.get(method_col, "") if method_col else EFFECTIVE_DEPTH_METHOD
    if raw_value == "":
        # Un método suelto solo se reprocha en su propia columna si ninguna propiedad que lo
        # comparte tiene valor (textura comparte ``texture_method``).
        return None, []
    spec = catalog.get(code)
    if spec is None:
        return None, [
            _err(i, value_col, "property_not_in_catalog", "Propiedad ausente del catálogo")
        ]
    value, problem = _numeric(i, value_col, raw_value, spec)
    if problem is not None or value is None:
        return None, [problem] if problem else []
    if raw_method == "" or raw_method not in spec.accepted_methods:
        return None, [
            _err(
                i,
                method_col or value_col,
                "method_not_accepted",
                "Método ausente o no aceptado para la propiedad",
            )
        ]
    return MeasurementRow(code, value, spec.unit, raw_method), []


def _semantic_row(
    i: int,
    rec: dict[str, str],
    catalog: dict[str, PropertySpec],
    today: date,
    parcel_code: str | None,
) -> tuple[AcceptedRow | None, list[dict[str, Any]]]:
    errs: list[dict[str, Any]] = []
    if rec["parcel_code"] != parcel_code:
        errs.append(
            _err(
                i, "parcel_code", "parcel_mismatch", "El código no coincide con la parcela destino"
            )
        )
    try:
        sampled = date.fromisoformat(rec["sample_date"])
    except ValueError:
        sampled = None
        errs.append(_err(i, "sample_date", "invalid_date", "Fecha inexistente"))
    if sampled is not None and sampled > today:
        errs.append(
            _err(i, "sample_date", "future_date", "La fecha de muestreo no puede ser futura")
        )
    d_from, d_to = int(rec["depth_from_cm"]), int(rec["depth_to_cm"])
    if d_to <= d_from:
        errs.append(
            _err(i, "depth_to_cm", "depth_order", "depth_to_cm debe ser mayor que depth_from_cm")
        )

    measurements: list[MeasurementRow] = []
    for code in PROPERTY_COLUMNS:
        m, m_errs = _measurement(i, code, rec, catalog)
        errs += m_errs
        if m is not None:
            measurements.append(m)
    # Un método sin ningún valor al que aplicarse (cada columna de método con sus propiedades).
    for method_col in sorted(_METHOD_COLUMNS):
        users = [v for c, (v, mc) in PROPERTY_COLUMNS.items() if mc == method_col]
        if rec.get(method_col, "") != "" and all(rec.get(v, "") == "" for v in users):
            errs.append(_err(i, method_col, "method_without_value", "Método sin valor"))
    errs += _texture_errors(i, rec, measurements)
    if not measurements and not errs:
        errs.append(_err(i, None, "no_measurements", "La fila no tiene ninguna medición"))
    if errs or sampled is None:
        return None, errs
    lab = rec.get("lab") or None
    return (
        AcceptedRow(
            i, sampled, lab, d_from, d_to, REPRESENTATIVENESS_FROM_PARCEL_MATCH, tuple(measurements)
        ),
        errs,
    )


def _texture_errors(
    i: int, rec: dict[str, str], measurements: list[MeasurementRow]
) -> list[dict[str, Any]]:
    cols = {c: PROPERTY_COLUMNS[c][0] for c in _TEXTURE}
    present = [c for c in _TEXTURE if rec.get(cols[c], "") != ""]
    if not present:
        return []
    missing = [c for c in _TEXTURE if c not in present]
    if missing:
        return [
            _err(i, cols[c], "texture_incomplete", "Falta un componente de la textura")
            for c in missing
        ]
    parsed = {m.code: m.value for m in measurements if m.code in _TEXTURE}
    if len(parsed) == len(_TEXTURE) and abs(sum(parsed.values()) - 100.0) > TEXTURE_SUM_TOLERANCE:
        return [_err(i, "sand_pct", "texture_sum", "arena + limo + arcilla debe sumar 100 ± 2")]
    return []


def accepted_by_property(rows: list[AcceptedRow]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in rows:
        for m in r.measurements:
            counts[m.code] = counts.get(m.code, 0) + 1
    return counts


def _row_key(e: dict[str, Any]) -> int:
    loc = e["loc"]
    return loc[1] if len(loc) > 1 and isinstance(loc[1], int) else 0
