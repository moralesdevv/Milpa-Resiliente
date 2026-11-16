"""Benchmarks T-B (BE-11). Mide con datos SINTÉTICOS DE CARGA y registra las condiciones.

No define objetivos de latencia (spec R3 §23.2): solo mide y reporta. Lo que depende de R2 (ranking,
heatmap, escenarios, matriz base) NO se mide y se informa como ``bloqueado``. Los datos Parquet
sintéticos se generan en un directorio temporal, con columnas genéricas (no son datos climáticos ni
imitan el esquema de R1) y se borran al terminar.
"""

from __future__ import annotations

import json
import os
import platform
import secrets
import statistics
import sys
import tempfile
import time
import tracemalloc
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from api.reproducibility.hashing import sha256_file

API_DIR = Path(__file__).resolve().parents[3]
DEFAULT_ADMIN_URL = "postgresql+psycopg://postgres:postgres_test_only@127.0.0.1:55432/postgres"


@dataclass
class Result:
    name: str
    status: str  # medido | bloqueado | omitido
    runs: int = 0
    unit: str = "ms"
    min: float | None = None
    p50: float | None = None
    p95: float | None = None
    max: float | None = None
    mean: float | None = None
    peak_py_alloc_mb: float | None = None
    detail: dict[str, Any] = field(default_factory=dict)
    note: str = ""


def peak_rss_mb() -> float | None:
    """Pico de memoria residente del proceso (MB), sin dependencias nuevas."""
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            class PMC(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
            k32.GetCurrentProcess.restype = wintypes.HANDLE
            psapi.GetProcessMemoryInfo.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(PMC),
                wintypes.DWORD,
            ]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            pmc = PMC()
            pmc.cb = ctypes.sizeof(PMC)
            if not psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
                return None
            return float(pmc.PeakWorkingSetSize) / 1e6
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmHWM:"):
                return int(line.split()[1]) / 1024
    except Exception:
        return None
    return None


def timed(name: str, fn: Callable[[], Any], runs: int, warmup: int = 2, **detail: Any) -> Result:
    for _ in range(warmup):
        fn()
    samples: list[float] = []
    tracemalloc.start()
    for _ in range(runs):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    s = sorted(samples)
    return Result(
        name,
        "medido",
        runs,
        "ms",
        round(s[0], 3),
        round(statistics.median(s), 3),
        round(s[min(len(s) - 1, int(0.95 * len(s)))], 3),
        round(s[-1], 3),
        round(statistics.fmean(s), 3),
        round(peak / 1e6, 2),
        detail,
    )


def blocked(name: str, why: str) -> Result:
    return Result(name, "bloqueado", note=why)


def setup_database(admin_url: str) -> tuple[str, str, str]:
    name = f"milpa_bench_{uuid.uuid4().hex[:8]}"
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    role = os.environ.get("TEST_APP_ROLE", "milpa_app")
    pw = os.environ.get("TEST_APP_ROLE_PASSWORD", "app_test_only")
    with admin.connect() as c:
        if not c.execute(text("SELECT 1 FROM pg_roles WHERE rolname=:r"), {"r": role}).first():
            c.execute(text(f"CREATE ROLE {role} LOGIN PASSWORD '{pw}' NOSUPERUSER NOBYPASSRLS"))
        c.execute(text(f'CREATE DATABASE "{name}"'))
    url = make_url(admin_url).set(database=name).render_as_string(hide_password=False)
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    os.environ["APP_DB_ROLE"] = role
    command.upgrade(cfg, "head")
    app_url = make_url(url).set(username=role, password=pw).render_as_string(hide_password=False)
    admin.dispose()
    return name, url, app_url


def teardown_database(admin_url: str, name: str) -> None:
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    admin.dispose()


def seed(owner_url: str, n_parcels: int) -> dict[str, Any]:
    from api.security.passwords import hash_password

    eng = create_engine(owner_url)
    pw = hash_password("bench-password-123456")
    with eng.begin() as c:
        region = c.execute(
            text(
                "INSERT INTO geo.region (code,name,config_uri,config_hash,bbox) VALUES ('B','b','x',repeat('0',64),"
                "ST_GeomFromText('POLYGON((-90 14,-89 14,-89 15,-90 15,-90 14))',4326)) RETURNING region_id"
            )
        ).scalar_one()
        zone = c.execute(
            text(
                "INSERT INTO geo.zone (region_id,name,geom) VALUES (:r,'z',ST_Multi(ST_GeomFromText("
                "'POLYGON((-90 14,-89 14,-89 15,-90 15,-90 14))',4326))) RETURNING zone_id"
            ),
            {"r": region},
        ).scalar_one()
        users = []
        for i in range(2):
            uid = c.execute(
                text(
                    "INSERT INTO auth.app_user (email,password_hash,role) VALUES (:e,:h,'agricultor') RETURNING user_id"
                ),
                {"e": f"bench{i}@example.org", "h": pw},
            ).scalar_one()
            fid = c.execute(
                text(
                    "INSERT INTO farm.farmer (user_id,display_name) VALUES (:u,'x') RETURNING farmer_id"
                ),
                {"u": uid},
            ).scalar_one()
            c.execute(
                text(
                    "INSERT INTO auth.consent (subject_user_id,purpose,text_version,granted_at) VALUES (:u,'analysis','b',now())"
                ),
                {"u": uid},
            )
            users.append((uid, fid))
        c.execute(
            text(
                "INSERT INTO farm.parcel (zone_id, farmer_id, code) SELECT :z, :f, 'P'||g FROM generate_series(1,:n) g"
            ),
            {"z": zone, "f": users[0][1], "n": n_parcels},
        )
        c.execute(
            text(
                "INSERT INTO farm.parcel (zone_id, farmer_id, code) SELECT :z, :f, 'Q'||g FROM generate_series(1,:n) g"
            ),
            {"z": zone, "f": users[1][1], "n": n_parcels},
        )
        one = c.execute(
            text("SELECT parcel_id FROM farm.parcel WHERE farmer_id=:f LIMIT 1"), {"f": users[0][1]}
        ).scalar_one()
    eng.dispose()
    return {
        "user": users[0][0],
        "email": "bench0@example.org",
        "parcel": one,
        "zone": zone,
        "n_parcels": n_parcels,
    }


def run_all(admin_url: str, runs: int, n_parcels: int, parquet_rows: int) -> dict[str, Any]:  # noqa: PLR0915
    from fastapi.testclient import TestClient

    from api.config import Settings
    from api.db.uow import unit_of_work
    from api.jobs.dispatch import (
        InlineDispatcher,
        NullDispatcher,
        ProcessPoolDispatcher,
        WorkerConfig,
    )
    from api.jobs.registry import override_handler
    from api.main import create_app
    from api.models.enums import JobKind
    from api.repositories.jobs import JobRepository
    from api.storage.object_store import LocalObjectStore
    from api.storage.parquet import ParquetContract, ParquetDatasetReader

    results: list[Result] = []
    name, owner_url, app_url = setup_database(admin_url)
    tmp = Path(tempfile.mkdtemp(prefix="milpa-bench-"))
    pg_version = ""
    try:
        eng = create_engine(owner_url)
        with eng.connect() as c:
            pg_version = c.execute(text("SHOW server_version")).scalar_one()
        eng.dispose()
        info = seed(owner_url, n_parcels)
        settings = Settings(
            database_url=app_url,
            jwt_secret=secrets.token_urlsafe(48),  # efímero: solo este proceso de medición
            data_dir=tmp,
            rate_limit_per_min=10_000_000,
        )
        app = create_app(settings, dispatcher=NullDispatcher(), recover_on_start=False)
        with TestClient(app) as client:
            results.append(
                timed(
                    "GET /healthz (ASGI en proceso, sin red)",
                    lambda: client.get("/healthz"),
                    runs * 4,
                )
            )
            tokens: list[str] = []

            def login() -> None:
                r = client.post(
                    "/v1/auth/login",
                    json={"email": info["email"], "password": "bench-password-123456"},
                )
                tokens[:] = [r.json()["access_token"]]

            results.append(
                timed("POST /v1/auth/login (Argon2id verify + JWT)", login, max(10, runs // 2))
            )
            h = {"Authorization": f"Bearer {tokens[0]}"}
            results.append(
                timed(
                    "GET /v1/parcels/{id} (JWT + RLS + generalización)",
                    lambda: client.get(f"/v1/parcels/{info['parcel']}", headers=h),
                    runs * 2,
                )
            )
            results.append(
                timed(
                    "GET /v1/zones (paginado)", lambda: client.get("/v1/zones", headers=h), runs * 2
                )
            )

            def count_rls() -> None:
                with unit_of_work(app.state.engine, info["user"]) as uow:
                    uow.session.execute(text("SELECT count(*) FROM farm.parcel")).scalar_one()

            results.append(
                timed(
                    f"SQL: count(*) farm.parcel con RLS ({2 * n_parcels} filas totales)",
                    count_rls,
                    runs,
                    detail={"filas_totales": 2 * n_parcels, "filas_visibles": n_parcels},
                )
            )

        # ---- trabajos: ciclo completo create/claim/finish con handler nulo (en línea)
        wcfg = WorkerConfig.from_settings(settings)
        prev = override_handler(JobKind.report, lambda ctx, p: {"v": 1})
        try:
            inline = InlineDispatcher(wcfg)

            def one_job() -> None:
                with unit_of_work(app.state.engine, info["user"]) as uow:
                    job, _ = JobRepository(uow.session).create(
                        JobKind.report, {"v": 1}, info["user"], None
                    )
                    uow.commit()
                    jid = job.job_id
                inline.submit(jid)

            results.append(
                timed(
                    "Trabajo: crear + reclamar + ejecutar handler nulo + cerrar (en línea)",
                    one_job,
                    runs,
                    detail={"nota": "mide la sobrecarga del sistema de trabajos, no ciencia"},
                )
            )

            # ---- pool de procesos real (spawn): latencia de extremo a extremo con 1 y 2 workers
            for workers in (1, 2):
                pool = ProcessPoolDispatcher(wcfg, max_workers=workers)
                ids = []
                with unit_of_work(app.state.engine, info["user"]) as uow:
                    for _ in range(12):
                        job, _ = JobRepository(uow.session).create(
                            JobKind.parcel_delete,
                            {"v": 1, "parcel_id": str(uuid.uuid4())},
                            info["user"],
                            None,
                        )
                        ids.append(job.job_id)
                    uow.commit()
                t0 = time.perf_counter()
                for jid in ids:
                    pool.submit(jid)
                deadline = time.monotonic() + 180
                while time.monotonic() < deadline:
                    with unit_of_work(app.state.engine) as u2:
                        pending = u2.session.execute(
                            text(
                                "SELECT count(*) FROM engine.job WHERE status IN ('queued','running') AND kind='parcel_delete'"
                            )
                        ).scalar_one()
                    if pending == 0:
                        break
                    time.sleep(0.2)
                total = (time.perf_counter() - t0) * 1000
                pool.shutdown()
                results.append(
                    Result(
                        f"Pool de procesos spawn: 12 trabajos parcel_delete (no-op), {workers} worker(es)",
                        "medido",
                        1,
                        "ms",
                        detail={
                            "total_ms": round(total, 1),
                            "trabajos": 12,
                            "workers": workers,
                            "incluye_arranque_de_procesos_spawn": True,
                        },
                    )
                )
        finally:
            override_handler(JobKind.report, prev)

        # ---- Parquet SINTÉTICO DE CARGA (columnas genéricas, no el esquema de R1)
        rng = np.random.default_rng(0)
        df = pd.DataFrame(
            {
                "k1": np.arange(parquet_rows, dtype=np.int64),
                "k2": rng.integers(0, 50, parquet_rows),
                "a": rng.random(parquet_rows),
                "b": rng.random(parquet_rows),
                "c": rng.random(parquet_rows),
                "label": rng.choice(["x", "y", "z"], parquet_rows),
            }
        )
        store = LocalObjectStore(tmp)
        path = store.resolve("bench/synthetic_load.parquet")
        path.parent.mkdir(parents=True)
        t0 = time.perf_counter()
        df.to_parquet(path, index=False)
        write_ms = (time.perf_counter() - t0) * 1000
        size_mb = path.stat().st_size / 1e6
        reader = ParquetDatasetReader(store)
        contract = ParquetContract("synthetic_load", ("k1",), ("k1", "a"))
        results.append(
            timed(
                f"Parquet: lectura completa ({parquet_rows:,} filas x 6 columnas)",
                lambda: reader.read("bench/synthetic_load.parquet", contract),
                max(3, runs // 4),
                1,
                archivo_mb=round(size_mb, 1),
                escritura_ms=round(write_ms, 1),
            )
        )
        results.append(
            timed(
                "Parquet: lectura de 2 columnas",
                lambda: reader.read("bench/synthetic_load.parquet", contract, columns=["k1", "a"]),
                max(3, runs // 4),
                1,
            )
        )
        results.append(
            timed(
                "SHA-256 del archivo Parquet",
                lambda: sha256_file(path),
                max(3, runs // 4),
                1,
                archivo_mb=round(size_mb, 1),
            )
        )

        # ---- PDF
        try:
            from api.cli import sample_report_input
            from api.reports.pdf import render_pdf

            data = sample_report_input("public", "es+en")
            render_pdf(data)
            results.append(
                timed(
                    "PDF: render ReportLab (plantilla PROVISIONAL)",
                    lambda: render_pdf(data),
                    max(5, runs // 4),
                    1,
                )
            )
        except Exception as exc:
            results.append(
                Result(
                    "PDF: render ReportLab",
                    "omitido",
                    note=f"{type(exc).__name__}: no se pudo generar el PDF",
                )
            )

        for what in (
            "POST /v1/runs/{id}/rank (ranking + estabilidad)",
            "GET /v1/runs/{id}/heatmap",
            "GET /v1/runs/{id}/dekad-chart",
            "Corrida base (matriz estrategia x cohorte x fecha)",
            "Grilla de 45 corridas de escenarios",
        ):
            results.append(
                blocked(
                    what,
                    "Requiere milpa_core (R2) y datos curados (R1): no integrados. No se estima ni se inventa.",
                )
            )
    finally:
        teardown_database(admin_url, name)
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)

    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "conditions": {
            "host": platform.platform(),
            "cpu_count": os.cpu_count(),
            "python": sys.version.split()[0],
            "postgres": pg_version,
            "runs_base": runs,
            "parcels_per_user": n_parcels,
            "parquet_synthetic_rows": parquet_rows,
            "peak_rss_mb_process": round(peak_rss_mb() or 0, 1),
            "transport": "ASGI en proceso (TestClient): NO incluye red ni uvicorn",
            "db": "contenedor PostGIS local, misma máquina",
            "limitaciones": [
                "Datos sintéticos de carga; no representan los volúmenes reales de MILPA.",
                "Mediciones en un host de desarrollo con otras cargas; no son objetivos de latencia ni capacidad de producción.",
                "El ranking, heatmap y matriz base dependen de R2 y no se miden.",
                "peak_py_alloc_mb solo cuenta asignaciones de Python (tracemalloc), no memoria nativa de pyarrow.",
            ],
        },
        "results": [asdict(r) for r in results],
    }


def to_markdown(report: dict[str, Any]) -> str:
    c = report["conditions"]
    lines = [
        "# Benchmarks T-B (BE-11)",
        "",
        f"Generado: {report['generated_at']}",
        "",
        "## Condiciones",
        "",
    ]
    for k, v in c.items():
        if k == "limitaciones":
            continue
        lines.append(f"- **{k}**: {v}")
    lines += [
        "",
        "## Resultados",
        "",
        "| Prueba | Estado | n | min (ms) | p50 (ms) | p95 (ms) | máx (ms) | media (ms) | pico alloc Py (MB) | detalle |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in report["results"]:
        det = "; ".join(f"{k}={v}" for k, v in r["detail"].items()) or r["note"]
        lines.append(
            f"| {r['name']} | {r['status']} | {r['runs'] or ''} | {r['min'] if r['min'] is not None else ''} | {r['p50'] if r['p50'] is not None else ''} | "
            f"{r['p95'] if r['p95'] is not None else ''} | {r['max'] if r['max'] is not None else ''} | {r['mean'] if r['mean'] is not None else ''} | "
            f"{r['peak_py_alloc_mb'] if r['peak_py_alloc_mb'] is not None else ''} | {det} |"
        )
    lines += ["", "## Limitaciones", ""] + [f"- {x}" for x in c["limitaciones"]]
    lines += [
        "",
        "No se establece ningún objetivo de latencia a partir de estas cifras (spec R3 §23.2).",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    admin_url = os.environ.get("TEST_DATABASE_ADMIN_URL", DEFAULT_ADMIN_URL)
    runs = int(os.environ.get("BENCH_RUNS", "30"))
    n_parcels = int(os.environ.get("BENCH_PARCELS", "5000"))
    rows = int(os.environ.get("BENCH_PARQUET_ROWS", "1000000"))
    out = Path(os.environ.get("BENCH_OUT", str(API_DIR.parents[1] / "bench-results")))
    try:
        report = run_all(admin_url, runs, n_parcels, rows)
    except Exception as exc:
        print(
            f"BLOQUEADO: no se pudo preparar PostgreSQL de pruebas ({type(exc).__name__}). "
            "Defina TEST_DATABASE_ADMIN_URL (ver docs/TESTING.md).",
            file=sys.stderr,
        )
        return 2
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    (out / f"bench-{stamp}.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    md = to_markdown(report)
    (out / "LATEST.md").write_text(md, encoding="utf-8")
    print(md)
    return 0
