"""CLI de administración y utilidades de R3. ``python -m api.cli <comando>``.

Las contraseñas NUNCA se reciben por argumentos (quedarían en el historial del shell): se leen de la
variable ``NEW_USER_PASSWORD`` o de un prompt oculto. Las altas de usuarios usan la URL del rol
propietario (``MIGRATION_DATABASE_URL``): el rol de aplicación no tiene permiso para crear cuentas.
"""

from __future__ import annotations

import argparse
import contextlib
import getpass
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Engine, create_engine, text

from api.models.enums import ConsentPurpose, UserRole
from api.reports.contract import ReportInput


def _owner_engine() -> Engine:
    url = os.environ.get("MIGRATION_DATABASE_URL")
    if not url:
        print(
            "Defina MIGRATION_DATABASE_URL (rol propietario) para esta operación", file=sys.stderr
        )
        raise SystemExit(2)
    return create_engine(url.replace("postgresql://", "postgresql+psycopg://", 1))


def cmd_create_user(a: argparse.Namespace) -> int:
    from api.security.passwords import hash_password

    pw = os.environ.get("NEW_USER_PASSWORD") or getpass.getpass("Contraseña (no se muestra): ")
    try:
        pw_hash = hash_password(pw)
    except ValueError as exc:
        print(f"Contraseña rechazada: {exc}", file=sys.stderr)
        return 2
    with _owner_engine().begin() as c:
        uid = c.execute(
            text(
                "INSERT INTO auth.app_user (email, password_hash, role) VALUES (:e,:h,:r) RETURNING user_id"
            ),
            {"e": a.email.strip().lower(), "h": pw_hash, "r": UserRole(a.role).value},
        ).scalar_one()
    print(f"user_id={uid}")
    return 0


def cmd_create_farmer(a: argparse.Namespace) -> int:
    with _owner_engine().begin() as c:
        fid = c.execute(
            text(
                "INSERT INTO farm.farmer (user_id, display_name, community) "
                "SELECT user_id, :n, :c FROM auth.app_user WHERE email=:e RETURNING farmer_id"
            ),
            {"e": a.email.strip().lower(), "n": a.display_name, "c": a.community},
        ).scalar_one_or_none()
    if fid is None:
        print("No existe un usuario con ese correo", file=sys.stderr)
        return 2
    print(f"farmer_id={fid}")
    return 0


def cmd_grant_consent(a: argparse.Namespace) -> int:
    with _owner_engine().begin() as c:
        cid = c.execute(
            text(
                "INSERT INTO auth.consent (subject_user_id, purpose, text_version, granted_at) "
                "SELECT user_id, :p, :v, :t FROM auth.app_user WHERE email=:e RETURNING consent_id"
            ),
            {
                "e": a.email.strip().lower(),
                "p": ConsentPurpose(a.purpose).value,
                "v": a.text_version,
                "t": datetime.now(UTC),
            },
        ).scalar_one_or_none()
    print(f"consent_id={cid}" if cid else "No existe un usuario con ese correo")
    return 0 if cid else 2


def cmd_assign(a: argparse.Namespace) -> int:
    with _owner_engine().begin() as c:
        row = c.execute(
            text(
                "INSERT INTO farm.technician_assignment (technician_id, farmer_id, consent_id) "
                "SELECT t.user_id, f.farmer_id, co.consent_id FROM auth.app_user t, farm.farmer f "
                "JOIN auth.consent co ON co.subject_user_id = f.user_id AND co.purpose='analysis' AND co.withdrawn_at IS NULL "
                "WHERE t.email=:t AND f.user_id = (SELECT user_id FROM auth.app_user WHERE email=:f) "
                "ON CONFLICT (technician_id, farmer_id) DO UPDATE SET revoked_at=NULL, consent_id=EXCLUDED.consent_id "
                "RETURNING technician_id"
            ),
            {"t": a.technician_email.strip().lower(), "f": a.farmer_email.strip().lower()},
        ).first()
    if row is None:
        print(
            "Verifique que ambos existan y que el agricultor tenga consentimiento 'analysis' vigente",
            file=sys.stderr,
        )
        return 2
    print("asignación creada")
    return 0


def cmd_openapi(a: argparse.Namespace) -> int:
    os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://openapi:openapi@localhost/openapi")
    os.environ.setdefault("JWT_SECRET", "openapi-generation-only-not-a-real-secret-0123456789")
    from api.jobs.dispatch import NullDispatcher
    from api.main import create_app

    app = create_app(dispatcher=NullDispatcher(), recover_on_start=False)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"OpenAPI escrito en {out}")
    return 0


def sample_report_input(privacy: str, locale: str) -> ReportInput:
    """ENTRADA SINTÉTICA para probar el servicio PDF. No contiene resultados científicos."""
    h = "0" * 64
    return ReportInput.model_validate(
        {
            "locale": locale,
            "privacy_level": privacy,
            "zone_name": "Zona de ejemplo (sintética)",
            "hashes": {
                "code_version": "sample",
                "region_config_hash": h,
                "catalog_hash": h,
                "data_hash": h,
                "params_hash": h,
                "seed": 0,
            },
            "generated_at": datetime(2026, 1, 1, tzinfo=UTC),
            "summary_es": "Documento de prueba de la plantilla técnica provisional. Sin resultados científicos.",
            "summary_en": "Provisional technical template test document. No scientific results.",
            "sections": [
                {
                    "title_es": "Contenido de prueba",
                    "title_en": "Test content",
                    "body_es": "Texto de relleno para verificar paginación, tipografía y anexo.",
                    "body_en": "Placeholder text to verify layout and annex.",
                }
            ],
            "assumptions": ["Ninguno: documento sintético."],
            "limitations": ["No usar para decisiones."],
        }
    )


def cmd_report_sample(a: argparse.Namespace) -> int:
    from api.reports.renderer import FetchGuard, ReportRenderError, html_to_pdf, render_html
    from api.reproducibility.hashing import sha256_bytes

    try:
        pdf = html_to_pdf(render_html(sample_report_input(a.privacy, a.locale)), FetchGuard())
    except ReportRenderError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(pdf)
    print(
        f"PDF de prueba (plantilla PROVISIONAL): {out}  sha256={sha256_bytes(pdf)}  bytes={len(pdf)}"
    )
    return 0


def cmd_reproduce(a: argparse.Namespace) -> int:
    from api.reproducibility.runs import check_reproduce_prerequisites

    status = check_reproduce_prerequisites(Path(a.data_dir))
    for v in status.verified:
        print(f"VERIFICADO: {v}", file=sys.stderr)
    for m in status.missing:
        print(f"FALTA: {m}", file=sys.stderr)
    for n in status.notes:
        print(f"NOTA: {n}", file=sys.stderr)
    print(
        f"reproduce: NO completado (código {status.exit_code}). No se simula éxito.",
        file=sys.stderr,
    )
    return status.exit_code


def cmd_verify_manifest(a: argparse.Namespace) -> int:
    from api.reproducibility.hashing import MissingInputError
    from api.reproducibility.runs import load_manifest, verify_manifest

    try:
        rep = verify_manifest(load_manifest(Path(a.manifest)), Path(a.base))
    except MissingInputError as exc:
        print(f"FALTA: {exc}", file=sys.stderr)
        return 2
    for kind, items in (
        ("FALTA", rep.missing),
        ("HASH DISTINTO", rep.mismatched),
        ("ERROR", rep.errors),
    ):
        for i in items:
            print(f"{kind}: {i}", file=sys.stderr)
    print(f"verificados={rep.checked} ok={rep.ok}")
    return 0 if rep.ok else 2


def cmd_check_core(_: argparse.Namespace) -> int:
    from api.adapters.milpa_core import check_core_contract

    rep = check_core_contract()
    for p in rep.problems:
        print(f"PENDIENTE: {p}", file=sys.stderr)
    print("milpa_core: contrato de fachada OK" if rep.ok else "milpa_core: NO integrado")
    return 0 if rep.ok else 2


def cmd_register_engine(a: argparse.Namespace) -> int:
    """Registra (idempotente, rol propietario) el catálogo de R2 y la grilla de escenarios.

    Inserta ``ref.catalog_release`` con el hash real de ``catalogs/r2`` y ``engine.scenario_def``
    con la definición que publica ``milpa_core`` (BASE + grilla estándar). No toca otros datos.
    """
    import subprocess

    from api.adapters import core_io
    from api.adapters.milpa_core import import_core

    core = import_core()
    if core is None:
        print("milpa_core no está instalado", file=sys.stderr)
        return 2
    catalogs = core_io.load_catalogs(Path(a.catalogs))
    sha = os.environ.get("GIT_SHA") or "unversioned"
    if sha == "unversioned":
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            sha = subprocess.run(
                ["git", "rev-parse", "HEAD"],  # noqa: S607
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            ).stdout.strip()
    scenarios = {s.scenario_id: s for s in [core.BASE, *core.standard_grid()]}
    with _owner_engine().begin() as c:
        c.execute(
            text(
                "INSERT INTO ref.catalog_release (catalog_hash, git_sha) VALUES (:h, :g) "
                "ON CONFLICT (catalog_hash) DO NOTHING"
            ),
            {"h": catalogs.catalog_hash, "g": sha},
        )
        for sc in scenarios.values():
            c.execute(
                text(
                    "INSERT INTO engine.scenario_def (scenario_id, delta_t_c, precip_factor, "
                    "onset_delay_days, humidity_assumption, grid_role, method_doc) "
                    "VALUES (:i, :dt, :pf, :d, CAST(:h AS humidity_t), :r, :m) "
                    "ON CONFLICT (scenario_id) DO NOTHING"
                ),
                {
                    "i": sc.scenario_id,
                    "dt": sc.delta_t_c,
                    "pf": sc.precip_factor,
                    "d": sc.onset_delay_days,
                    "h": sc.humidity.value,
                    "r": sc.grid_role,
                    "m": sc.method_doc,
                },
            )
    print(f"catalog_hash={catalogs.catalog_hash} escenarios={len(scenarios)}")
    return 0


def cmd_hash(a: argparse.Namespace) -> int:
    from api.reproducibility.hashing import sha256_file

    print(sha256_file(Path(a.path)))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m api.cli", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("create-user", help="Alta de usuario (rol propietario)")
    s.add_argument("--email", required=True)
    s.add_argument("--role", required=True, choices=[r.value for r in UserRole])
    s.set_defaults(fn=cmd_create_user)
    s = sub.add_parser("create-farmer", help="Perfil de agricultor para un usuario")
    s.add_argument("--email", required=True)
    s.add_argument("--display-name", required=True)
    s.add_argument("--community")
    s.set_defaults(fn=cmd_create_farmer)
    s = sub.add_parser("grant-consent", help="Registrar consentimiento (uso administrativo)")
    s.add_argument("--email", required=True)
    s.add_argument("--purpose", required=True, choices=[c.value for c in ConsentPurpose])
    s.add_argument("--text-version", required=True)
    s.set_defaults(fn=cmd_grant_consent)
    s = sub.add_parser(
        "assign-technician", help="Asignar técnico a agricultor (requiere consentimiento)"
    )
    s.add_argument("--technician-email", required=True)
    s.add_argument("--farmer-email", required=True)
    s.set_defaults(fn=cmd_assign)
    s = sub.add_parser(
        "register-engine", help="Registrar catálogo de R2 y grilla de escenarios (propietario)"
    )
    s.add_argument("--catalogs", default="catalogs/r2")
    s.set_defaults(fn=cmd_register_engine)
    s = sub.add_parser("openapi", help="Exportar OpenAPI")
    s.add_argument("--out", default="docs/openapi/openapi.json")
    s.set_defaults(fn=cmd_openapi)
    s = sub.add_parser("report-sample", help="PDF de prueba con plantilla PROVISIONAL")
    s.add_argument("--out", default="data/results/sample_report.pdf")
    s.add_argument("--privacy", choices=["internal", "public"], default="public")
    s.add_argument("--locale", choices=["es", "es+en"], default="es+en")
    s.set_defaults(fn=cmd_report_sample)
    s = sub.add_parser("reproduce", help="Comprobar prerrequisitos de reproducción")
    s.add_argument("--data-dir", default=os.environ.get("DATA_DIR", "./data"))
    s.set_defaults(fn=cmd_reproduce)
    s = sub.add_parser("verify-manifest", help="Verificar archivos contra un manifiesto SHA-256")
    s.add_argument("manifest")
    s.add_argument("--base", default=".")
    s.set_defaults(fn=cmd_verify_manifest)
    s = sub.add_parser("check-core", help="Verificar la fachada de milpa_core (R2)")
    s.set_defaults(fn=cmd_check_core)
    s = sub.add_parser("hash", help="SHA-256 de un archivo")
    s.add_argument("path")
    s.set_defaults(fn=cmd_hash)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
