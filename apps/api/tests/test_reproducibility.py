"""BE-10: identificadores de corrida, manifiestos y prerrequisitos de `make reproduce`."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from api import cli
from api.reproducibility.hashing import MissingInputError, sha256_bytes
from api.reproducibility.runs import (
    EXIT_MISSING_INPUTS,
    EXIT_WAITING_DEPENDENCY,
    MANIFEST_FORMAT,
    RunIdentifiers,
    build_manifest,
    check_reproduce_prerequisites,
    load_manifest,
    verify_manifest,
)

H = [c * 64 for c in "abcdef"]


def ids(**over: object) -> RunIdentifiers:
    base: dict[str, object] = {
        "code_version": "git:abc1234+core:0.1",
        "region_config_hash": H[0],
        "catalog_hash": H[1],
        "data_hash": H[2],
        "params_hash": H[3],
        "seed": 42,
    }
    base.update(over)
    return RunIdentifiers.model_validate(base)


def test_run_identifiers_validate_format() -> None:
    assert ids().seed == 42
    for bad in (
        {"data_hash": "xyz"},
        {"seed": -1},
        {"code_version": ""},
        {"params_hash": "A" * 64},
    ):
        with pytest.raises(ValidationError):
            ids(**bad)
    with pytest.raises(ValidationError):
        RunIdentifiers.model_validate({**ids().model_dump(), "extra": 1})


def test_diff_detects_exactly_the_changed_identifiers() -> None:
    a = ids()
    assert a.diff(ids()) == []
    assert a.diff(ids(data_hash=H[4], seed=7)) == ["data_hash", "seed"]


@given(seed=st.integers(0, 2**63 - 1), h=st.sampled_from(H))
def test_identifiers_roundtrip_json(seed: int, h: str) -> None:
    a = ids(seed=seed, data_hash=h)
    assert RunIdentifiers.model_validate_json(a.model_dump_json()) == a


def test_manifest_build_and_verify_detects_missing_changed_and_traversal(tmp_path: Path) -> None:
    (tmp_path / "curated").mkdir()
    (tmp_path / "curated" / "a.bin").write_bytes(b"uno")
    (tmp_path / "curated" / "b.bin").write_bytes(b"dos")
    manifest = build_manifest(tmp_path, ["curated/b.bin", "curated/a.bin"])
    assert [e["path"] for e in manifest["files"]] == [
        "curated/a.bin",
        "curated/b.bin",
    ]  # orden determinista
    assert manifest["files"][0]["sha256"] == sha256_bytes(b"uno")
    assert build_manifest(tmp_path, ["curated/a.bin", "curated/b.bin"]) == manifest  # reproducible
    assert verify_manifest(manifest, tmp_path).ok

    (tmp_path / "curated" / "b.bin").write_bytes(b"CAMBIADO")
    (tmp_path / "curated" / "a.bin").unlink()
    rep = verify_manifest(manifest, tmp_path)
    assert not rep.ok and rep.missing == ["curated/a.bin"] and rep.mismatched == ["curated/b.bin"]

    evil = {"format": MANIFEST_FORMAT, "files": [{"path": "../fuera.txt", "sha256": H[0]}]}
    assert not verify_manifest(evil, tmp_path).ok
    assert not verify_manifest({"format": "otro", "files": []}, tmp_path).ok
    bad_hash = {
        "format": MANIFEST_FORMAT,
        "files": [{"path": "curated/b.bin", "sha256": "no-hash"}],
    }
    assert not verify_manifest(bad_hash, tmp_path).ok


def test_build_manifest_fails_with_exact_missing_input(tmp_path: Path) -> None:
    with pytest.raises(MissingInputError, match=r"falta\.parquet"):
        build_manifest(tmp_path, ["falta.parquet"])  # no se calculan hashes de datos que no existen


def test_load_manifest(tmp_path: Path) -> None:
    with pytest.raises(MissingInputError):
        load_manifest(tmp_path / "nope.json")
    p = tmp_path / "m.json"
    p.write_text(json.dumps({"format": MANIFEST_FORMAT, "files": []}), encoding="utf-8")
    assert load_manifest(p)["files"] == []


def test_reproduce_reports_exactly_what_is_missing_and_never_succeeds(tmp_path: Path) -> None:
    st_ = check_reproduce_prerequisites(tmp_path)
    assert st_.exit_code == EXIT_MISSING_INPUTS != 0
    joined = " | ".join(st_.missing)
    assert "demo" in joined and "R1" in joined
    assert "milpa_core" not in joined  # R2 está integrado: ya no figura como faltante
    (tmp_path / "demo").mkdir()
    assert any("EXPECTED.json" in m for m in check_reproduce_prerequisites(tmp_path).missing)


def test_cli_reproduce_exits_nonzero_and_does_not_claim_success(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = cli.main(["reproduce", "--data-dir", str(tmp_path)])
    err = capsys.readouterr().err
    assert code != 0 and "FALTA" in err and "No se simula éxito" in err


def test_cli_check_core_reports_not_integrated(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "milpa_core", None)  # simula el paquete ausente
    assert cli.main(["check-core"]) == 2
    assert "NO integrado" in capsys.readouterr().out


def test_cli_check_core_accepts_the_installed_package(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["check-core"]) == 0
    assert "OK" in capsys.readouterr().out


def test_cli_verify_manifest_and_hash(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    f = tmp_path / "x.bin"
    f.write_bytes(b"abc")
    assert cli.main(["hash", str(f)]) == 0
    assert capsys.readouterr().out.strip() == sha256_bytes(b"abc")
    m = tmp_path / "m.json"
    m.write_text(json.dumps(build_manifest(tmp_path, ["x.bin"])), encoding="utf-8")
    assert cli.main(["verify-manifest", str(m), "--base", str(tmp_path)]) == 0
    f.write_bytes(b"alterado")
    assert cli.main(["verify-manifest", str(m), "--base", str(tmp_path)]) == 2
    assert "HASH DISTINTO" in capsys.readouterr().err
    assert cli.main(["verify-manifest", str(tmp_path / "no.json")]) == 2


def test_cli_report_sample_input_is_synthetic_and_marked() -> None:
    data = cli.sample_report_input("public", "es+en")
    assert "sintética" in data.zone_name and data.provisional_banner is True
    assert data.hashes.seed == 0 and set(data.hashes.data_hash) == {"0"}


def test_cli_password_is_never_an_argument() -> None:
    parser = cli.build_parser()
    action = next(
        a for a in parser._subparsers._group_actions[0].choices["create-user"]._actions if a.dest
    )
    options = {a.dest for a in parser._subparsers._group_actions[0].choices["create-user"]._actions}
    assert "password" not in options and action is not None


# ------------------------------------------------ capa de datos con el paquete demo de R1 (real)
REPO_DEMO = Path(__file__).resolve().parents[3] / "data" / "demo"


def test_frozen_demo_package_matches_its_expected_json() -> None:
    from api.reproducibility.runs import verify_demo_package

    if not REPO_DEMO.is_dir():
        pytest.skip("data/demo no existe: generar con `milpa-etl build-demo`")
    problems, verified, expected = verify_demo_package(REPO_DEMO)
    assert problems == [] and expected is not None
    assert len(verified) == len(expected["files_sha256"]) == 4
    assert expected["label"] == "datos sintéticos"


def test_tampered_frozen_file_is_detected(tmp_path: Path) -> None:
    import shutil

    from api.reproducibility.runs import verify_demo_package

    if not REPO_DEMO.is_dir():
        pytest.skip("data/demo no existe")
    demo = tmp_path / "demo"
    shutil.copytree(REPO_DEMO, demo)
    victim = demo / "zona_sintetica" / "daily.parquet"
    victim.write_bytes(victim.read_bytes() + b"x")
    problems, _, _ = verify_demo_package(demo)
    assert any("hash distinto" in p and "daily.parquet" in p for p in problems)
    (demo / "zona_sintetica" / "dekad.parquet").unlink()
    assert any("falta el archivo congelado" in p for p in verify_demo_package(demo)[0])


def test_malformed_expected_json_is_reported(tmp_path: Path) -> None:
    from api.reproducibility.runs import verify_demo_package

    (tmp_path / "EXPECTED.json").write_text("{no es json", encoding="utf-8")
    assert "ilegible" in verify_demo_package(tmp_path)[0][0]
    (tmp_path / "EXPECTED.json").write_text('{"zone": "z"}', encoding="utf-8")
    assert "claves" in verify_demo_package(tmp_path)[0][0]


def test_reproduce_regenerates_the_data_layer_and_still_refuses_to_claim_success() -> None:
    """Con R1 presente la capa de datos se verifica y se regenera; sin R2 el código es 3, nunca 0."""
    pytest.importorskip("milpa_etl")
    if not REPO_DEMO.is_dir():
        pytest.skip("data/demo no existe")
    st_ = check_reproduce_prerequisites(REPO_DEMO.parent)
    assert any("regenerad" in v for v in st_.verified)
    assert (
        st_.exit_code == EXIT_WAITING_DEPENDENCY != 0
    )  # recomputo vs EXPECTED.json aún no contratado


# ------------------------------------------- tolerancia numérica entre plataformas (README §25)
def test_numeric_tolerance_accepts_last_bit_noise_and_rejects_real_differences() -> None:
    import numpy as np
    import pandas as pd

    from api.reproducibility.runs import frames_equal_within_tolerance

    base = pd.DataFrame({"x": [1.0, 2.5, np.nan], "year": [2001, 2002, 2003], "s": ["a", "b", "c"]})
    noisy = base.copy()
    noisy["x"] = [1.0 * (1 + 4e-16), 2.5 * (1 - 2e-16), np.nan]
    ok, worst, _ = frames_equal_within_tolerance(base, noisy)
    assert ok and 0 < worst < 1e-15
    off = base.copy()
    off["x"] = [1.0 + 1e-6, 2.5, np.nan]
    assert frames_equal_within_tolerance(base, off)[0] is False  # diferencia real
    nan_moved = base.copy()
    nan_moved["x"] = [np.nan, 2.5, 3.0]
    assert "NaN" in frames_equal_within_tolerance(base, nan_moved)[2]
    text = base.copy()
    text["s"] = ["a", "b", "z"]
    assert frames_equal_within_tolerance(base, text)[0] is False  # no numéricos: exactos
    assert frames_equal_within_tolerance(base, base.drop(columns=["s"]))[0] is False
    ints = base.copy()
    ints["year"] = [2001, 2002, 2004]
    assert frames_equal_within_tolerance(base, ints)[0] is False  # enteros: exactos
