"""Identificadores de reproducibilidad de una corrida, manifiestos y verificación previa a ``reproduce``.

Lo que NO hace (pertenece a otros roles): descargar/curar fuentes (R1), recalcular la corrida (R2).
Lo que SÍ hace: validar y comparar los identificadores que la API transporta, verificar archivos
contra un manifiesto SHA-256 e informar EXACTAMENTE qué entrada falta.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from api.adapters.milpa_core import check_core_contract
from api.reproducibility.hashing import MissingInputError, is_sha256, sha256_file

SHA = r"^[0-9a-f]{64}$"
MANIFEST_FORMAT = "r3-manifest-v0-provisional"  # el manifiesto oficial de ingestas lo define R1


class RunIdentifiers(BaseModel):
    """code_version, region_config_hash, catalog_hash, data_hash, params_hash, seed (README §25)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code_version: str = Field(min_length=1, max_length=200)
    region_config_hash: str = Field(pattern=SHA)
    catalog_hash: str = Field(pattern=SHA)
    data_hash: str = Field(pattern=SHA)
    params_hash: str = Field(pattern=SHA)
    seed: int = Field(ge=0, lt=2**63)

    def diff(self, other: RunIdentifiers) -> list[str]:
        """Nombres de los identificadores que cambiaron (detección de cambios entre corridas)."""
        return [k for k in type(self).model_fields if getattr(self, k) != getattr(other, k)]


@dataclass
class ManifestReport:
    ok: bool
    checked: int = 0
    missing: list[str] = field(default_factory=list)
    mismatched: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def build_manifest(base: Path, relative_paths: list[str]) -> dict[str, Any]:
    """Manifiesto determinista (rutas ordenadas). Falla si falta algún archivo (nada se inventa)."""
    entries = []
    for rel in sorted(relative_paths):
        p = base / rel
        entries.append({"path": rel, "sha256": sha256_file(p), "size": p.stat().st_size})
    return {"format": MANIFEST_FORMAT, "files": entries}


def verify_manifest(manifest: dict[str, Any], base: Path) -> ManifestReport:
    rep = ManifestReport(ok=True)
    if manifest.get("format") != MANIFEST_FORMAT:
        rep.ok = False
        rep.errors.append(f"formato de manifiesto no reconocido (se esperaba {MANIFEST_FORMAT})")
        return rep
    root = base.resolve()
    for entry in manifest.get("files", []):
        rel, expected = str(entry.get("path", "")), str(entry.get("sha256", ""))
        target = (root / rel).resolve()
        if not target.is_relative_to(root):
            rep.errors.append(f"ruta fuera de la base: {rel}")
            rep.ok = False
            continue
        if not is_sha256(expected):
            rep.errors.append(f"hash inválido en el manifiesto para {rel}")
            rep.ok = False
            continue
        try:
            actual = sha256_file(target)
        except MissingInputError:
            rep.missing.append(rel)
            rep.ok = False
            continue
        rep.checked += 1
        if actual != expected:
            rep.mismatched.append(rel)
            rep.ok = False
    return rep


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise MissingInputError(f"No existe el manifiesto: {path.name}")
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


# ---------------------------------------------------------------------- make reproduce
EXIT_OK = 0
EXIT_MISSING_INPUTS = 2
EXIT_WAITING_DEPENDENCY = 3


DEMO_FORMAT_KEYS = ("zone", "seed", "data_hash", "files_sha256")
ETL_TIMEOUT_SECONDS = 600


@dataclass
class ReproduceStatus:
    exit_code: int
    missing: list[str]
    notes: list[str]
    verified: list[str] = field(default_factory=list)


def verify_demo_package(demo: Path) -> tuple[list[str], list[str], dict[str, Any] | None]:
    """Verifica ``data/demo`` contra su ``EXPECTED.json`` (formato de R1: ``build-demo``).

    Devuelve ``(problemas, verificados, expected)``. Comprueba los SHA-256 de los archivos congelados.
    """
    path = demo / "EXPECTED.json"
    try:
        expected = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"EXPECTED.json ilegible ({type(exc).__name__})"], [], None
    absent = [k for k in DEMO_FORMAT_KEYS if k not in expected]
    if absent:
        return [f"EXPECTED.json sin las claves {absent} (formato de R1)"], [], None
    problems: list[str] = []
    verified: list[str] = []
    if not is_sha256(str(expected["data_hash"])):
        problems.append("EXPECTED.json: data_hash no es un SHA-256")
    for rel, digest in sorted(expected["files_sha256"].items()):
        f = demo / rel
        if not f.is_file():
            problems.append(f"falta el archivo congelado {rel}")
        elif sha256_file(f) != digest:
            problems.append(f"hash distinto en el archivo congelado {rel}")
        else:
            verified.append(f"archivo congelado {rel}")
    return problems, verified, expected


PLATFORM_RTOL = 1e-9  # [Verificar] el README §25 fija la tolerancia por ADR; valor provisional
PLATFORM_ATOL = 1e-12


def frames_equal_within_tolerance(a: Any, b: Any) -> tuple[bool, float, str]:
    """Compara dos DataFrames: esquema y no numéricos EXACTOS; numéricos con tolerancia.

    Devuelve ``(igual, error_relativo_máximo, motivo)``. Los NaN deben coincidir en posición.
    """
    import numpy as np
    import pandas as pd

    if list(a.columns) != list(b.columns) or a.shape != b.shape:
        return False, float("inf"), "esquema o forma distintos"
    worst = 0.0
    for col in a.columns:
        x, y = a[col], b[col]
        if str(x.dtype) != str(y.dtype):
            return False, float("inf"), f"tipo distinto en {col}"
        if pd.api.types.is_float_dtype(x.dtype):
            xv, yv = x.to_numpy(float), y.to_numpy(float)
            if (np.isnan(xv) != np.isnan(yv)).any():
                return False, float("inf"), f"NaN en posiciones distintas en {col}"
            ok = ~np.isnan(xv)
            diff = np.abs(xv[ok] - yv[ok])
            scale = np.maximum(np.abs(xv[ok]), 1e-300)
            if diff.size:
                worst = max(worst, float((diff / scale).max()))
            if (diff > PLATFORM_ATOL + PLATFORM_RTOL * np.abs(xv[ok])).any():
                return False, worst, f"diferencia numérica fuera de tolerancia en {col}"
        elif not x.equals(y):
            return False, float("inf"), f"valores distintos en {col}"
    return True, worst, ""


def _build_demo(tmp: str) -> tuple[dict[str, Any] | None, str | None]:
    """Ejecuta ``milpa-etl build-demo`` en ``tmp`` (proceso aparte). ``(salida, problema)``."""
    env = {**os.environ, "DATA_DIR": tmp, "PYTHONUTF8": "1"}
    try:
        run = subprocess.run(
            [sys.executable, "-m", "milpa_etl.cli", "build-demo"],
            capture_output=True,
            text=True,
            env=env,
            timeout=ETL_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"no se pudo ejecutar milpa-etl ({type(exc).__name__})"
    if run.returncode != 0:
        tail = (run.stderr or "").strip().splitlines()[-1:] or ["sin detalle"]
        return None, f"milpa-etl build-demo falló (código {run.returncode}): {tail[0][:200]}"
    try:
        produced: dict[str, Any] = json.loads(run.stdout)
    except ValueError:
        return None, "milpa-etl build-demo no devolvió JSON"
    return produced, None


def _compare_demo(frozen_dir: Path, fresh_dir: Path) -> tuple[float | None, str | None]:
    """Error relativo máximo entre los Parquet congelados y los regenerados, o el problema."""
    import pandas as pd

    worst = 0.0
    for frozen in sorted(frozen_dir.glob("*.parquet")):
        fresh = fresh_dir / frozen.name
        if not fresh.is_file():
            return None, f"la regeneración no produjo {frozen.name}"
        same, err, why = frames_equal_within_tolerance(
            pd.read_parquet(frozen), pd.read_parquet(fresh)
        )
        if not same:
            return None, f"{frozen.name}: {why}"
        worst = max(worst, err)
    return worst, None


def regenerate_demo(expected: dict[str, Any], demo: Path) -> tuple[str | None, str | None]:
    """Regenera el paquete sintético con la ETL de R1 y lo compara con ``demo``.

    Devuelve ``(veredicto, problema)``: ``exact`` (mismo ``data_hash``), ``tolerance:<error>`` (mismos
    datos hasta error de punto flotante de otra plataforma) o ``None`` con el problema.
    """
    with tempfile.TemporaryDirectory() as tmp:
        produced, problem = _build_demo(tmp)
        if produced is None:
            return None, problem
        if produced.get("data_hash") == expected["data_hash"]:
            return "exact", None
        zone = str(expected["zone"])
        worst, problem = _compare_demo(demo / zone, Path(tmp) / "demo" / zone)
        if worst is None:
            return None, problem
        return f"tolerance:{worst:.2e}", None


def check_reproduce_prerequisites(data_dir: Path) -> ReproduceStatus:
    """Verifica lo verificable y informa con exactitud qué falta. NUNCA simula éxito (spec R3 §16.3).

    Capa de datos (R1): hashes de ``data/demo`` y regeneración determinista con ``milpa-etl``.
    Capa de motor (R2): la recomputación de la corrida base y su comparación con ``EXPECTED.json``
    requieren ``milpa_core``; mientras no exista, el resultado es «esperando dependencia» (código 3).
    """
    missing: list[str] = []
    notes: list[str] = []
    verified: list[str] = []
    core = check_core_contract()
    if not core.package_present:
        missing.append("packages/milpa_core (R2): paquete no instalado")
    elif core.problems:
        missing.append("milpa_core no cumple la fachada documentada: " + "; ".join(core.problems))
    demo = data_dir / "demo"
    expected: dict[str, Any] | None = None
    data_layer_failed = False
    if not demo.is_dir():
        missing.append(f"{demo.name}/ (R1): paquete de demostración congelado ausente en DATA_DIR")
        data_layer_failed = True
    elif not (demo / "EXPECTED.json").is_file():
        missing.append("data/demo/EXPECTED.json (R1): hashes esperados ausentes")
        data_layer_failed = True
    else:
        problems, verified, expected = verify_demo_package(demo)
        if problems:
            missing.extend(f"data/demo: {p}" for p in problems)
            data_layer_failed = True
    if expected is not None and not data_layer_failed:
        if int(expected["seed"]) != 0:
            notes.append("La regeneración con milpa-etl solo admite la semilla 0 de R1")
        else:
            verdict, error = regenerate_demo(expected, demo)
            if error:
                missing.append(f"regeneración con milpa_etl (R1): {error}")
            elif verdict == "exact":
                verified.append(
                    f"data_hash regenerado con milpa-etl = EXPECTED.json ({expected['data_hash'][:12]}…)"
                )
            else:
                err = (verdict or "").split(":", 1)[-1]
                verified.append(
                    "datos regenerados con milpa-etl iguales a data/demo dentro de la tolerancia numérica "
                    f"entre plataformas (error relativo máximo {err}; rtol {PLATFORM_RTOL:g}, provisional)"
                )
    if data_layer_failed or any(
        m.startswith(("data/demo", "regeneración", "data_hash")) for m in missing
    ):
        return ReproduceStatus(EXIT_MISSING_INPUTS, missing, notes, verified)
    if not core.package_present or core.problems:
        notes.append(
            "Capa de datos verificada; falta el motor (R2) para recomputar la corrida base y comparar "
            "las cifras de EXPECTED.json (waiting_for_dependency)."
        )
        return ReproduceStatus(EXIT_WAITING_DEPENDENCY, missing, notes, verified)
    # Capa del motor: recalcula la corrida BASE sobre el paquete congelado y compara la huella.
    from api.reproducibility import engine_check

    zone = str(expected["zone"]) if expected is not None else ""
    diffs, summary = engine_check.verify(demo, zone, Path.cwd())
    if diffs:
        missing.extend(f"motor (R2): {d}" for d in diffs)
        return ReproduceStatus(EXIT_MISSING_INPUTS, missing, notes, verified)
    verified.append(f"corrida base de milpa_core reproducida desde data/demo: {summary}")
    notes.append(
        "Reproducido: datos (R1) y corrida base del motor (R2) sobre una serie SINTÉTICA rotulada. "
        "No valida la ciencia ni usa observaciones reales."
    )
    return ReproduceStatus(EXIT_OK, missing, notes, verified)
