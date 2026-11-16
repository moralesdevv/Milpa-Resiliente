"""Disparo de la ingesta de una zona (R1) como PROCESO externo: la API nunca importa ``milpa_etl``.

Pasos (CLI ``milpa-etl``, README §9), solo los que escriben archivos bajo ``DATA_DIR``:
``fetch power`` → ``curate`` → ``validate`` → [``fetch imerg`` → ``merge imerg``, solo con
``EARTHDATA_TOKEN``; el merge exige la serie curada]. El registro de zona, manifiesto y procedencia en PostgreSQL (``milpa-etl register …``)
exige el rol **propietario**, que el proceso de la API no tiene a propósito (ADR-006): lo ejecuta el
operador (``make register``). El resultado del trabajo lo informa en ``next_steps``.

Seguridad: argumentos fijos en lista (sin shell); el nombre de zona se valida como identificador de
archivo; coordenadas y elevación son números; el entorno del hijo es explícito y mínimo (sin
``DATABASE_URL`` ni secretos de la API).
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from api.errors import ApiError, ErrorCode, ValidationFailed

R1 = "R1"
_ZONE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_+-]{0,63}$")
START, END = "2001-01-01", "2025-12-31"  # ventana de 25 años del README


class IngestFailed(ApiError):
    status, code, title = 502, ErrorCode.INTERNAL_ERROR, "La ingesta de la zona falló"


@dataclass(frozen=True)
class ZoneSpec:
    name: str
    lat: float
    lon: float
    elevation_m: float | None
    geojson: dict[str, Any]


Runner = Callable[[Sequence[str], Mapping[str, str], int], "subprocess.CompletedProcess[str]"]


def _run(
    cmd: Sequence[str], env: Mapping[str, str], timeout: int
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - lista fija, sin shell
        list(cmd), capture_output=True, text=True, env=dict(env), timeout=timeout, check=False
    )


class ProcessIngest:
    """``IngestPort`` que invoca ``python -m milpa_etl.cli`` en un proceso hijo."""

    component = R1

    def __init__(
        self,
        *,
        data_dir: Path,
        describe_zone: Callable[[UUID], ZoneSpec | None],
        step_timeout_seconds: int = 3600,
        python: str | None = None,
        runner: Runner = _run,
        earthdata_token: str | None = None,
    ) -> None:
        self.data_dir = data_dir
        self.describe_zone = describe_zone
        self.timeout = step_timeout_seconds
        self.python = python or sys.executable
        self.runner = runner
        self.token = earthdata_token

    def is_available(self) -> bool:
        return importlib.util.find_spec("milpa_etl") is not None

    def _env(self) -> dict[str, str]:
        keep = {
            k: os.environ[k]
            for k in ("PATH", "SYSTEMROOT", "HOME", "TMPDIR", "TEMP")
            if k in os.environ
        }
        env = {**keep, "DATA_DIR": str(self.data_dir), "PYTHONUTF8": "1", "MILPA_MODE": "sandbox"}
        if self.token:
            env["EARTHDATA_TOKEN"] = self.token
        return env

    def _step(self, name: str, args: Sequence[str], log: list[dict[str, Any]]) -> None:
        cmd = [self.python, "-m", "milpa_etl.cli", *args]
        t0 = time.monotonic()
        try:
            res = self.runner(cmd, self._env(), self.timeout)
        except subprocess.TimeoutExpired as exc:
            log.append({"step": name, "ok": False, "error": "timeout"})
            raise IngestFailed(f"El paso '{name}' excedió el tiempo máximo") from exc
        except OSError as exc:
            log.append({"step": name, "ok": False, "error": type(exc).__name__})
            raise IngestFailed(f"No se pudo ejecutar milpa-etl ({type(exc).__name__})") from exc
        seconds = round(time.monotonic() - t0, 1)
        if res.returncode != 0:
            tail = (res.stderr or res.stdout or "").strip().splitlines()[-1:] or ["sin detalle"]
            log.append({"step": name, "ok": False, "code": res.returncode, "seconds": seconds})
            # el detalle de la ETL no incluye datos personales, pero se recorta por seguridad
            raise IngestFailed(
                f"El paso '{name}' terminó con código {res.returncode}: {tail[0][:200]}"
            )
        log.append({"step": name, "ok": True, "seconds": seconds})

    def ingest_zone(self, zone_id: UUID) -> Mapping[str, Any]:
        spec = self.describe_zone(zone_id)
        if spec is None:
            raise ValidationFailed("La zona no existe")
        if not _ZONE_RE.match(spec.name):
            raise ValidationFailed(
                "El nombre de la zona no es un identificador de archivo válido (A-Z a-z 0-9 _ + -)"
            )
        if spec.elevation_m is None:
            raise ValidationFailed(
                "La zona no tiene elevación (DEM): ejecute 'milpa-etl fetch dem' antes de la ingesta"
            )
        lat, lon, elev = f"{spec.lat:.6f}", f"{spec.lon:.6f}", f"{spec.elevation_m:.2f}"
        log: list[dict[str, Any]] = []
        self._step(
            "fetch power",
            [
                "fetch",
                "power",
                "--zone",
                spec.name,
                "--lat",
                lat,
                "--lon",
                lon,
                "--start",
                START,
                "--end",
                END,
            ],
            log,
        )
        # Orden de R1 (su README): la curación va ANTES del merge; `merge imerg` exige la serie curada.
        self._step(
            "curate",
            ["curate", "--zone", spec.name, "--lat", lat, "--lon", lon, "--elev", elev],
            log,
        )
        self._step("validate", ["validate", "--zone", spec.name, "--lat", lat, "--elev", elev], log)
        if self.token:
            with tempfile.TemporaryDirectory() as tmp:
                gj = Path(tmp) / "zone.geojson"
                gj.write_text(
                    json.dumps({"type": "Feature", "properties": {}, "geometry": spec.geojson}),
                    encoding="utf-8",
                )
                self._step(
                    "fetch imerg",
                    [
                        "fetch",
                        "imerg",
                        "--zone",
                        spec.name,
                        "--geojson",
                        str(gj),
                        "--start",
                        START,
                        "--end",
                        END,
                    ],
                    log,
                )
            self._step("merge imerg", ["merge", "imerg", "--zone", spec.name], log)
        meta_path = self.data_dir / "curated" / spec.name / "curated_meta.json"
        data_hash = None
        if meta_path.is_file():
            try:
                data_hash = json.loads(meta_path.read_text(encoding="utf-8")).get("data_hash")
            except (OSError, ValueError):
                data_hash = None
        return {
            "zone": spec.name,
            "steps": log,
            "imerg": bool(self.token),
            "data_hash": data_hash,
            "next_steps": [
                "milpa-etl register zone … (rol propietario)",
                "milpa-etl register manifest",
                "milpa-etl register provenance --zone " + spec.name,
            ],
        }
