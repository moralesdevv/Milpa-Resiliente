"""Utilidades de prueba compartidas (constantes, fábricas de datos SINTÉTICOS de prueba)."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, text

ROOT = Path(__file__).resolve().parent.parent
ADMIN_URL = os.environ.get(
    "TEST_DATABASE_ADMIN_URL",
    "postgresql+psycopg://postgres:postgres_test_only@127.0.0.1:55432/postgres",
)
APP_ROLE = os.environ.get("TEST_APP_ROLE", "milpa_app")
APP_PASSWORD = os.environ.get("TEST_APP_ROLE_PASSWORD", "app_test_only")  # solo pruebas
JWT_SECRET_TEST = "unit-test-jwt-secret-with-at-least-32-chars!"
PASSWORD = "correct-horse-battery-staple"  # contraseña de usuarios de prueba (no es un secreto)


@dataclass(frozen=True)
class TestDb:
    __test__ = False
    name: str
    admin_url: str  # propietario (migraciones, fábricas)
    app_url: str  # rol de aplicación (RLS efectiva)


# --------------------------------------------------------------------------- fábricas de prueba
SQUARE = "POLYGON((-89.60 14.40, -89.40 14.40, -89.40 14.60, -89.60 14.60, -89.60 14.40))"
INSIDE = (14.5123456, -89.5123456)  # punto "exacto" de prueba (nunca debe persistirse ni loguearse)


class Factory:
    """Crea filas de prueba como propietario (sin pasar por la API). Datos SINTÉTICOS de prueba."""

    def __init__(self, engine: Engine) -> None:
        self.e = engine

    def _one(self, sql: str, **p: Any) -> Any:
        with self.e.connect() as c:
            return c.execute(text(sql), p).scalar_one()

    def _exec(self, sql: str, **p: Any) -> None:
        with self.e.connect() as c:
            c.execute(text(sql), p)

    def user(self, role: str, email: str | None = None, password: str = PASSWORD) -> dict[str, Any]:
        from api.security.passwords import hash_password

        email = email or f"{role}-{uuid.uuid4().hex[:8]}@example.org"
        uid = self._one(
            "INSERT INTO auth.app_user (email, password_hash, role) VALUES (:e, :h, :r) RETURNING user_id",
            e=email.lower(),
            h=hash_password(password),
            r=role,
        )
        return {"user_id": uid, "email": email.lower(), "password": password, "role": role}

    def farmer(self, user: dict[str, Any], name: str = "Agricultor de prueba") -> uuid.UUID:
        return self._one(  # type: ignore[no-any-return]
            "INSERT INTO farm.farmer (user_id, display_name, community) VALUES (:u, :n, 'Comunidad de prueba') "
            "RETURNING farmer_id",
            u=user["user_id"],
            n=name,
        )

    def consent(self, user: dict[str, Any], purpose: str = "analysis") -> uuid.UUID:
        return self._one(  # type: ignore[no-any-return]
            "INSERT INTO auth.consent (subject_user_id, purpose, text_version, granted_at) "
            "VALUES (:u, :p, 'v0-test', :t) RETURNING consent_id",
            u=user["user_id"],
            p=purpose,
            t=datetime.now(UTC),
        )

    def withdraw(self, consent_id: uuid.UUID) -> None:
        self._exec(
            "UPDATE auth.consent SET withdrawn_at = now() WHERE consent_id = :c", c=consent_id
        )

    def assign(
        self, technician: dict[str, Any], farmer_id: uuid.UUID, consent_id: uuid.UUID
    ) -> None:
        self._exec(
            "INSERT INTO farm.technician_assignment (technician_id, farmer_id, consent_id) VALUES (:t,:f,:c)",
            t=technician["user_id"],
            f=farmer_id,
            c=consent_id,
        )

    def region_zone(self) -> tuple[uuid.UUID, uuid.UUID]:
        region = self._one(
            "INSERT INTO geo.region (code, name, config_uri, config_hash, bbox) "
            "VALUES (:c, 'Región de prueba', 'test://region', repeat('0',64), ST_GeomFromText(:g,4326)) "
            "RETURNING region_id",
            c=f"R{uuid.uuid4().hex[:6]}",
            g=SQUARE,
        )
        zone = self._one(
            "INSERT INTO geo.zone (region_id, name, geom) VALUES (:r, 'Zona de prueba', "
            "ST_Multi(ST_GeomFromText(:g,4326))) RETURNING zone_id",
            r=region,
            g=SQUARE,
        )
        return region, zone

    def parcel(self, farmer_id: uuid.UUID, zone_id: uuid.UUID, code: str = "P-001") -> uuid.UUID:
        return self._one(  # type: ignore[no-any-return]
            "INSERT INTO farm.parcel (zone_id, farmer_id, code, display_geom, display_grid_m) "
            "VALUES (:z, :f, :c, ST_SetSRID(ST_MakePoint(-89.5, 14.5), 4326), 1000) RETURNING parcel_id",
            z=zone_id,
            f=farmer_id,
            c=code,
        )

    def soil_property(
        self,
        code: str = "ph",
        unit: str = "pH",
        vmin: float = 3.0,
        vmax: float = 10.0,
        methods: tuple[str, ...] = ("water_1_2_5",),
        max_age: int | None = None,
    ) -> None:
        self._exec(
            "INSERT INTO ref.soil_property (code, unit, valid_min, valid_max, accepted_methods, max_age_years) "
            "VALUES (:c,:u,:a,:b,:m,:g) ON CONFLICT DO NOTHING",
            c=code,
            u=unit,
            a=vmin,
            b=vmax,
            m=list(methods),
            g=max_age,
        )

    def sample_with_measurement(
        self, parcel_id: uuid.UUID, code: str = "ph", value: float = 6.5
    ) -> uuid.UUID:
        ip = self._one(
            "INSERT INTO prov.indicator_provenance (indicator_code, unit, provenance, evidence_level, source_ids, "
            "processing_method, evidence_rule_id) VALUES (:c,'pH','medido','C','{}','test-fixture','test-rule') "
            "RETURNING ip_id",
            c=code,
        )
        sample = self._one(
            "INSERT INTO soil.sample (parcel_id, sampled_at, depth_from_cm, depth_to_cm) "
            "VALUES (:p, current_date, 0, 20) RETURNING sample_id",
            p=parcel_id,
        )
        self._exec(
            "INSERT INTO soil.measurement (sample_id, property_code, value, unit, method, representativeness, ip_id) "
            "VALUES (:s,:c,:v,'pH','water_1_2_5','parcela',:i)",
            s=sample,
            c=code,
            v=value,
            i=ip,
        )
        return ip  # type: ignore[no-any-return]

    # ---- corridas y escenarios: FILAS DE PRUEBA que representan "una corrida existe" ------------
    # (no contienen resultados científicos; los hashes son marcadores fijos de prueba)
    def run(
        self,
        zone_id: uuid.UUID,
        parcel_id: uuid.UUID | None = None,
        status: str = "ok",
        created_by: uuid.UUID | None = None,
    ) -> uuid.UUID:
        rel = self._one(
            "INSERT INTO ref.catalog_release (catalog_hash, git_sha) VALUES (:h, 'test') "
            "ON CONFLICT (catalog_hash) DO UPDATE SET git_sha='test' RETURNING catalog_release_id",
            h="c" * 64,
        )
        return self._one(  # type: ignore[no-any-return]
            "INSERT INTO engine.analysis_run (zone_id, parcel_id, period_start, period_end, mode, params, "
            "params_hash, region_config_hash, catalog_release_id, data_hash, code_version, seed, status, created_by) "
            "VALUES (:z,:p,'2001-01-01','2025-12-31','exposure','{}',:h1,:h2,:r,:h3,'test-code-version',42,:s,:u) "
            "RETURNING run_id",
            z=zone_id,
            p=parcel_id,
            h1="a" * 64,
            h2="b" * 64,
            h3="d" * 64,
            r=rel,
            s=status,
            u=created_by,
        )

    def scenario(
        self,
        run_id: uuid.UUID,
        scenario_id: str = "BASE",
        adaptation: str = "none",
        status: str = "ok",
    ) -> None:
        self._exec(
            "INSERT INTO engine.scenario_def (scenario_id, delta_t_c, precip_factor, onset_delay_days, "
            "humidity_assumption, grid_role, method_doc) VALUES (:s, 0, 1, 0, 'not_applicable', 'baseline', 'test') "
            "ON CONFLICT DO NOTHING",
            s=scenario_id,
        )
        self._exec(
            "INSERT INTO engine.scenario_run (run_id, scenario_id, adaptation_mode, status, results_uri, "
            "engine_version) VALUES (:r,:s,:a,:st,'test://uri','test-engine')",
            r=run_id,
            s=scenario_id,
            a=adaptation,
            st=status,
        )

    def report(
        self,
        user_id: uuid.UUID,
        run_id: uuid.UUID | None,
        privacy: str = "internal",
        pdf_uri: str | None = None,
    ) -> uuid.UUID:
        return self._one(  # type: ignore[no-any-return]
            "INSERT INTO report.report (run_id, privacy_level, content_json, pdf_uri, pdf_sha256, generated_by) "
            "VALUES (:r,:p,'{}',:u,:h,:g) RETURNING report_id",
            r=run_id,
            p=privacy,
            u=pdf_uri,
            h=("e" * 64 if pdf_uri else None),
            g=user_id,
        )
