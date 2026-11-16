"""Fábrica de la aplicación FastAPI (monolito modular). ``uvicorn api.main:app``."""

from __future__ import annotations

import logging
import re
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import Engine
from sqlalchemy.exc import DataError, IntegrityError, OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.adapters.ports import Ports
from api.adapters.registry import load_ports
from api.config import Settings, get_settings
from api.contracts.r2_draft import apply_r2_dto_draft
from api.db.engine import dispose_engines, get_engine
from api.db.invariants import SecurityInvariantViolation, assert_security_invariants
from api.errors import ApiError, ErrorCode, RateLimited, problem_type
from api.jobs.dispatch import JobDispatcher, ProcessPoolDispatcher, WorkerConfig
from api.jobs.recovery import recover_jobs
from api.logging_config import configure_logging, request_id_var
from api.routers import auth, catalog, parcels, runs, zones
from api.routers.reports_jobs import health_router, jobs_router, reports_router
from api.security.ratelimit import SlidingWindowLimiter
from api.storage.object_store import LocalObjectStore

log = logging.getLogger("api")
_REQ_ID_RE = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
MAX_JSON_BODY = 1024 * 1024  # 1 MiB para endpoints JSON; el CSV tiene su propio límite

TAGS = [
    {"name": "auth", "description": "Sesión JWT"},
    {"name": "zones", "description": "Zonas climáticas (dato público de análisis)"},
    {"name": "parcels", "description": "Parcelas, suelo y prioridades (datos privados, RLS)"},
    {"name": "catalog", "description": "Catálogos de R1"},
    {"name": "runs", "description": "Corridas y análisis (requiere milpa_core de R2)"},
    {"name": "provenance", "description": "Procedencia de indicadores"},
    {"name": "reports", "description": "Informes PDF"},
    {"name": "jobs", "description": "Trabajos asíncronos"},
    {"name": "health", "description": "Salud"},
]


def problem_response(
    status: int,
    code: ErrorCode | str,
    title: str,
    detail: str,
    *,
    errors: list[dict[str, Any]] | None = None,
    hint: str | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = {
        "type": problem_type(code),
        "title": title,
        "status": status,
        "code": str(code),
        "detail": detail,
        "request_id": request_id_var.get(),
        "errors": errors or [],
    }
    if hint:
        body["hint"] = hint
    return JSONResponse(
        body, status_code=status, headers=headers, media_type="application/problem+json"
    )


def _verify_security_invariants(engine: Engine) -> None:
    """Falla cerrado si RLS puede evadirse; si la base no responde, lo registra (``/healthz``)."""
    try:
        assert_security_invariants(engine)
    except SecurityInvariantViolation:
        log.critical("security_invariants_violated")
        raise
    except Exception as exc:  # base no disponible: no se puede verificar
        log.error("security_invariants_unchecked", extra={"exc_type": type(exc).__name__})


def create_app(
    settings: Settings | None = None,
    *,
    engine: Engine | None = None,
    ports: Ports | None = None,
    dispatcher: JobDispatcher | None = None,
    recover_on_start: bool = True,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        _verify_security_invariants(app.state.engine)
        if recover_on_start:
            try:
                recover_jobs(
                    app.state.engine, app.state.dispatcher, max_attempts=settings.job_max_attempts
                )
            except Exception as exc:
                log.error("job_recovery_failed", extra={"exc_type": type(exc).__name__})
        yield
        app.state.dispatcher.shutdown()
        dispose_engines()

    app = FastAPI(
        title="MILPA RESILIENTE — API (R3)",
        version="0.1.0",
        description=(
            "Backend y plataforma de MILPA RESILIENTE 3.3. **OpenAPI v0.** Los esquemas marcados "
            "`x-contract-status: provisional_r3` o `pending_r2` NO son contratos definitivos "
            "(ver docs/integration/). Los cálculos científicos pertenecen a `milpa_core` (R2)."
        ),
        openapi_tags=TAGS,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine or get_engine(settings.database_url)
    app.state.ports = ports or load_ports()
    app.state.store = LocalObjectStore(settings.data_dir)
    app.state.dispatcher = dispatcher or ProcessPoolDispatcher(
        WorkerConfig.from_settings(settings), settings.job_max_workers
    )
    app.state.ip_limiter = SlidingWindowLimiter(settings.rate_limit_per_min)
    app.state.user_limiter = SlidingWindowLimiter(settings.rate_limit_per_min)

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "If-None-Match"],
            expose_headers=["Location", "ETag", "X-Request-ID"],
        )

    @app.middleware("http")
    async def request_context(request: Request, call_next: Any) -> Response:
        rid = request.headers.get("x-request-id", "")
        rid = rid if _REQ_ID_RE.match(rid) else uuid.uuid4().hex
        token = request_id_var.set(rid)
        start = time.perf_counter()
        try:
            response = await _guarded(request, call_next, settings)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = rid
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cache-Control", "no-store")
        route = request.scope.get("route")
        # Se registra la plantilla de ruta (sin ids ni query string): nada sensible en el log.
        log.info(
            "request",
            extra={
                "method": request.method,
                "route": getattr(route, "path", "unmatched"),
                "status": response.status_code,
                "duration_ms": int((time.perf_counter() - start) * 1000),
                "request_id": rid,
            },
        )
        return response

    _register_handlers(app)
    for r in (
        auth.router,
        zones.router,
        parcels.router,
        catalog.router,
        runs.router,
        runs.provenance_router,
        reports_router,
        jobs_router,
    ):
        app.include_router(r, prefix="/v1")
    app.include_router(health_router)
    _customize_openapi(app)
    if settings.web_dist_dir.is_dir():  # frontend estático de R4 (cuando lo entregue)
        from fastapi.staticfiles import StaticFiles

        class SpaFiles(StaticFiles):
            """Sirve ``index.html`` para rutas del enrutador del cliente (``/calendar``…)."""

            async def get_response(self, path: str, scope: Any) -> Response:
                try:
                    return await super().get_response(path, scope)
                except StarletteHTTPException as exc:
                    norm = path.replace("\\", "/").lstrip("/")  # Windows entrega "v1\x"
                    leaf = norm.rsplit("/", 1)[-1]
                    if exc.status_code == 404 and "." not in leaf and not norm.startswith("v1/"):
                        return await super().get_response("index.html", scope)
                    raise

        app.mount("/", SpaFiles(directory=settings.web_dist_dir, html=True), name="web")
    return app


async def _guarded(request: Request, call_next: Any, settings: Settings) -> Response:
    """Límites previos al enrutado: tasa por IP, modo demo de solo lectura y tamaño de cuerpo."""
    path = request.url.path
    app = request.app
    if path != "/healthz":
        ip = request.client.host if request.client else "unknown"
        if settings.trust_forwarded_for and (xff := request.headers.get("x-forwarded-for")):
            ip = xff.split(",")[0].strip()
        try:
            app.state.ip_limiter.check(ip)
        except RateLimited as exc:
            return problem_response(429, exc.code, exc.title, exc.detail, headers=exc.headers)
    if settings.demo_readonly and request.method in _MUTATING and path != "/v1/auth/login":
        return problem_response(
            403,
            ErrorCode.READ_ONLY_MODE,
            "Modo de solo lectura",
            "La instancia de demostración es de solo lectura.",
        )
    length = request.headers.get("content-length")
    is_csv = path.endswith("/soil-samples")
    if not is_csv and length and length.isdigit() and int(length) > MAX_JSON_BODY:
        return problem_response(
            413,
            ErrorCode.PAYLOAD_TOO_LARGE,
            "Contenido demasiado grande",
            "El cuerpo de la solicitud excede el máximo permitido.",
        )
    return await call_next(request)  # type: ignore[no-any-return]


def _register_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return problem_response(
            exc.status,
            exc.code,
            exc.title,
            exc.detail,
            errors=exc.errors,
            hint=exc.hint,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Nunca se devuelve 'input' ni 'ctx': pueden contener datos privados (coordenadas, CSV).
        items = [
            {"loc": [str(p) for p in e["loc"]], "msg": e["msg"], "code": e["type"]}
            for e in exc.errors()
        ]
        malformed = any(e["code"] in {"json_invalid", "model_attributes_type"} for e in items)
        return problem_response(
            400 if malformed else 422,
            ErrorCode.VALIDATION_ERROR,
            "Solicitud mal formada" if malformed else "Error de validación",
            "La solicitud no cumple el contrato.",
            errors=items,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        codes = {
            401: ErrorCode.UNAUTHENTICATED,
            403: ErrorCode.FORBIDDEN,
            404: ErrorCode.NOT_FOUND,
            429: ErrorCode.RATE_LIMITED,
        }
        code = codes.get(exc.status_code, ErrorCode.VALIDATION_ERROR)
        return problem_response(
            exc.status_code,
            code,
            "Error HTTP",
            "Solicitud no válida.",
            headers=dict(exc.headers or {}),
        )

    @app.exception_handler(OperationalError)
    async def _db_down(_: Request, exc: OperationalError) -> JSONResponse:
        log.error("db_operational_error", extra={"exc_type": type(exc).__name__})
        return problem_response(
            503,
            ErrorCode.SERVICE_UNAVAILABLE,
            "Servicio no disponible",
            "La base de datos no está disponible.",
        )

    @app.exception_handler(DataError)
    async def _bad_data(_: Request, exc: DataError) -> JSONResponse:
        # Valor que PostgreSQL no admite (p. ej. carácter NUL, desborde numérico): error de entrada.
        log.warning("db_data_error", extra={"exc_type": type(exc).__name__})
        return problem_response(
            422,
            ErrorCode.VALIDATION_ERROR,
            "Error de validación",
            "Algún valor enviado contiene datos que no se pueden procesar.",
        )

    @app.exception_handler(IntegrityError)
    async def _integrity(_: Request, exc: IntegrityError) -> JSONResponse:
        log.warning("db_integrity_error", extra={"exc_type": type(exc).__name__})
        return problem_response(
            409,
            ErrorCode.VALIDATION_ERROR,
            "Conflicto",
            "La operación entra en conflicto con el estado actual de los datos.",
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.error("unhandled_exception", extra={"exc_type": type(exc).__name__})
        return problem_response(
            500,
            ErrorCode.INTERNAL_ERROR,
            "Error interno",
            "Ocurrió un error interno. Indique el request_id al soporte técnico.",
        )


def _customize_openapi(app: FastAPI) -> None:
    def build() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        from fastapi.openapi.utils import get_openapi

        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
            tags=TAGS,
        )
        schema["info"]["x-contract-status"] = "openapi_v0_draft"
        _use_problem_detail_for_validation_errors(schema)
        apply_r2_dto_draft(schema)
        app.openapi_schema = schema
        return schema

    app.openapi = build  # type: ignore[method-assign]


def _use_problem_detail_for_validation_errors(schema: dict[str, Any]) -> None:
    """FastAPI documenta el 422 con HTTPValidationError, pero esta API responde con ProblemDetail."""
    target = {"$ref": "#/components/schemas/ProblemDetail"}
    for ops in schema["paths"].values():
        for op in ops.values():
            for resp in op.get("responses", {}).values():
                for media in resp.get("content", {}).values():
                    if media.get("schema", {}).get("$ref", "").endswith("/HTTPValidationError"):
                        media["schema"] = dict(target)
                        resp["description"] = "Error de validación"
    # RFC 7807: los errores se sirven como application/problem+json; OpenAPI debe declararlo así.
    for ops in schema["paths"].values():
        for op in ops.values():
            for code, resp in op.get("responses", {}).items():
                content = resp.get("content", {})
                if str(code)[0] in "45" and "application/json" in content:
                    ref = content["application/json"].get("schema", {}).get("$ref", "")
                    if ref.endswith("/ProblemDetail"):
                        content["application/problem+json"] = content.pop("application/json")
    comps = schema.get("components", {}).get("schemas", {})
    for name in ("HTTPValidationError", "ValidationError"):
        comps.pop(name, None)


def _lazy_app() -> FastAPI:
    return create_app()


def __getattr__(name: str) -> FastAPI:
    # `uvicorn api.main:app` crea la aplicación bajo demanda (importar el módulo no exige entorno).
    if name == "app":
        global _APP  # noqa: PLW0603
        if _APP is None:
            _APP = _lazy_app()
        return _APP
    raise AttributeError(name)


_APP: FastAPI | None = None
