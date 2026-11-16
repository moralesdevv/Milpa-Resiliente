"""Unitarias: ObjectStore, Parquet, hashes/reproducibilidad, CSV de suelo."""

from __future__ import annotations

import contextlib
import os
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from api.reproducibility.hashing import (
    MissingInputError,
    canonical_hash,
    canonical_json,
    data_hash,
    is_sha256,
    logical_dataframe_hash,
    sha256_bytes,
    sha256_file,
)
from api.soil_csv import CsvValidationFailed, PropertySpec, accepted_by_property, parse_soil_csv
from api.storage.object_store import LocalObjectStore, StorageObjectExists, StoragePathError
from api.storage.parquet import (
    COVERAGE_CONTRACT,
    DatasetIncompatible,
    DatasetIntegrityError,
    DatasetUnavailable,
    ParquetDatasetReader,
    curated_path,
    write_parquet_deterministic,
)


# ----------------------------------------------------------------------- hashes
def test_sha256_known_vectors(tmp_path: Path) -> None:
    assert sha256_bytes(b"") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    f = tmp_path / "a.bin"
    f.write_bytes(b"abc")
    assert sha256_file(f) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    with pytest.raises(MissingInputError, match=r"nope\.bin"):
        sha256_file(tmp_path / "nope.bin")


@given(
    st.dictionaries(
        st.text(max_size=8),
        st.one_of(st.integers(), st.text(max_size=8), st.booleans(), st.none()),
        max_size=6,
    )
)
def test_canonical_hash_ignores_key_order(d: dict[str, object]) -> None:
    shuffled = dict(reversed(list(d.items())))
    assert canonical_hash(d) == canonical_hash(shuffled)
    assert canonical_json(d) == canonical_json(shuffled)


def test_canonical_hash_changes_with_params_and_rejects_nan() -> None:
    assert canonical_hash({"peff": "a", "seed": 1}) != canonical_hash({"peff": "a", "seed": 2})
    with pytest.raises(ValueError):
        canonical_json({"x": float("nan")})


@given(st.permutations(list(range(8))))
@settings(max_examples=30, deadline=None)
def test_logical_hash_is_independent_of_physical_row_and_column_order(perm: list[int]) -> None:
    df = pd.DataFrame(
        {"k": list(range(8)), "v": [i * 2.5 for i in range(8)], "s": list("abcdefgh")}
    )
    other = df.iloc[perm][["s", "v", "k"]].reset_index(drop=True)
    assert logical_dataframe_hash(df, ["k"]) == logical_dataframe_hash(other, ["k"])


def test_logical_hash_detects_change_and_distinguishes_null_from_zero() -> None:
    a = pd.DataFrame({"k": [1, 2], "v": [0.0, 1.0]})
    b = pd.DataFrame({"k": [1, 2], "v": [float("nan"), 1.0]})
    assert logical_dataframe_hash(a, ["k"]) != logical_dataframe_hash(b, ["k"])  # faltante != 0
    with pytest.raises(ValueError, match="clave"):
        logical_dataframe_hash(a, ["z"])


def test_data_hash_is_order_independent_and_validates() -> None:
    r1, r2, cur = "1" * 64, "2" * 64, "3" * 64
    assert data_hash([r1, r2], cur) == data_hash([r2, r1], cur)
    assert data_hash([r1], cur) != data_hash([r1, r2], cur)
    assert is_sha256(r1) and not is_sha256("xyz")
    with pytest.raises(ValueError):
        data_hash(["no-hash"], cur)


# ----------------------------------------------------------------------- ObjectStore
def test_store_blocks_traversal_absolute_and_odd_segments(tmp_path: Path) -> None:
    store = LocalObjectStore(tmp_path / "data")
    for bad in [
        "../x",
        "a/../../x",
        "/etc/passwd",
        "C:\\Windows\\x",
        "a//b",
        "./a",
        "",
        "a\x00b",
        "..",
        "a/.",
        ".hidden/x",
        "a b/c",
    ]:
        with pytest.raises(StoragePathError):
            store.resolve(bad)
    assert store.resolve("curated/zona-1/daily.parquet").is_relative_to(store.root)


@given(st.text(max_size=40))
@settings(max_examples=150, deadline=None)
def test_store_resolve_never_escapes_root(rel: str) -> None:
    store = LocalObjectStore(Path(os.environ.get("TMPDIR", "/tmp")) / "milpa-prop-store")  # noqa: S108
    try:
        resolved = store.resolve(rel)
    except StoragePathError:
        return
    assert resolved.is_relative_to(store.root)


def test_store_blocks_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secreto")
    store = LocalObjectStore(tmp_path / "data")
    try:
        os.symlink(outside, store.root / "link", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks no permitidos en este entorno")
    with pytest.raises(StoragePathError):
        store.resolve("link/secret.txt")


def test_store_write_is_atomic_no_overwrite_and_hash(tmp_path: Path) -> None:
    store = LocalObjectStore(tmp_path)
    digest = store.write_bytes("results/r1/BASE/none/x.bin", b"hola")
    assert digest == sha256_bytes(b"hola") == store.sha256("results/r1/BASE/none/x.bin")
    with pytest.raises(StorageObjectExists):
        store.write_bytes("results/r1/BASE/none/x.bin", b"otro")  # nunca sobrescribe resultados
    assert store.write_bytes("results/r1/BASE/none/x.bin", b"otro", overwrite=True) == sha256_bytes(
        b"otro"
    )
    assert not list(store.root.rglob(".tmp-*"))  # sin temporales residuales
    assert store.delete("results/r1/BASE/none/x.bin") and not store.delete(
        "results/r1/BASE/none/x.bin"
    )
    store.write_bytes("results/r2/a.bin", b"1")
    assert store.delete_tree("results/r2") and not store.delete_tree("results/r2")


# ----------------------------------------------------------------------- Parquet (datos SINTÉTICOS de prueba)
def cov_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "cell_id": [1, 1],
            "variable": ["precip_mm", "tmax_c"],
            "year": [2001, 2001],
            "n_expected": [365, 365],
            "n_valid": [360, 365],
            "pct_missing": [1.4, 0.0],
        }
    )


def test_parquet_reader_errors_are_typed_and_do_not_leak_paths(tmp_path: Path) -> None:
    store = LocalObjectStore(tmp_path)
    reader = ParquetDatasetReader(store)
    rel = curated_path("zona-a", "coverage")
    with pytest.raises(DatasetUnavailable) as e:
        reader.read(rel, COVERAGE_CONTRACT)
    assert str(tmp_path) not in e.value.detail
    p = store.resolve(rel)
    p.parent.mkdir(parents=True)
    p.write_bytes(b"basura")
    with pytest.raises(DatasetIncompatible):
        reader.read(rel, COVERAGE_CONTRACT)
    cov_df().drop(columns=["n_valid"]).to_parquet(p)
    with pytest.raises(DatasetIncompatible, match="n_valid"):
        reader.read(rel, COVERAGE_CONTRACT)
    cov_df().to_parquet(p)
    assert len(reader.read(rel, COVERAGE_CONTRACT)) == 2
    assert list(reader.read(rel, COVERAGE_CONTRACT, columns=["year"]).columns) == ["year"]
    with pytest.raises(DatasetIncompatible):
        reader.read(rel, COVERAGE_CONTRACT, columns=["inventada"])  # no se infieren columnas


def test_parquet_hash_verification_and_size_cap(tmp_path: Path) -> None:
    store = LocalObjectStore(tmp_path)
    rel = curated_path("zona-a", "coverage")
    p = store.resolve(rel)
    p.parent.mkdir(parents=True)
    cov_df().to_parquet(p)
    good = store.sha256(rel)
    reader = ParquetDatasetReader(store)
    assert len(reader.read(rel, COVERAGE_CONTRACT, expected_sha256=good)) == 2
    with pytest.raises(DatasetIntegrityError):
        reader.read(rel, COVERAGE_CONTRACT, expected_sha256="0" * 64)
    with pytest.raises(DatasetIncompatible, match="tamaño"):
        ParquetDatasetReader(store, max_bytes=10).read(rel, COVERAGE_CONTRACT)
    with pytest.raises(DatasetUnavailable):
        reader.read("../fuera.parquet", COVERAGE_CONTRACT)


def test_curated_path_rejects_unsafe_zone_ids() -> None:
    for bad in ["../x", "a/b", "", "a b", "x" * 100]:
        with pytest.raises(StoragePathError):
            curated_path(bad, "daily")
    assert curated_path("pilot_zone-1", "dekad") == "curated/pilot_zone-1/dekad.parquet"


def test_deterministic_parquet_writer_same_bytes_and_no_overwrite(tmp_path: Path) -> None:
    store = LocalObjectStore(tmp_path)
    a = pd.DataFrame({"k": [3, 1, 2], "v": [0.3, 0.1, 0.2]})
    b = a.iloc[[2, 0, 1]][["v", "k"]]  # mismo contenido lógico, distinto orden físico
    h1 = write_parquet_deterministic(store, "results/r/BASE/none/c.parquet", a, ["k"])
    h2 = write_parquet_deterministic(store, "results/r2/BASE/none/c.parquet", b, ["k"])
    assert h1 == h2
    with pytest.raises(StorageObjectExists):
        write_parquet_deterministic(store, "results/r/BASE/none/c.parquet", a, ["k"])


# ----------------------------------------------------------------------- CSV de suelo
CAT = {
    "ph": PropertySpec("ph", "pH", 3.0, 10.0, ("water_1_2_5",)),
    "organic_matter": PropertySpec("organic_matter", "%", 0.0, 100.0, ("walkley_black",)),
    "sand": PropertySpec("sand", "%", 0.0, 100.0, ("hidrometro",)),
    "silt": PropertySpec("silt", "%", 0.0, 100.0, ("hidrometro",)),
    "clay": PropertySpec("clay", "%", 0.0, 100.0, ("hidrometro",)),
    "effective_depth": PropertySpec("effective_depth", "cm", 0.0, 1000.0, ("declarado/medido",)),
}
# Columnas del formato de la especificación (apartado 9); las no usadas se omiten
HDR = "parcel_code,sample_date,depth_from_cm,depth_to_cm,ph,ph_method,om_pct,om_method\n"
TEX = (
    "parcel_code,sample_date,depth_from_cm,depth_to_cm,sand_pct,silt_pct,clay_pct,texture_method,"
    "effective_root_depth_cm\n"
)
CODE = "P-001"
TODAY = date(2026, 11, 14)


def parse(csv: str | bytes, code: str | None = CODE) -> list:  # type: ignore[type-arg]
    raw = csv.encode() if isinstance(csv, str) else csv
    return parse_soil_csv(raw, CAT, today=TODAY, parcel_code=code)


def test_csv_empty_value_means_no_measurement_never_zero() -> None:
    rows = parse(HDR + "P-001,2025-03-01,0,20,6.2,water_1_2_5,,\n")
    assert [m.code for m in rows[0].measurements] == ["ph"]  # materia orgánica: sin fila (no 0)
    assert accepted_by_property(rows) == {"ph": 1}
    both = parse(
        HDR
        + "P-001,2025-03-01,0,20,6.2,water_1_2_5,2.1,walkley_black\n"
        + "P-001,2025-03-02,0,20,,,3.0,walkley_black\n"
    )
    assert accepted_by_property(both) == {"ph": 1, "organic_matter": 2}
    assert all(m.value != 0 for r in both for m in r.measurements)
    assert {r.representativeness for r in both} == {"parcela"}  # derivada del parcel_code


def test_csv_spec_example_row_is_accepted() -> None:
    """La fila de ejemplo de la especificación (apartado 9), con su encabezado completo."""
    spec = (
        "parcel_code,sample_date,depth_from_cm,depth_to_cm,lab,ph,ph_method,om_pct,om_method,"
        "sand_pct,silt_pct,clay_pct,texture_method,cec_cmol_kg,cec_method,"
        "effective_root_depth_cm,awc_mm_per_m,awc_method\n"
        "P-014,2025-03-12,0,20,Laboratorio X,5.8,water_1_2_5,,,42,31,27,hidrometro,,,60,,\n"
    )
    rows = parse_soil_csv(spec.encode(), CAT, today=TODAY, parcel_code="P-014")
    assert accepted_by_property(rows) == {
        "ph": 1,
        "sand": 1,
        "silt": 1,
        "clay": 1,
        "effective_depth": 1,
    }
    assert rows[0].lab == "Laboratorio X"
    assert {m.method for m in rows[0].measurements if m.code == "effective_depth"} == {
        "declarado/medido"
    }


def test_csv_accepts_bom_crlf_and_blank_lines() -> None:
    rows = parse(("﻿" + HDR + "P-001,2025-03-01,0,20,6.2,water_1_2_5,,\r\n\r\n").encode("utf-8"))
    assert len(rows) == 1 and rows[0].sampled_at == date(2025, 3, 1)


@pytest.mark.parametrize(
    "bad,code",
    [
        (HDR + "P-001,2025-03-01,0,20,2.0,water_1_2_5,,\n", "out_of_range"),
        (HDR + "P-001,2025-03-01,0,20,nan,water_1_2_5,,\n", "not_finite"),
        (HDR + "P-001,2025-03-01,0,20,inf,water_1_2_5,,\n", "not_finite"),
        (HDR + "P-001,2025-03-01,0,20,6,otro_metodo,,\n", "method_not_accepted"),
        (HDR + "P-001,2025-03-01,0,20,6,,,\n", "method_not_accepted"),  # valor sin método
        (HDR + "P-001,2025-03-01,0,20,,metodo_sin_valor,,\n", "method_without_value"),
        (HDR + "P-001,2025-03-01,0,20,,,,\n", "no_measurements"),
        (HDR + "P-001,2027-03-01,0,20,6,water_1_2_5,,\n", "future_date"),
        (HDR + "P-001,2025-02-30,0,20,6,water_1_2_5,,\n", "invalid_date"),
        (HDR + "P-001,01/03/2025,0,20,6,water_1_2_5,,\n", "invalid_value"),
        (HDR + "P-001,2025-03-01,20,20,6,water_1_2_5,,\n", "depth_order"),
        (HDR + "P-002,2025-03-01,0,20,6,water_1_2_5,,\n", "parcel_mismatch"),
        (HDR + ",2025-03-01,0,20,6,water_1_2_5,,\n", "invalid_value"),  # parcel_code vacío
        (HDR + 'P-001,2025-03-01,0,20,"6,5",water_1_2_5,,\n', "not_numeric"),  # coma decimal
        (HDR + "P-001,2025-03-01,0,20,6,water_1_2_5\n", "column_count"),
        (HDR + "P-001,2025-03-01,0,20,6,water_1_2_5,,," + "x\n", "column_count"),
        (HDR + "P-001,2025-03-01,0,20," + "9" * 300 + ",water_1_2_5,,\n", "cell_too_long"),
    ],
)
def test_csv_row_errors(bad: str, code: str) -> None:
    with pytest.raises(CsvValidationFailed) as e:
        parse(bad)
    assert code in {x["code"] for x in e.value.errors}
    assert e.value.status == 422 and str(e.value.code) == "CSV_VALIDATION_FAILED"


@pytest.mark.parametrize("lead", ["=", "+", "-", "@", "\t="])  # el espacio inicial se recorta
def test_csv_rejects_spreadsheet_formula_injection_in_text_columns(lead: str) -> None:
    csv_text = (
        "parcel_code,sample_date,depth_from_cm,depth_to_cm,lab,ph,ph_method\n"
        f'P-001,2025-03-01,0,20,"{lead}HYPERLINK(1)",6,water_1_2_5\n'
    )
    with pytest.raises(CsvValidationFailed) as e:
        parse(csv_text)
    assert "formula_injection" in {x["code"] for x in e.value.errors}
    assert "HYPERLINK" not in repr(e.value.errors)


@pytest.mark.parametrize(
    "row,code",
    [
        ("P-001,2025-03-01,0,20,42,31,,hidrometro,\n", "texture_incomplete"),
        ("P-001,2025-03-01,0,20,50,30,30,hidrometro,\n", "texture_sum"),
        ("P-001,2025-03-01,0,20,45,35,-5,hidrometro,\n", "out_of_range"),
        ("P-001,2025-03-01,0,20,42,31,27,,\n", "method_not_accepted"),
        ("P-001,2025-03-01,0,20,,,,hidrometro,\n", "method_without_value"),
    ],
)
def test_csv_texture_rules_from_spec(row: str, code: str) -> None:
    with pytest.raises(CsvValidationFailed) as e:
        parse(TEX + row)
    assert code in {x["code"] for x in e.value.errors}


def test_csv_texture_sum_tolerance_is_plus_minus_two() -> None:
    ok = parse(
        TEX
        + "P-001,2025-03-01,0,20,42,31,27,hidrometro,\n"
        + "P-001,2025-03-02,0,20,42,31,28.9,hidrometro,\n"  # suma 101.9
        + "P-001,2025-03-03,0,20,42,31,25,hidrometro,\n"  # suma 98: límite inferior incluido
    )
    assert accepted_by_property(ok) == {"sand": 3, "silt": 3, "clay": 3}
    for bad in ("24.9", "29.1"):  # suma 97.9 y 102.1: fuera de 100 ± 2
        with pytest.raises(CsvValidationFailed) as e:
            parse(TEX + f"P-001,2025-03-01,0,20,42,31,{bad},hidrometro,\n")
        assert "texture_sum" in {x["code"] for x in e.value.errors}


def test_csv_target_parcel_without_code_is_rejected_not_guessed() -> None:
    with pytest.raises(CsvValidationFailed) as e:
        parse(HDR + "P-001,2025-03-01,0,20,6,water_1_2_5,,\n", code=None)
    assert "target_parcel_without_code" in {x["code"] for x in e.value.errors}


def test_csv_property_value_for_property_missing_in_catalog_is_rejected() -> None:
    with pytest.raises(CsvValidationFailed) as e:
        parse(
            "parcel_code,sample_date,depth_from_cm,depth_to_cm,cec_cmol_kg,cec_method\n"
            "P-001,2025-03-01,0,20,15,acetato_amonio\n"
        )
    assert "property_not_in_catalog" in {x["code"] for x in e.value.errors}


@pytest.mark.parametrize(
    "raw,code",
    [
        (b"", "empty"),
        (b"\n\n", "empty"),
        ("a,b\n1,2\n", "missing_column"),
        (HDR.replace("ph,", "ph,ph,", 1) + "", "duplicate_column"),
        (
            HDR.replace("ph_method", "metodo_x") + "P-001,2025-03-01,0,20,6,w,,\n",
            "unknown_column",
        ),
        (
            # formato antiguo propio de R3 (no es el de la especificación): se rechaza
            "sampled_at,depth_from_cm,depth_to_cm,representativeness,ph,ph_method\n"
            "2025-03-01,0,20,parcela,6,water_1_2_5\n",
            "unknown_column",
        ),
        (
            "parcel_code,sample_date,depth_from_cm,depth_to_cm\nP-001,2025-03-01,0,20\n",
            "no_property",
        ),
        ("a".encode("utf-16"), "encoding"),
        (b"\x00\x01", "encoding"),
    ],
)
def test_csv_structure_errors(raw: str | bytes, code: str) -> None:
    with pytest.raises(CsvValidationFailed) as e:
        parse(raw)
    assert code in {x["code"] for x in e.value.errors}


def test_csv_limits_rows_and_columns() -> None:
    many = HDR + "P-001,2025-03-01,0,20,6,water_1_2_5,,\n" * 6
    with pytest.raises(CsvValidationFailed) as e:
        parse_soil_csv(many.encode(), CAT, today=TODAY, parcel_code=CODE, max_rows=5)
    assert "too_many_rows" in {x["code"] for x in e.value.errors}
    wide = ",".join(f"c{i}" for i in range(100)) + "\n" + ",".join("1" for _ in range(100)) + "\n"
    with pytest.raises(CsvValidationFailed) as e2:
        parse(wide)
    assert "too_many_columns" in {x["code"] for x in e2.value.errors}


def test_csv_error_messages_never_echo_cell_values() -> None:
    secret = "VALOR-PRIVADO-123"
    with pytest.raises(CsvValidationFailed) as e:
        parse(HDR + f"P-001,2025-03-01,0,20,{secret},water_1_2_5,,\n")
    assert secret not in repr(e.value.errors)
    with pytest.raises(CsvValidationFailed) as e2:
        parse(HDR + f"{secret},2025-03-01,0,20,6,water_1_2_5,,\n")
    assert secret not in repr(e2.value.errors)  # parcel_mismatch no repite el código recibido


@given(vals=st.lists(st.floats(3.0, 10.0, allow_nan=False), min_size=1, max_size=20))
@settings(max_examples=40, deadline=None)
def test_csv_valid_rows_are_all_accepted_and_counted(vals: list[float]) -> None:
    body = "".join(
        f"P-001,2025-03-{(i % 28) + 1:02d},0,20,{v:.3f},water_1_2_5,,\n" for i, v in enumerate(vals)
    )
    rows = parse(HDR + body)
    assert len(rows) == len(vals) and accepted_by_property(rows) == {"ph": len(vals)}


@given(junk=st.binary(max_size=300))
@settings(max_examples=120, deadline=None)
def test_csv_arbitrary_bytes_never_crash(junk: bytes) -> None:
    with contextlib.suppress(CsvValidationFailed):  # rechazo controlado: nunca otra excepción
        parse(junk)
