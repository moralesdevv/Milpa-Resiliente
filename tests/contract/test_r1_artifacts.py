"""Compatibilidad de R3 con los artefactos REALES entregados por R1 (``references/``).

No usa datos inventados: lee los archivos de R1 tal como están. Si ``references/`` no existe en el
árbol, las pruebas se omiten con motivo (omitida ≠ aprobada). Los defectos conocidos del lado de R1 se
marcan ``xfail(strict=True)``: se ejecutan, documentan el hallazgo, y fallarán en voz alta cuando R1
los corrija (para retirar la marca). Detalle: ``docs/auditoria/matriz_compatibilidad.md``.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pyarrow.parquet as pq
import pytest
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.engine import make_url

from api.db.invariants import security_violations
from api.errors import ApiError
from api.soil_csv import CsvValidationFailed, PropertySpec, parse_soil_csv
from api.storage.object_store import LocalObjectStore
from api.storage.parquet import (
    COVERAGE_CONTRACT,
    DAILY_CONTRACT,
    DEKAD_CONTRACT,
    ParquetDatasetReader,
    curated_path,
)
from testkit import ADMIN_URL, ROOT, TestDb

R1 = ROOT / "references" / "Milpa-Resiliente-R1"
ZONE = "chiquimula_prueba"
pytestmark = pytest.mark.skipif(
    not R1.is_dir(), reason="references/Milpa-Resiliente-R1 no está en este árbol"
)

# Orden CORREGIDO: los archivos de R1 no se pueden aplicar en el orden de su nombre
# (03_ref.sql referencia geo.region, que crea 04_geo.sql).
R1_DDL_ORDER = (
    "000_init",
    "01_auth",
    "02_prov",
    "04_geo",
    "03_ref",
    "05_farm",
    "06_private",
    "07_soil",
    "08_econ",
    "09_engine",
    "10_report",
)
SCHEMAS = ("auth", "prov", "ref", "geo", "farm", "private", "soil", "econ", "engine", "report")


def _sql(name: str) -> str:
    return (R1 / "sql" / f"{name}.sql").read_text(encoding="utf-8")


def _run(conn: Connection, name: str) -> None:
    """Ejecuta un script de R1 TAL CUAL salvo BEGIN/COMMIT (la prueba controla la transacción) y
    el escape de ``%`` que exige el driver."""
    sql = re.sub(r"^\s*(BEGIN|COMMIT)\s*;\s*$", "", _sql(name), flags=re.MULTILINE)
    conn.exec_driver_sql(sql.replace("%", "%%"))


# ======================================================================== CSV de suelo
def _r1_soil_catalog() -> dict[str, PropertySpec]:
    """Catálogo ``ref.soil_property`` tal como lo siembra R1 (91_seed_soil.sql)."""
    rows = re.findall(
        r"\('(\w+)',\s*'([^']+)',\s*(\d+),\s*(\d+),\s*ARRAY\[([^\]]+)\]", _sql("91_seed_soil")
    )
    assert len(rows) == 8
    return {
        code: PropertySpec(
            code, unit, float(lo), float(hi), tuple(re.findall(r"'([^']+)'", methods))
        )
        for code, unit, lo, hi, methods in rows
    }


TODAY = date(2026, 11, 15)


def _parse(name: str, parcel: str = "P-014") -> list:  # type: ignore[type-arg]
    return parse_soil_csv(
        (R1 / name).read_bytes(), _r1_soil_catalog(), today=TODAY, parcel_code=parcel
    )


@pytest.mark.parametrize(("name", "rows"), [("suelo.csv", 1), ("suelo_prueba.csv", 6)])
def test_r1_valid_soil_csv_files_are_accepted(name: str, rows: int) -> None:
    assert len(_parse(name)) == rows


def test_r1_valid_csv_blank_cells_are_not_measured_never_zero() -> None:
    row = _parse("suelo.csv")[0]  # om/cec/awc vacíos en el ejemplo de la especificación
    assert {m.code for m in row.measurements} == {"ph", "sand", "silt", "clay", "effective_depth"}
    assert all(m.value != 0 for m in row.measurements)


def test_r1_invalid_soil_csv_each_defect_gets_its_specific_error() -> None:
    """Cada fila de ``suelo_invalido_p014.csv`` es un defecto distinto y deliberado de R1."""
    with pytest.raises(CsvValidationFailed) as e:
        _parse("suelo_invalido_p014.csv")
    got = {(x["loc"][1], x["code"]) for x in e.value.errors}
    assert got == {
        (1, "out_of_range"),  # pH 11.2
        (2, "method_not_accepted"),  # pH sin método
        (3, "texture_sum"),  # 50+30+30
        (4, "future_date"),  # 2099-01-01
        (5, "depth_order"),  # 20 → 10
        (6, "not_numeric"),  # "6,5" (coma decimal)
        (7, "out_of_range"),  # arcilla -5
        (8, "invalid_value"),  # parcel_code vacío
        (9, "formula_injection"),  # =HYPERLINK(...) en lab
    }
    assert "HYPERLINK" not in repr(e.value.errors) and "ejemplo.invalido" not in repr(
        e.value.errors
    )


def test_r1_csv_for_another_parcel_is_not_attached_to_the_target() -> None:
    with pytest.raises(CsvValidationFailed) as e:
        _parse("suelo.csv", parcel="P-999")
    assert {x["code"] for x in e.value.errors} == {"parcel_mismatch"}


# ============================================================================== Parquet
def _reader() -> ParquetDatasetReader:
    return ParquetDatasetReader(LocalObjectStore(R1 / "data"))


def _cols(name: str) -> dict[str, str]:
    pf = pq.ParquetFile(R1 / "data" / curated_path(ZONE, name))  # type: ignore[arg-type]
    return {f.name: str(f.type) for f in pf.schema_arrow}


def test_r1_curated_layout_matches_the_documented_path() -> None:
    """``data/curated/<zona>/{daily,dekad,coverage}.parquet`` (README §9) existe y es legible."""
    for name in ("daily", "dekad", "coverage"):
        assert (R1 / "data" / curated_path(ZONE, name)).is_file()  # type: ignore[arg-type]


def test_r1_parquet_actual_columns_snapshot() -> None:
    """Foto de lo que R1 entregó realmente. Si R1 cambia el esquema, esta prueba lo avisa."""
    daily, dekad, cov = _cols("daily"), _cols("dekad"), _cols("coverage")
    # R1 entrega series ZONALES: el README §13.7 propone clave por celda (ADR-018 registra la diferencia)
    assert "cell_id" not in daily and "cell_id" not in dekad and "cell_id" not in cov
    assert "tmean_c" not in daily
    assert daily["obs_date"].startswith("timestamp")
    assert {"precip_power_mm", "precip_imerg_mm", "precip_source", "ea_method", "et0_mm"} <= set(
        daily
    )
    assert {"year", "dekad", "p_mm", "et0_mm", "n_days", "n_valid_days"} <= set(dekad)
    assert {c for c in dekad if c.startswith("pef_mm_")} == {
        "pef_mm_usda_scs_fao",
        "pef_mm_fao_dependable",
        "pef_mm_upper_bound",
        "pef_mm_fixed_fraction",
    }
    assert set(cov) == {"variable", "year", "n_expected", "n_valid", "pct_missing"}


@pytest.mark.parametrize("name", ["daily", "dekad", "coverage"])
def test_r1_parquet_satisfies_the_zonal_contract_r3_reads(name: str) -> None:
    """ADR-018: R3 lee el Parquet ZONAL que R1 entrega (sin `cell_id`); antes era una incompatibilidad."""
    contract = {"daily": DAILY_CONTRACT, "dekad": DEKAD_CONTRACT, "coverage": COVERAGE_CONTRACT}[
        name
    ]
    df = _reader().read(curated_path(ZONE, name), contract)  # type: ignore[arg-type]
    assert not df.empty and contract.status == "confirmed_by_delivered_files"
    assert len(df) == {"daily": 9131, "dekad": 900, "coverage": 200}[name]


def test_r1_parquet_reader_still_fails_closed_when_a_required_column_is_missing(
    tmp_path: Path,
) -> None:
    """Un archivo que no cumpla el contrato sigue siendo un error tipado, nunca datos mal leídos."""
    import pandas as pd

    rel = curated_path(ZONE, "coverage")
    dest = tmp_path / rel
    dest.parent.mkdir(parents=True)
    df = pd.read_parquet(R1 / "data" / rel)  # type: ignore[arg-type]
    df.drop(columns=["n_valid"]).to_parquet(dest, index=False)
    with pytest.raises(ApiError) as e:
        ParquetDatasetReader(LocalObjectStore(tmp_path)).read(rel, COVERAGE_CONTRACT)  # type: ignore[arg-type]
    assert str(e.value.code) == "DATASET_INCOMPATIBLE" and "n_valid" in str(e.value)


def test_r1_curated_meta_records_hashes_and_limitations() -> None:
    import json

    meta = json.loads((R1 / "data" / "curated" / ZONE / "curated_meta.json").read_text("utf-8"))
    assert re.fullmatch(r"[0-9a-f]{64}", meta["data_hash"])
    assert all(re.fullmatch(r"[0-9a-f]{64}", h) for h in meta["raw_sha256"])
    assert meta["limitations"], "R1 debe declarar las limitaciones de los datos"


# ================================================================================== DDL
def _catalog(conn: Connection) -> set[str]:
    """Catálogo normalizado (columnas, restricciones sin nombre, enums, índices sin PK/UNIQUE)."""
    q = text
    lines: set[str] = set()
    params = {"s": list(SCHEMAS)}
    lines |= set(
        conn.execute(
            q(
                "SELECT 'COL '||table_schema||'.'||table_name||'.'||column_name||' '||udt_name"
                "||coalesce('('||character_maximum_length||')','')"
                "||coalesce('('||numeric_precision||','||numeric_scale||')','')"
                "||' null='||is_nullable||' def='"
                "||coalesce(regexp_replace(column_default,'\\s+',' ','g'),'-') "
                "FROM information_schema.columns WHERE table_schema = ANY(:s) "
                "AND table_name <> 'property_status'"
            ),
            params,
        ).scalars()
    )
    lines |= set(
        conn.execute(
            q(
                "SELECT 'CON '||n.nspname||'.'||c.relname||' '||con.contype::text||' '"
                "||regexp_replace(pg_get_constraintdef(con.oid),'\\s+',' ','g') "
                "FROM pg_constraint con JOIN pg_class c ON c.oid=con.conrelid "
                "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname = ANY(:s)"
            ),
            params,
        ).scalars()
    )
    lines |= set(
        conn.execute(
            q(
                "SELECT 'ENUM '||t.typname||' = '||string_agg(e.enumlabel,',' ORDER BY e.enumsortorder)"
                " FROM pg_type t JOIN pg_enum e ON e.enumtypid=t.oid GROUP BY t.typname"
            )
        ).scalars()
    )
    lines |= set(
        conn.execute(
            q(
                "SELECT 'IDX '||schemaname||'.'||tablename||' '||regexp_replace(indexdef,'\\s+',' ','g')"
                " FROM pg_indexes WHERE schemaname = ANY(:s) AND indexname NOT LIKE '%\\_pkey' "
                "AND indexname NOT LIKE '%\\_key'"
            ),
            params,
        ).scalars()
    )
    return lines


@pytest.fixture(scope="module")
def r1_ddl_engine() -> Iterator[Engine]:
    """Base efímera con el DDL de R1 aplicado (en orden corregido)."""
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as c:
            c.execute(text("SELECT 1"))
    except Exception as exc:
        admin.dispose()
        pytest.skip(f"PostgreSQL/PostGIS de pruebas no disponible ({type(exc).__name__})")
    name = f"r1_ddl_{uuid.uuid4().hex[:10]}"
    with admin.connect() as c:
        c.execute(text(f'CREATE DATABASE "{name}"'))
    eng = create_engine(make_url(ADMIN_URL).set(database=name), isolation_level="AUTOCOMMIT")
    with eng.connect() as c:
        for f in R1_DDL_ORDER:
            _run(c, f)
    yield eng
    eng.dispose()
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    admin.dispose()


def test_r1_ddl_files_cannot_be_applied_in_filename_order() -> None:
    """Hallazgo C-01: `03_ref.sql` usa `geo.region`, creada en `04_geo.sql` (FK hacia adelante)."""
    ref, geo = _sql("03_ref"), _sql("04_geo")
    assert "REFERENCES geo.region" in ref and "CREATE TABLE geo.region" in geo
    assert "CREATE TABLE geo.region" not in _sql("000_init") + _sql("02_prov")


# Diferencias ACEPTADAS «solo en R1» (R3 es más laxo en esos puntos porque sigue la especificación
# §13 literal, o añade valores). Cualquier otra cosa que R1 tenga y R3 no, hace fallar la prueba.
ONLY_R1_EXPECTED = (
    "COL econ.price_record.ip_id uuid null=NO",  # R1 endureció NOT NULL; §13.4 lo deja nullable
    "COL soil.estimate.ip_id uuid null=NO",  # ídem
    "CON engine.job c CHECK ((kind = ANY",  # R3 añade parcel_delete y consent_purge (ADR-007)
    "IDX geo.zone CREATE INDEX zone_geom_idx",  # mismo índice con otro nombre
)


def test_r3_schema_covers_everything_in_the_r1_ddl(r1_ddl_engine: Engine, test_db: TestDb) -> None:
    with r1_ddl_engine.connect() as c1:
        r1 = _catalog(c1)
    r3_engine = create_engine(test_db.admin_url, isolation_level="AUTOCOMMIT")
    try:
        with r3_engine.connect() as c3:
            r3 = _catalog(c3)
    finally:
        r3_engine.dispose()
    only_r1 = sorted(r1 - r3)
    unexpected = [x for x in only_r1 if not any(x.startswith(p) for p in ONLY_R1_EXPECTED)]
    assert not unexpected, f"R1 define algo que el esquema de R3 no tiene: {unexpected}"
    for prefix in ONLY_R1_EXPECTED:  # la lista de excepciones no debe quedarse obsoleta
        assert any(x.startswith(prefix) for x in only_r1), f"excepción obsoleta: {prefix}"


def test_r3_only_adds_and_never_removes_r1_columns(r1_ddl_engine: Engine, test_db: TestDb) -> None:
    with r1_ddl_engine.connect() as c1:
        r1_cols = {x.split(" null=")[0] for x in _catalog(c1) if x.startswith("COL ")}
    r3_engine = create_engine(test_db.admin_url, isolation_level="AUTOCOMMIT")
    try:
        with r3_engine.connect() as c3:
            r3_cols = {x.split(" null=")[0] for x in _catalog(c3) if x.startswith("COL ")}
    finally:
        r3_engine.dispose()
    assert r1_cols <= r3_cols


# ============================================================================== Seeds de R1
@pytest.fixture
def owner_tx(test_db: TestDb) -> Iterator[Connection]:
    """Conexión propietaria dentro de una transacción que SIEMPRE se revierte."""
    eng = create_engine(test_db.admin_url)
    conn = eng.connect()
    tx = conn.begin()
    try:
        yield conn
    finally:
        tx.rollback()
        conn.close()
        eng.dispose()


def test_r1_seed_scripts_load_into_the_r3_schema(owner_tx: Connection) -> None:
    for f in ("90_seed", "91_seed_soil", "93_seed_imerg"):
        _run(owner_tx, f)
    codes = set(owner_tx.execute(text("SELECT code FROM prov.data_source")).scalars())
    assert {"POWER_DAILY", "IMERG_FINAL_V07"} <= codes
    assert owner_tx.execute(text("SELECT count(*) FROM ref.soil_property")).scalar_one() == 8
    assert security_violations(owner_tx) == [] or all(
        "rol de la aplicación" in v for v in security_violations(owner_tx)
    )


def test_security_invariants_hold_on_the_migrated_schema(app_engine: Engine) -> None:
    with app_engine.connect() as c:
        assert security_violations(c) == []


@pytest.mark.xfail(
    strict=True,
    reason="DEFECTO EN R1 (hallazgo S-01, verificado con fuga real): 92_soil_fixture_provenance.sql "
    "recrea soil.property_status SIN `security_invoker`, por lo que evade RLS. R1 debe añadir "
    "`WITH (security_invoker = true)`. Ver docs/auditoria/matriz_compatibilidad.md.",
)
def test_r1_script_92_keeps_the_view_under_rls(owner_tx: Connection) -> None:
    _run(owner_tx, "92_soil_fixture_provenance")
    problems = [v for v in security_violations(owner_tx) if "vista" in v]
    assert problems == []


def test_r1_script_92_is_detected_by_the_startup_guard(owner_tx: Connection) -> None:
    """Si alguien ejecuta el script 92 tal cual, el servicio lo detecta y se niega a arrancar."""
    _run(owner_tx, "92_soil_fixture_provenance")
    assert any("soil.property_status" in v for v in security_violations(owner_tx))
