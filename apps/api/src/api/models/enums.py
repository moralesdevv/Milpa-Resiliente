"""Enums de infraestructura cuyo origen canónico es R3 (README §13.1: user_role_t, job_status_t).

Los enums científicos NO están aquí (ver ``api.contracts.provisional_enums``).
Paridad Python <-> SQL <-> OpenAPI: tests/contract/test_enum_parity.py.
"""

from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    tecnico = "tecnico"
    agricultor = "agricultor"
    admin = "admin"


class JobStatus(StrEnum):
    queued = "queued"
    running = "running"
    ok = "ok"
    failed = "failed"
    cancelled = "cancelled"


class JobKind(StrEnum):
    # Definidos por la especificación (README §13.6):
    zone_ingest = "zone_ingest"
    analysis_run = "analysis_run"
    scenario_run = "scenario_run"
    report = "report"
    # Extensión R3 (ADR-007, pendiente de aprobación):
    parcel_delete = "parcel_delete"
    consent_purge = "consent_purge"


class ConsentPurpose(StrEnum):
    analysis = "analysis"
    report_sharing = "report_sharing"
    exact_geometry = "exact_geometry"


class PrivacyLevel(StrEnum):
    internal = "internal"
    public = "public"
