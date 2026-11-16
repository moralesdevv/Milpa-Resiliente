"""ProcessIngest (R1 como proceso): secuencia de pasos, validación de argumentos y entorno mínimo.

El ejecutor es un DOBLE DE PRUEBA: no se llama a NASA ni se importa ``milpa_etl``.
"""

from __future__ import annotations

import importlib.util
import secrets
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from uuid import uuid4

import pytest

from api.adapters.etl_process import IngestFailed, ProcessIngest, ZoneSpec
from api.errors import ValidationFailed

SPEC = ZoneSpec(
    name="zona_de_prueba",
    lat=14.8,
    lon=-89.5,
    elevation_m=790.15,
    geojson={
        "type": "Polygon",
        "coordinates": [[[-89.6, 14.7], [-89.4, 14.7], [-89.4, 14.9], [-89.6, 14.7]]],
    },
)


class FakeRunner:
    def __init__(self, fail_at: str | None = None, timeout_at: str | None = None) -> None:
        self.calls: list[tuple[list[str], dict[str, str], int]] = []
        self.fail_at, self.timeout_at = fail_at, timeout_at

    def __call__(
        self, cmd: Sequence[str], env: Mapping[str, str], timeout: int
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append((list(cmd), dict(env), timeout))
        verb = " ".join(cmd[3:5])
        if self.timeout_at and self.timeout_at in verb:
            raise subprocess.TimeoutExpired(cmd, timeout)
        if self.fail_at and self.fail_at in verb:
            return subprocess.CompletedProcess(cmd, 2, "", "ERROR: algo falló\nultima linea")
        return subprocess.CompletedProcess(cmd, 0, "{}", "")


def make(
    tmp_path: Path,
    runner: FakeRunner,
    spec: ZoneSpec | None = SPEC,
    token: str | None = None,
) -> ProcessIngest:
    return ProcessIngest(
        data_dir=tmp_path,
        describe_zone=lambda _z: spec,
        runner=runner,
        earthdata_token=token,
        python="py",
    )


def verbs(r: FakeRunner) -> list[str]:
    return [" ".join(c[0][3:5]) if c[0][3] in {"fetch", "merge"} else c[0][3] for c in r.calls]


def test_without_token_runs_power_curate_validate_only(tmp_path: Path) -> None:
    r = FakeRunner()
    out = make(tmp_path, r).ingest_zone(uuid4())
    assert verbs(r) == ["fetch power", "curate", "validate"]
    assert out["imerg"] is False
    assert [s["step"] for s in out["steps"]] == ["fetch power", "curate", "validate"]
    assert all(s["ok"] for s in out["steps"])
    assert any("register provenance" in n for n in out["next_steps"])  # registro en BD: operador


def test_with_token_adds_imerg_and_merge_in_order(tmp_path: Path) -> None:
    r = FakeRunner()
    fake = secrets.token_urlsafe(24)  # valor ficticio generado en la prueba
    out = make(tmp_path, r, token=fake).ingest_zone(uuid4())
    assert verbs(r) == ["fetch power", "fetch imerg", "merge imerg", "curate", "validate"]
    assert out["imerg"] is True
    assert r.calls[1][1]["EARTHDATA_TOKEN"] == fake
    assert fake not in str(out)  # nunca vuelve en el resultado del trabajo


def test_child_environment_is_minimal_and_has_no_api_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:SECRETO@h/db")
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    monkeypatch.setenv("MIGRATION_DATABASE_URL", "postgresql://owner:SECRETO@h/db")
    r = FakeRunner()
    make(tmp_path, r).ingest_zone(uuid4())
    for _, env, _ in r.calls:
        assert not {
            "DATABASE_URL",
            "JWT_SECRET",
            "MIGRATION_DATABASE_URL",
            "EARTHDATA_TOKEN",
        } & set(env)
        assert env["DATA_DIR"] == str(tmp_path) and env["MILPA_MODE"] == "sandbox"


def test_arguments_are_a_list_with_numbers_formatted_not_a_shell_string(tmp_path: Path) -> None:
    r = FakeRunner()
    make(tmp_path, r).ingest_zone(uuid4())
    cmd = r.calls[0][0]
    assert isinstance(cmd, list) and cmd[:3] == ["py", "-m", "milpa_etl.cli"]
    assert cmd[cmd.index("--lat") + 1] == "14.800000"
    assert cmd[cmd.index("--zone") + 1] == "zona_de_prueba"
    assert "790.15" in r.calls[2][0]


@pytest.mark.parametrize("bad", ["../etc", "a b", "x;rm -rf /", "$(id)", "", "a" * 70, "ñandú"])
def test_zone_names_that_are_not_file_identifiers_are_rejected(tmp_path: Path, bad: str) -> None:
    r = FakeRunner()
    spec = ZoneSpec(bad, 1.0, 1.0, 10.0, SPEC.geojson)
    with pytest.raises(ValidationFailed):
        make(tmp_path, r, spec).ingest_zone(uuid4())
    assert r.calls == []  # nada se ejecuta


def test_missing_zone_or_elevation_is_a_validation_error_not_a_guess(tmp_path: Path) -> None:
    r = FakeRunner()
    with pytest.raises(ValidationFailed, match="no existe"):
        make(tmp_path, r, None).ingest_zone(uuid4())
    no_elev = ZoneSpec("z1", 1.0, 1.0, None, SPEC.geojson)
    with pytest.raises(ValidationFailed, match="elevación"):
        make(tmp_path, r, no_elev).ingest_zone(uuid4())
    assert r.calls == []


def test_a_failing_step_stops_the_pipeline_and_reports_which(tmp_path: Path) -> None:
    r = FakeRunner(fail_at="curate")
    with pytest.raises(IngestFailed, match=r"curate.*código 2.*ultima linea"):
        make(tmp_path, r).ingest_zone(uuid4())
    assert verbs(r) == ["fetch power", "curate"]  # validate no se ejecutó


def test_timeouts_and_missing_executable_become_controlled_errors(tmp_path: Path) -> None:
    with pytest.raises(IngestFailed, match="tiempo"):
        make(tmp_path, FakeRunner(timeout_at="fetch power")).ingest_zone(uuid4())

    def boom(*_a: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError

    p = ProcessIngest(data_dir=tmp_path, describe_zone=lambda _z: SPEC, runner=boom)
    with pytest.raises(IngestFailed, match="FileNotFoundError"):
        p.ingest_zone(uuid4())


def test_result_reports_the_data_hash_written_by_the_etl(tmp_path: Path) -> None:
    meta = tmp_path / "curated" / "zona_de_prueba"
    meta.mkdir(parents=True)
    (meta / "curated_meta.json").write_text('{"data_hash": "' + "ab" * 32 + '"}', encoding="utf-8")
    out = make(tmp_path, FakeRunner()).ingest_zone(uuid4())
    assert out["data_hash"] == "ab" * 32


def test_availability_reflects_whether_milpa_etl_is_installed(tmp_path: Path) -> None:
    expected = importlib.util.find_spec("milpa_etl") is not None
    assert make(tmp_path, FakeRunner()).is_available() is expected
