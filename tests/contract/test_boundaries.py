"""Fronteras arquitectónicas (CLAUDE.md §2-§3, spec R3 §2.4): comprobadas por análisis estático."""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "apps" / "api" / "src" / "api"
FORBIDDEN_INFRA = {
    "redis",
    "celery",
    "arq",
    "dask",
    "minio",
    "timescaledb",
    "dagster",
    "kubernetes",
    "sentry-sdk",
    "prometheus-client",
    "opentelemetry-sdk",
    "boto3",
    "pika",
    "kombu",
}


def imports_of(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            mods.add(node.module)
    return mods


def string_mentions(path: Path, needle: str) -> bool:
    return needle in path.read_text(encoding="utf-8")


def py_files(sub: str = "") -> list[Path]:
    return sorted((SRC / sub).rglob("*.py"))


def test_api_never_imports_milpa_etl() -> None:
    for f in py_files():
        assert not any(m.split(".")[0] == "milpa_etl" for m in imports_of(f)), f


def test_milpa_core_is_only_touched_by_its_adapter() -> None:
    allowed = {
        SRC / "adapters" / "milpa_core.py",
        SRC
        / "adapters"
        / "core_io.py",  # E/S del adaptador: construye los objetos tipados del motor
        SRC
        / "reproducibility"
        / "engine_check.py",  # huella reproducible: invoca la fachada del motor
        SRC / "contracts" / "provisional_enums.py",
    }
    for f in py_files():
        if f in allowed:
            continue
        assert not any(m.split(".")[0] == "milpa_core" for m in imports_of(f)), f
        assert not string_mentions(f, "import_module(") or f.name == "milpa_core.py", f


def test_routers_contain_no_persistence_or_business_logic_imports() -> None:
    forbidden = ("sqlalchemy", "api.repositories", "api.models", "api.db", "pandas", "pyarrow")
    for f in py_files("routers"):
        for m in imports_of(f):
            assert not m.startswith(forbidden), (f.name, m)


def test_routers_do_not_import_scientific_or_adapter_implementations() -> None:
    for f in py_files("routers"):
        for m in imports_of(f):
            assert not m.startswith(("api.adapters.milpa_core", "api.adapters.not_integrated")), (
                f.name,
                m,
            )


def test_services_do_not_depend_on_routers_or_fastapi_app() -> None:
    for f in py_files("services"):
        for m in imports_of(f):
            assert not m.startswith(("api.routers", "api.main", "fastapi")), (f.name, m)


def test_repositories_do_not_depend_on_services_or_http() -> None:
    for f in py_files("repositories"):
        for m in imports_of(f):
            assert not m.startswith(("api.services", "api.routers", "fastapi")), (f.name, m)


def test_no_scientific_algorithms_in_the_api() -> None:
    """R3 no implementa ET0, Pef, balance hídrico, ranking, cohortes ni VoI (spec R3 §2.3)."""
    banned = (
        "penman",
        "monteith",
        "et0_fao",
        "def effective_precip",
        "def compute_et0",
        "kc_curve",
        "def water_balance",
        "dirichlet(",
        "numpy.random",
        "np.random",
        "scipy",
    )
    for f in py_files():
        if (
            "bench" in f.parts
        ):  # el benchmark usa un RNG solo para generar datos sintéticos de CARGA
            continue
        txt = f.read_text(encoding="utf-8").lower()
        for word in banned:
            if word in txt:
                pytest.fail(f"{f.name} parece contener lógica científica: {word}")


def test_no_forbidden_infrastructure_dependencies_in_lock_or_pyproject() -> None:
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    locked = {p["name"].lower() for p in lock["package"]}
    assert not (locked & FORBIDDEN_INFRA), locked & FORBIDDEN_INFRA
    # OpenTelemetry descartado en el MVP: `opentelemetry-api` entra solo como dependencia TRANSITIVA
    # de FastAPI (sin SDK ni exportadores, no instrumenta nada). Cualquier otro paquete otel falla.
    otel = {n for n in locked if n.startswith("opentelemetry")}
    assert otel <= {"opentelemetry-api"}, otel


def test_api_source_does_not_use_observability_stacks() -> None:
    for f in py_files():
        for m in imports_of(f):
            assert not m.startswith(("opentelemetry", "sentry_sdk", "prometheus_client")), (
                f.name,
                m,
            )
    for pj in (ROOT / "pyproject.toml", ROOT / "apps" / "api" / "pyproject.toml"):
        deps = str(tomllib.loads(pj.read_text(encoding="utf-8"))).lower()
        for name in FORBIDDEN_INFRA:
            assert name not in deps, (pj.name, name)


def test_compose_has_exactly_two_services_and_no_forbidden_images() -> None:
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    services_block = text.split("\nservices:\n", 1)[1].split("\nvolumes:\n", 1)[0]
    names = [
        ln.strip().rstrip(":")
        for ln in services_block.splitlines()
        if ln.startswith("  ") and not ln.startswith("    ") and ln.strip().endswith(":")
    ]
    assert names == ["db", "app"]
    for bad in ("redis", "celery", "minio", "rabbit", "kafka"):
        assert bad not in text.lower()


def test_secrets_are_not_committed_in_examples() -> None:
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    for line in env.splitlines():
        if line.startswith(
            ("JWT_SECRET=", "POSTGRES_PASSWORD=", "APP_DB_PASSWORD=", "EARTHDATA_TOKEN=")
        ):
            assert line.split("=", 1)[1].split("#")[0].strip() == "", line
    assert "ENABLE_EXACT_GEOMETRY=false" in env


def test_dockerfile_runs_as_non_root_and_bundles_pango() -> None:
    d = (ROOT / "infra" / "Dockerfile.app").read_text(encoding="utf-8")
    runtime = d.split("AS runtime", 1)[1].split("AS test", 1)[0]
    assert "USER milpa" in runtime and "libpango-1.0-0" in d
    assert "JWT_SECRET" not in d and "PASSWORD" not in d  # sin secretos en capas
