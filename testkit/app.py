"""Escenario de pruebas y construcción de Settings (datos SINTÉTICOS de prueba)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from api.config import Settings
from testkit import JWT_SECRET_TEST, Factory, TestDb


def make_settings(db: TestDb, data_dir: Path, **over: Any) -> Settings:
    values: dict[str, Any] = {
        "database_url": db.app_url,
        "jwt_secret": JWT_SECRET_TEST,
        "data_dir": data_dir,
        "rate_limit_per_min": 100_000,
        "login_lock_threshold": 3,
        "milpa_mode": "sandbox",
    }
    values.update(over)
    return Settings(**values)


class World:
    """Escenario base: dos agricultores, un técnico asignado a uno solo, un admin y una zona."""

    def __init__(self, f: Factory) -> None:
        self.f = f
        self.region, self.zone = f.region_zone()
        self.farmer_a_user = f.user("agricultor")
        self.farmer_b_user = f.user("agricultor")
        self.tech = f.user("tecnico")
        self.tech_unassigned = f.user("tecnico")
        self.admin = f.user("admin")
        self.farmer_a = f.farmer(self.farmer_a_user, "Agricultora A")
        self.farmer_b = f.farmer(self.farmer_b_user, "Agricultor B")
        self.consent_a = f.consent(self.farmer_a_user)
        self.consent_b = f.consent(self.farmer_b_user)
        f.assign(self.tech, self.farmer_a, self.consent_a)
        self.parcel_a = f.parcel(self.farmer_a, self.zone, "PARCELA-A")
        self.parcel_b = f.parcel(self.farmer_b, self.zone, "PARCELA-B")
