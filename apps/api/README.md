# MILPA RESILIENTE — Backend y plataforma (R3)

API FastAPI + PostgreSQL 16/PostGIS + trabajos en proceso + informes PDF. Monolito modular (ADR-001). **El `README.md` de la raíz es la especificación integral 3.3; este archivo describe solo `apps/api`.**

> Estado: infraestructura R3 implementada y probada **de forma independiente**. R1 (datos), R2 (`milpa_core`) y R4 (frontend) **no están integrados**: los endpoints que dependen de ellos responden `503 DEPENDENCY_NOT_INTEGRATED` y nunca devuelven resultados simulados. Detalle en `docs/integration/INTEGRATION_STATUS.md`.

## Estructura
```
apps/api/
├─ src/api/
│  ├─ main.py            fábrica de la app, middlewares, errores, OpenAPI
│  ├─ routers/           HTTP: validan y delegan (sin SQL ni lógica)
│  ├─ schemas/           DTO Pydantic (cada uno con x-contract-status)
│  ├─ services/          reglas de aplicación y autorización por pertenencia
│  ├─ repositories/      persistencia (SQLAlchemy 2)
│  ├─ models/            mapeos ORM
│  ├─ security/          Argon2id, JWT, límite de tasa, privacidad
│  ├─ jobs/              engine.job + ProcessPoolExecutor, worker, recuperación, borrado
│  ├─ reports/           contrato de entrada, renderizado seguro, servicio PDF
│  ├─ adapters/          puertos hacia R1/R2 (+ NotIntegrated, MilpaCoreEngine)
│  ├─ storage/           ObjectStore local y lector Parquet
│  ├─ reproducibility/   SHA-256, manifiestos, prerrequisitos de reproducción
│  ├─ db/ config/ mock/ bench/ cli.py logging_config.py errors.py soil_csv.py
├─ migrations/           Alembic (cadena única 0001…0013; DDL en sql/)
├─ templates/            plantilla de informe PROVISIONAL + CSS de impresión
└─ tests/                unitarias y de propiedades
```
Fuera de `apps/api`: `tests/{integration,privacy,contract}`, `testkit/` (fábricas y dobles de prueba), `infra/`, `docker-compose.yml`, `Makefile`, `.github/`, `docs/`.

## Puesta en marcha rápida
```bash
cp .env.example .env     # complete POSTGRES_PASSWORD, APP_DB_PASSWORD, JWT_SECRET
docker compose up --build -d
curl http://127.0.0.1:8000/healthz
```
Desarrollo, variables y primer usuario: `docs/DEPLOYMENT.md`.

## Comandos (`Makefile`; requiere GNU make)
`make setup · lint · test-unit · test-contract · test-integration · test · test-docker · db-up · db-migrate · build · up · demo · reproduce · report · openapi · mock · types · bench · audit`. Los objetivos de R1/R2/R4 (`seed, data, run-base, scenarios, test-science, test-e2e`) **fallan con mensaje** indicando el componente ausente.

## Documentación
`docs/BACKEND_AUDIT.md` · `docs/API.md` · `docs/DATABASE.md` · `docs/SECURITY.md` · `docs/PRIVACY.md` · `docs/JOBS.md` · `docs/REPORTS.md` · `docs/REPRODUCIBILITY.md` · `docs/TESTING.md` · `docs/DEPLOYMENT.md` · `docs/decisions/` (ADR) · `docs/integration/` (contratos y estado) · `docs/benchmarks/`.

## Reglas que no se rompen (CLAUDE.md)
Sin ciencia en la API · no importar `milpa_etl` · no inventar contratos (los provisionales están rotulados) · RLS + `SET LOCAL app.user_id` · nunca registrar tokens/contraseñas/coordenadas · sin Redis/Celery/ARQ/Dask · toda decisión estructural en un ADR.
